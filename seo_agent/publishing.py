"""Human-only CMS review and deterministic, durable publication orchestration.

Same-user local Python is not an authentication boundary. Only publication_ui
calls configuration/authorization/execution; workers and imports never do.
"""
from contextlib import closing
import json
import re

from . import tracking as t
from .coordination import run_lock, workspace_lock
from .storage import new_id, utc_now, checked_id, PUBLISHING_TABLES, cms_destination_key
from .wordpress import WordPress, CMSVault, CMSFailure, destination_url, inspect_state, rendered, bind_public_target, masked_content
from . import elementor_publishing as ep

STATEMENT = "I approve these exact CMS writes"
SCOPE = ("Briefly lock CMS posts/options inventory and the page metadata for conflict checks. "
         "Replace only the identified page-local core/heading text in post_content; "
         "update post_modified and post_modified_gmt; retain a server journal with before/after content; "
         "invalidate this page's WordPress cache. No editor, autosave, draft, status change, "
         "post-title, SEO-title, template, plugin, option or metadata write. "
         "Each action commits separately. Stop after uncertainty or failed verification.")


def rows(store, sid, table):
    if table not in PUBLISHING_TABLES:
        raise ValueError("Unknown publication table")
    store.site(sid)
    with store.db() as db:
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in db.execute(
            f"SELECT * FROM {table} WHERE site_id=? ORDER BY rowid", (sid,))]


def record(store, sid, table, identity):
    checked_id(identity)
    found = next((r for r in rows(store, sid, table) if r.get("id") == identity), None)
    if found is None:
        raise ValueError("Publication record does not belong to the selected site")
    return found


def destination(store, sid):
    found = rows(store, sid, "cms_destinations")
    return found[0]["payload"] if found else None


def configure_from_human_ui(store, sid, *, url, instance, environment, username, password,
                            isolation, human_clicked, isolation_verified=False, vault=None,
                            adapter="core-heading/1", discovery_id=None):
    store.require_private_write()
    if human_clicked is not True or not instance.strip() or len(instance) > 100:
        raise ValueError("Human destination configuration and instance identifier required")
    destination_url(url, environment)
    if environment == "production" and url != store.site(sid).url:
        raise ValueError("Production destination must exactly match the selected site's canonical URL")
    if environment in {"staging", "local"} and (isolation_verified is not True or len(isolation.strip()) < 30 or url == store.site(sid).url):
        raise ValueError("Separate staging destination and explicit isolation evidence required")
    if adapter not in {"core-heading/1", ep.ADAPTER}:
        raise ValueError("Unsupported publishing adapter")
    with run_lock(workspace_lock(store.root)):
        from .publisher_setup import evidence_binding
        binding = evidence_binding(store, sid, url=url, instance=instance, environment=environment,
                                   adapter=adapter, discovery_id=discovery_id)
        key = new_id()  # Never reuse a restored or previously configured credential reference.
        (vault or CMSVault()).write(key, username, password)
        payload = {"url": url, "instance": instance, "environment": environment, "isolation": isolation,
                   "credential_id": key, "generation": new_id(), "enabled": True,
                   "site_url": store.site(sid).url, "configured": utc_now(), "isolation_verified_by_human": isolation_verified,
                   "adapter": adapter, "discovery_binding": binding}
        with store.db() as db:
            db.execute("INSERT INTO cms_destinations VALUES (?,?) ON CONFLICT(site_id) DO UPDATE SET payload=excluded.payload",
                       (sid, t.canonical(payload)))


def disable(store, sid):
    store.require_private_write()
    with run_lock(workspace_lock(store.root)), store.db() as db:
        d = destination(store, sid)
        if d:
            d.update(enabled=False, credential_id=None, generation=new_id())
            db.execute("UPDATE cms_destinations SET payload=? WHERE site_id=?", (t.canonical(d), sid))


def disable_restored(store):
    with store.db() as db:
        for row in db.execute("SELECT site_id,payload FROM cms_destinations").fetchall():
            d = json.loads(row[1])
            d.update(enabled=False, credential_id=None, generation=new_id())
            db.execute("UPDATE cms_destinations SET payload=? WHERE site_id=?", (t.canonical(d), row[0]))
        for table in ("cms_reviews", "cms_authorizations", "cms_attempts"):
            for row in db.execute(f"SELECT id,payload FROM {table}").fetchall():
                db.execute(f"UPDATE {table} SET payload=? WHERE id=?", (t.canonical({**json.loads(row[1]), "history_only": True}), row[0]))


def active_destination(store, sid, *, recovery=False):
    d = destination(store, sid)
    if not d or not d.get("enabled") or not d.get("credential_id") or d.get("site_url") != store.site(sid).url:
        raise ValueError("Publishing disabled; a human must configure this exact destination and credentials")
    if not recovery:
        from .publisher_setup import validate_binding
        validate_binding(store, sid, d)
    return d


def approval(store, sid, bid):
    b = t.batch(store, sid, bid)
    if b["payload"]["fingerprint"] != t.digest(b["payload"]["actions"]):
        raise ValueError("Frozen batch fingerprint mismatch")
    found = [a for a in t.rows(store, "human_approvals", sid) if a["batch_id"] == bid]
    if not found or found[-1]["payload"].get("history_only") or found[-1]["payload"].get("fingerprint") != b["payload"]["fingerprint"]:
        raise ValueError("Fresh exact human proposal approval required; historical receipts are not permission")
    return b, found[-1]


def mapped_url(d, site_url, url):
    if not url.startswith(site_url):
        raise ValueError("URL is outside selected site")
    return d["url"] + url[len(site_url):]


def prepare(store, sid, bid, mappings, *, client_factory=WordPress):
    """Read-only CMS discovery; mappings explicitly enumerate action/page/anchor."""
    store.require_private_write()
    with run_lock(workspace_lock(store.root)):
        d = active_destination(store, sid)
        b, a = approval(store, sid, bid)
        if t.batch_validity(store, sid, bid):
            raise ValueError("Frozen proposal approval is stale; refresh and review again")
        if set(mappings) != {v["action_id"] for v in b["payload"]["actions"]}:
            raise ValueError("Map every frozen action exactly once")
        prepared, pages = [], set()
        key = cms_destination_key(d)
        attempts = rows(store, sid, "cms_attempts")
        known = {r["id"]: r["destination_key"] for r in attempts}
        with closing(client_factory(d)) as client:
            for f in b["payload"]["actions"]:
                value, mapping = f["action"], mappings[f["action_id"]]
                is_elementor = d.get("adapter") == ep.ADAPTER
                expected_keys = {"object_id", "element_id", "metadata_row_id"} if is_elementor else {"object_id", "anchor"}
                if set(mapping) != expected_keys or value["action_kind"] != "text":
                    raise ValueError("Only explicitly mapped static heading text is supported; titles/settings are separate fields")
                page, anchor = mapping["object_id"], mapping.get("anchor", "elementor")
                if type(page) is not int or page < 1 or page in pages or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", anchor):
                    raise ValueError("Use one action per page and a unique explicit heading anchor")
                pages.add(page)
                if any(x["action_id"] == f["action_id"] and x["revision"] == f["revision"] and x["destination_key"] == key for x in attempts):
                    raise ValueError("This revision has already been attempted; reconcile it, never reuse its authorization")
                if any(x["action_id"] == f["action_id"] and x["revision"] == f["revision"] and (known.get(x["payload"]["attempt_id"]) == key if x["payload"]["attempt_id"] in known
                        else x["payload"]["environment"] == d["environment"])
                       for x in t.rows(store, "implementation_receipts", sid)):
                    raise ValueError("Historical implementation receipts cannot authorize another publication")
                url = mapped_url(d, store.site(sid).url, value["url"])
                state = client.state(page)
                inspect_state(d, state, url)
                if state.get("id") != page:
                    raise ValueError("CMS object identity mismatch")
                for heading_value in (value["current"], value["proposed"]):
                    if not heading_value.strip() or any(c in heading_value for c in "<>[]\r\n") or len(heading_value) > 500:
                        raise ValueError("Both forward and rollback values must be single-line plain heading text up to 500 characters, without markup or shortcode brackets")
                source = client.public(url)
                if is_elementor:
                    extra = ep.prepare(state, source, f, mapping)
                    from .publisher_setup import validate_installation, staging_proof
                    validate_installation(store, sid, d, state)
                    extra["staging_validation"] = staging_proof(store, sid, d, f, state)
                else:
                    matches = [v for v in state["headings"] if v["anchor"] == anchor and v["text"] == value["current"]]
                    if len(matches) != 1:
                        raise ValueError("CMS heading/current value is ambiguous or differs from the frozen action")
                    bind_public_target(source["html"], f.get("target"), anchor)
                    masked_content(state["content"], anchor, value["current"])
                    extra = {"field": "post_content:core/heading", "anchor": anchor, "block_index": matches[0]["block_index"],
                             "rendered_baseline": rendered(source, anchor, value["current"]),
                             "validation": "Exact CMS page/anchor/value and rendered heading matched; adjacent content and directives captured"}
                if client.state(page)["token"] != state["token"]:
                    raise ValueError("CMS changed while collecting the public baseline; prepare a fresh review")
                prepared.append({"action_id": f["action_id"], "revision": f["revision"], "url": url,
                    "source_url": value["url"], "object_id": page, "current": value["current"], "proposed": value["proposed"],
                    "before": state, "confirmations": value["confirmations"], **extra,
                    "rollback": {"current": value["proposed"], "proposed": value["current"], "requires": "Fresh whole-page token from the successful write; stop if any subsequent edit"}})
        payload = {"batch_id": bid, "approval_id": a["id"], "batch_fingerprint": b["payload"]["fingerprint"],
                   "destination": d, "actions": prepared, "write_scope": ep.SCOPE if d.get("adapter") == ep.ADAPTER else SCOPE, "reviewed_utc": utc_now()}
        rid = new_id()
        payload["fingerprint"] = t.digest(payload)
        with store.db() as db:
            db.execute("INSERT INTO cms_reviews VALUES (?,?,?,?)", (rid, sid, utc_now(), t.canonical(payload)))
        return rid


def validate_review(store, sid, review):
    p = review["payload"]
    if p.get("history_only") or p["fingerprint"] != t.digest({k: v for k, v in p.items() if k != "fingerprint"}):
        raise ValueError("Restored or altered CMS review is not reusable permission")
    if active_destination(store, sid) != p["destination"]:
        raise ValueError("Destination changed since review")
    b, a = approval(store, sid, p["batch_id"])
    if a["id"] != p["approval_id"] or b["payload"]["fingerprint"] != p["batch_fingerprint"]:
        raise ValueError("Proposal approval changed")
    from .publisher_setup import validate_staging_proof
    for action in p["actions"]:
        if action.get("adapter") == ep.ADAPTER:
            validate_staging_proof(store, sid, p["destination"], action)
    return p


def authorize_from_human_ui(store, sid, rid, *, human_clicked, statement, confirmation_source, rollback):
    store.require_private_write()
    if human_clicked is not True or statement != STATEMENT or not confirmation_source.strip() or len(confirmation_source) > 4000 or type(rollback) is not bool:
        raise ValueError("Explicit human approval of this CMS review and factual confirmations required")
    with run_lock(workspace_lock(store.root)), store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        r = record(store, sid, "cms_reviews", rid)
        p = validate_review(store, sid, r)
        if t.batch_validity(store, sid, p["batch_id"]):
            raise ValueError("Proposal approval is stale")
        identity = new_id()
        db.execute("INSERT INTO cms_authorizations VALUES (?,?,?,?,?)", (identity, sid, rid, utc_now(), t.canonical({
            "fingerprint": p["fingerprint"], "origin": "explicit human UI submission", "statement": statement,
            "confirmation_source": confirmation_source, "rollback": rollback})))
        return identity


def event(store, sid, attempt, **payload):
    with store.db() as db:
        db.execute("INSERT INTO cms_events VALUES (?,?,?,?,?)", (new_id(), sid, attempt, utc_now(), t.canonical(payload)))


def latest_event(store, sid, attempt):
    found = [r for r in rows(store, sid, "cms_events") if r["attempt_id"] == attempt]
    return found[-1]["payload"] if found else {"write": "uncertain", "verification": "not_run"}


def proven_result(store, sid, attempt):
    """Success is an immutable historical fact, even if the server later restores."""
    found = [r["payload"]["result"] for r in rows(store, sid, "cms_events")
             if r["attempt_id"] == attempt and r["payload"].get("write") == "succeeded" and r["payload"].get("result")]
    return found[-1] if found else None


def export_review(store, sid, rid):
    """Inert receipt packet; never importable as executable authority."""
    review = record(store, sid, "cms_reviews", rid)
    review["payload"]["destination"].pop("credential_id", None)
    attempts = [r for r in rows(store, sid, "cms_attempts") if r["review_id"] == rid]
    ids = {r["id"] for r in attempts}
    return {"schema": "cms-publication-history/1", "history_only": True, "site_id": sid, "review": review,
            "authorization_history_not_reusable_permission": [r for r in rows(store, sid, "cms_authorizations") if r["review_id"] == rid],
            "attempts": attempts, "events": [r for r in rows(store, sid, "cms_events") if r["attempt_id"] in ids]}


def auth_for(store, sid, rid):
    found = next((r for r in rows(store, sid, "cms_authorizations") if r["review_id"] == rid), None)
    review = record(store, sid, "cms_reviews", rid)
    if not found or found["payload"].get("history_only") or found["payload"]["fingerprint"] != review["payload"]["fingerprint"]:
        raise ValueError("This exact CMS review needs explicit human authorization")
    return found


def check_action(store, sid, p, a):
    if a["action_id"] in t.batch_validity(store, sid, p["batch_id"]):
        raise ValueError("Action revision, factual confirmation, validation or public evidence is stale")


def receipt(store, sid, p, a, attempt_id, outcome, actual=None, verification=""):
    # Feed existing trends/history; dedicated CMS events remain the durable executor journal.
    environment = p["destination"]["environment"]
    t.record_receipt(store, sid, {"schema": "seo-implementation-receipt/1", "receipt_id": new_id(), "site_id": sid,
        "action_id": a["action_id"], "revision": a["revision"], "attempt_id": attempt_id, "environment": environment,
        "outcome": outcome, "occurred_utc": utc_now(), "current": a["current"], "proposed": a["proposed"], "actual": actual,
        "approval_id": p["approval_id"] if environment == "production" else None,
        "source": "Application-controlled CMS publication; " + p["fingerprint"], "verification": verification, "corrects": None})


def verify(store, sid, client, p, a, attempt, result):
    direction = attempt["direction"]
    expected = a["proposed"] if direction == "apply" else a["current"]
    if result.get("request_id") != attempt["id"] or result.get("status") != "applied" or result.get("request") != attempt["payload"]["request"]:
        raise ValueError("Server journal does not prove this exact request")
    event(store, sid, attempt["id"], write="succeeded", verification="pending", result=result)
    try:
        state = client.state(a["object_id"])
        inspect_state(p["destination"], state, a["url"])
        if state["token"] != result["after_token"] or state["preserved"] != a["before"]["preserved"]:
            raise ValueError("CMS content/metadata changed outside the requested field")
        if a.get("adapter") == ep.ADAPTER:
            ep.verify_raw(state, a, direction)
        else:
            if masked_content(state["content"], a["anchor"], expected) != masked_content(a["before"]["content"], a["anchor"], a["current"]):
                raise ValueError("Unrelated raw CMS content changed")
            matches = [h for h in state["headings"] if h["anchor"] == a["anchor"] and h["block_index"] == a["block_index"] and h["text"] == expected]
            if len(matches) != 1:
                raise ValueError("CMS heading identity changed")
        if render_action(client.public(a["url"]), a, expected) != a["rendered_baseline"]:
            raise ValueError("Rendered field, adjacent content or technical directives changed")
        status = "passed"
    except (ValueError, KeyError):
        status = "failed"
    event(store, sid, attempt["id"], write="succeeded", verification=status, result=result)
    # A crash here does not lose the server/app journal; avoid duplicate legacy receipts.
    existing = [r["payload"] for r in t.rows(store, "implementation_receipts", sid) if r["payload"]["attempt_id"] == attempt["id"]]
    if direction == "apply" and existing and existing[-1]["outcome"] == "attempted":
        receipt(store, sid, p, a, attempt["id"], "reported_applied", expected, "CMS write succeeded; public verification " + status)
    elif direction == "rollback":
        original = next(r for r in rows(store, sid, "cms_attempts") if r["review_id"] == attempt["review_id"] and r["action_id"] == a["action_id"] and r["direction"] == "apply")
        history = [r["payload"] for r in t.rows(store, "implementation_receipts", sid) if r["payload"]["attempt_id"] == original["id"]]
        if any(r["outcome"] == "reported_applied" for r in history) and not any(r["outcome"] == "rolled_back" for r in history):
            receipt(store, sid, p, a, original["id"], "rolled_back", expected, "Explicitly authorized CMS rollback; public verification " + status)
    return status


def render_action(source, action, expected):
    if action.get("adapter") == ep.ADAPTER:
        return ep.render(source, ep.action_mapping(action), expected)
    return rendered(source, action["anchor"], expected)


def execute(store, sid, rid, *, human_clicked, direction="apply", client_factory=WordPress):
    """Explicit apply/rollback only. A rerun never resends an existing attempt."""
    store.require_private_write()
    if human_clicked is not True or direction not in {"apply", "rollback"}:
        raise ValueError("Explicit human apply or rollback instruction required")
    with run_lock(workspace_lock(store.root)):
        review = record(store, sid, "cms_reviews", rid)
        auth = auth_for(store, sid, rid)
        p = validate_review(store, sid, review)
        if direction == "rollback" and not auth["payload"]["rollback"]:
            raise ValueError("Rollback was not explicitly authorized in this exact reviewed batch")
        with closing(client_factory(p["destination"])) as client:
            # Preflight the whole unattempted batch before any write; each action is checked again below.
            work = []
            key = cms_destination_key(p["destination"])
            attempts = [r for r in rows(store, sid, "cms_attempts") if r["destination_key"] == key]
            for a in p["actions"]:
                existing = next((r for r in attempts if r["action_id"] == a["action_id"] and r["revision"] == a["revision"] and r["direction"] == direction), None)
                if existing:
                    if latest_event(store, sid, existing["id"]).get("verification") != "passed":
                        raise ValueError("Existing attempt needs read-only reconciliation; duplicate writes are prohibited")
                    continue
                if direction == "apply":
                    check_action(store, sid, p, a)
                    token = a["before"]["token"]
                else:
                    original = next((r for r in attempts if r["review_id"] == rid and r["action_id"] == a["action_id"] and r["direction"] == "apply"), None)
                    if not original:
                        continue
                    result = latest_event(store, sid, original["id"])
                    if result.get("write") != "succeeded":
                        raise ValueError("Reconcile the original write before rollback")
                    token = result["result"]["after_token"]
                state = client.state(a["object_id"])
                inspect_state(p["destination"], state, a["url"])
                if state["token"] != token:
                    raise ValueError("CMS conflict: content changed since review/write; do not overwrite subsequent edits")
                work.append((a, token))
            for a, token in work:
                # Block a new revision on a page with any unresolved prior application request.
                for other in rows(store, sid, "cms_attempts"):
                    if other["destination_key"] == key and other["payload"].get("object_id") == a["object_id"] and latest_event(store, sid, other["id"]).get("write") == "uncertain":
                        raise ValueError("An earlier request on this page has an uncertain outcome")
                identity = new_id()
                body = {"request_id": identity, "instance": p["destination"]["instance"], "url": a["url"], "token": token,
                        **(dict(environment=p["destination"]["environment"], **ep.request_fields(a, direction)) if a.get("adapter") == ep.ADAPTER
                           else {"anchor": a["anchor"], "block_index": a["block_index"]}),
                        "current": a["current"] if direction == "apply" else a["proposed"],
                        "proposed": a["proposed"] if direction == "apply" else a["current"]}
                payload = {"object_id": a["object_id"], "request": body, "authorization_id": auth["id"]}
                with store.db() as db:
                    db.execute("INSERT INTO cms_attempts VALUES (?,?,?,?,?,?,?,?,?)", (identity, sid, rid, a["action_id"], a["revision"], direction, utc_now(), t.canonical(payload), key))
                attempt = record(store, sid, "cms_attempts", identity)
                sent = False
                try:
                    if direction == "apply":
                        receipt(store, sid, p, a, identity, "attempted")
                    # Serialize proposal mutations with final validation + network write. The durable
                    # attempt is already committed, so a crash rolls back no evidence of intent.
                    with store.db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        validate_review(store, sid, review)
                        if direction == "apply":
                            check_action(store, sid, p, a)
                        state = client.state(a["object_id"])
                        inspect_state(p["destination"], state, a["url"])
                        if state["token"] != token:
                            raise ValueError("CMS conflict")
                        if render_action(client.public(a["url"]), a, body["current"]) != a["rendered_baseline"]:
                            raise ValueError("Public content or directives changed since review")
                        sent = True
                        result = client.write(a["object_id"], body)
                    if verify(store, sid, client, p, a, attempt, result) != "passed":
                        break
                except Exception:
                    if latest_event(store, sid, identity).get("write") != "succeeded":
                        event(store, sid, identity, write="uncertain" if sent else "not_sent", verification="not_passed",
                              reason="Request interrupted, rejected, conflicted or unavailable. Read destination journal before further action.")
                    break
        return [r for r in rows(store, sid, "cms_attempts") if r["review_id"] == rid]


def reconcile(store, sid, attempt_id, *, client_factory=WordPress):
    """GET only, even after validation becomes stale or wording changes. Never retries a write."""
    store.require_private_write()
    with run_lock(workspace_lock(store.root)):
        attempt = record(store, sid, "cms_attempts", attempt_id)
        if attempt["payload"].get("history_only"):
            raise ValueError("Restored attempts are history; use separately configured read-only CMS inspection")
        p = record(store, sid, "cms_reviews", attempt["review_id"])["payload"]
        active = active_destination(store, sid, recovery=True)
        if cms_destination_key(active) != attempt["destination_key"]:
            raise ValueError("Destination changed; do not reconcile against another installation")
        a = next(v for v in p["actions"] if v["action_id"] == attempt["action_id"])
        # Credential rotation revokes writes, but cannot strand read-only recovery.
        with closing(client_factory({**active, "adapter": p["destination"].get("adapter", "core-heading/1")})) as client:
            result = client.operation(a["object_id"], attempt_id)
            if result.get("status") == "applied":
                return verify(store, sid, client, p, a, attempt, result)
            proven = proven_result(store, sid, attempt_id)
            if proven:
                event(store, sid, attempt_id, write="succeeded", verification="failed", result=proven,
                      reason="Previously committed write is proven locally, but its server journal is now missing. Authorization remains consumed; investigate the server restore or journal loss.")
                return "failed"
            event(store, sid, attempt_id, write="uncertain", verification="not_run",
                  reason="No committed server receipt. Absence is not proof of failure; do not resend or start another revision on this page.")
            return "uncertain"


def resume(store, sid, attempt_id, *, human_clicked, client_factory=WordPress):
    """Explicit retry of the SAME request, only after read-only server reconciliation.

    A delayed first request and this retry serialize on the server page row and
    share one unique request key. Neither can commit a second copy of the write.
    """
    store.require_private_write()
    if human_clicked is not True:
        raise ValueError("Explicit human resume instruction required")
    with run_lock(workspace_lock(store.root)):
        attempt = record(store, sid, "cms_attempts", attempt_id)
        if attempt["payload"].get("history_only"):
            raise ValueError("Restored requests cannot be resumed")
        review = record(store, sid, "cms_reviews", attempt["review_id"])
        p = validate_review(store, sid, review)
        auth = auth_for(store, sid, attempt["review_id"])
        if attempt["direction"] == "rollback" and not auth["payload"]["rollback"]:
            raise ValueError("Rollback was not authorized")
        a = next(v for v in p["actions"] if v["action_id"] == attempt["action_id"])
        body = attempt["payload"]["request"]
        with closing(client_factory(p["destination"])) as client:
            result = client.operation(a["object_id"], attempt_id)
            if result.get("status") == "applied":
                return verify(store, sid, client, p, a, attempt, result)
            if result.get("status") != "unknown":
                raise ValueError("Unknown server receipt format; do not retry")
            if proven_result(store, sid, attempt_id):
                raise ValueError("This request already succeeded; server journal loss cannot authorize publishing it again")
            if attempt["direction"] == "apply":
                check_action(store, sid, p, a)
                existing = [r for r in t.rows(store, "implementation_receipts", sid) if r["payload"]["attempt_id"] == attempt_id]
                if not existing:
                    receipt(store, sid, p, a, attempt_id, "attempted")
            with store.db() as db:
                db.execute("BEGIN IMMEDIATE")
                validate_review(store, sid, review)
                if attempt["direction"] == "apply":
                    check_action(store, sid, p, a)
                state = client.state(a["object_id"])
                inspect_state(p["destination"], state, a["url"])
                if state["token"] != body["token"] or render_action(client.public(a["url"]), a, body["current"]) != a["rendered_baseline"]:
                    raise ValueError("CMS/public conflict; this uncertain request cannot be resent")
                try:
                    result = client.write(a["object_id"], body)
                except Exception:
                    result = None
            if result is None:
                event(store, sid, attempt_id, write="uncertain", verification="not_run", reason="Same request retry unavailable; reconcile again")
                return "uncertain"
            return verify(store, sid, client, p, a, attempt, result)
