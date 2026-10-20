"""Site-scoped connection setup and versioned advisory evidence, never write authority."""
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .coordination import run_lock, workspace_lock
from .storage import checked_id, new_id, utc_now, config_hash, private_location
from .protection import require_protected
from .wordpress import destination_url
from .discovery_models import (Connection, AdministratorExport, MAX_BYTES, ISOLATION, HOST_EFFECTS,
                               canonical, parse, reject, safe_data, timestamp)
from .discovery_client import DiscoveryVault, DiscoveryReader, page_url

KINDS = {"public", "authenticated", "administrator_export", "mapping", "isolation_review", "publisher_host_review", "elementor_candidate"}
MAX_AGE = timedelta(hours=24)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def connections(store, sid):
    store.site(sid)
    with store.db() as db:
        return [{"id": r["id"], **json.loads(r["payload"])} for r in db.execute(
            "SELECT * FROM discovery_connections WHERE site_id=? ORDER BY rowid", (sid,))]


def connection(store, sid, cid):
    checked_id(cid)
    found = next((c for c in connections(store, sid) if c["id"] == cid), None)
    if found is None:
        raise ValueError("Discovery connection does not belong to the selected site")
    return found


def configure(store, sid, values, *, cid=None, username="", password="", vault=None):
    store.require_private_write()
    try:
        model = Connection.model_validate(values)
        safe_data(model.model_dump())
        destination_url(model.url, model.environment)
        page_url(model.url, model.url)
        p = urlsplit(model.url)
        if not p.hostname or "\\" in model.url or "%" in p.path or any(s in {".", ".."} for s in p.path.split("/")):
            reject()
        p.port  # Reject malformed ports before storing any reference.
        config = store.site(sid)
        if model.environment == "production" and model.url != config.url:
            reject()
        if model.environment != "production" and model.url == config.url:
            reject()
    except Exception:
        raise ValueError("Connection rejected: use the selected site's canonical production URL or a separate exact staging/local URL") from None
    with run_lock(workspace_lock(store.root)):
        old = connection(store, sid, cid) if cid else None
        if model.installation_id and any(
                other["id"] != cid and other["installation_id"] == model.installation_id
                and (other["environment"] != model.environment or other["url"] != model.url)
                for other in connections(store, sid)):
            raise ValueError("Separate environments/destinations require distinct independently obtained installation identities")
        identity = cid or new_id()
        credential = None
        if model.method == "wordpress_rest":
            # Retain credentials only on the identical destination/access configuration.
            same = old and all(old[k] == getattr(model, k) for k in ("url", "environment", "method", "installation_id"))
            if username or password:
                credential = new_id()
                (vault or DiscoveryVault()).write(credential, username, password)
            elif same and old.get("enabled") and old.get("credential_id"):
                credential = old["credential_id"]
            else:
                raise ValueError("Enter discovery credentials in the app to reconnect this exact destination")
        same_scope = old and all(old[k] == v for k, v in model.model_dump().items()) and old.get("enabled")
        payload = {**model.model_dump(), "credential_id": credential, "enabled": True,
                   "generation": old["generation"] if same_scope else new_id(), "configured": utc_now(),
                   "installation_certainty": "administrator_asserted" if model.installation_id else "unknown"}
        with store.db() as db:
            db.execute("INSERT INTO discovery_connections VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (identity, sid, canonical(payload)))
        return identity


def disconnect(store, sid, cid):
    store.require_private_write()
    with run_lock(workspace_lock(store.root)), store.db() as db:
        c = connection(store, sid, cid)
        c.pop("id")
        c.update(enabled=False, credential_id=None, generation=new_id())
        db.execute("UPDATE discovery_connections SET payload=? WHERE id=? AND site_id=?", (canonical(c), cid, sid))


def scope(store, sid, c):
    config = store.site(sid)
    return {"site_id": sid, "site_url": config.url, "profile_hash": config_hash(config),
            "connection_id": c["id"], "generation": c["generation"], "cms_url": c["url"],
            "environment": c["environment"], "installation_id": c["installation_id"]}


def active(store, sid, cid):
    c = connection(store, sid, cid)
    if not c.get("enabled"):
        raise ValueError("Reconnect the selected discovery environment before collecting fresh evidence")
    if (c["environment"] == "production") != (c["url"] == store.site(sid).url):
        raise ValueError("Discovery destination no longer matches the selected site/environment")
    destination_url(c["url"], c["environment"])
    page_url(c["url"], c["url"])
    return c


def records(store, sid, cid):
    connection(store, sid, cid)
    with store.db() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM discovery_evidence WHERE site_id=? AND connection_id=? ORDER BY version DESC", (sid, cid))]
    for row in rows:
        row["payload"] = json.loads(row["payload"])
        payload = row["payload"]
        if digest(payload["body"]) != payload["sha256"]:
            raise ValueError("Saved discovery evidence hash mismatch")
    return rows


def status(store, sid, cid, row):
    c = connection(store, sid, cid)
    body = row["payload"]["body"]
    if body.get("history_only") or not c.get("enabled") or body["scope"] != scope(store, sid, c):
        return "invalidated"
    if datetime.now(timezone.utc) - timestamp(body["observed_utc"]) > MAX_AGE:
        return "stale"
    if row["kind"] == "elementor_candidate":
        from .elementor_candidates import dependencies_current
        if not dependencies_current(store, sid, cid, body["data"]):
            return "invalidated"
    if row["kind"] in {"mapping", "isolation_review", "publisher_host_review"}:
        if row["kind"] == "isolation_review":
            production = [{k: p[k] for k in ("id", "generation", "installation_id")}
                          for p in connections(store, sid) if p["environment"] == "production" and p["enabled"]]
            if body["data"].get("production_identity_binding") != production:
                return "invalidated"
        deps = ({"public": body["data"]["public_evidence_id"], "administrator_export": body["data"]["administrator_evidence_id"]}
                if row["kind"] == "mapping" else {"administrator_export": body["data"]["evidence_id"]})
        if row["kind"] == "publisher_host_review":
            deps["public"] = body["data"]["public_evidence_id"]
            # Bind even the absence of REST evidence. A newly collected record,
            # replacement or expiry requires a fresh independent human review.
            if "authenticated_evidence_id" not in body["data"]:
                return "invalidated"
            auth = latest(store, sid, cid, "authenticated", current=False)
            if auth and auth["payload"]["body"]["scope"] != body["scope"]:
                auth = None
            if auth and status(store, sid, cid, auth) != "current":
                return "invalidated"
            if body["data"]["authenticated_evidence_id"] != (auth["id"] if auth else None):
                return "invalidated"
        for kind, eid in deps.items():
            parent = latest(store, sid, cid, kind)
            if not parent or parent["id"] != eid:
                return "invalidated"
    return "current"


def latest(store, sid, cid, kind, *, current=True):
    row = next((r for r in records(store, sid, cid) if r["kind"] == kind), None)
    return row if row and (not current or status(store, sid, cid, row) == "current") else None


def attempts(store, sid, cid):
    connection(store, sid, cid)
    with store.db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM discovery_attempts WHERE site_id=? AND connection_id=? ORDER BY rowid DESC LIMIT 30", (sid, cid))]


def _start(store, sid, c, kind):
    aid = new_id()
    c.setdefault("_collection_scope", scope(store, sid, c))
    with store.db() as db:
        db.execute("INSERT INTO discovery_attempts VALUES (?,?,?,?,?,?,?,?)", (aid, sid, c["id"], kind, utc_now(), None, "running", canonical(c["_collection_scope"])))
    return aid


def _finish(store, aid, outcome):
    with store.db() as db:
        db.execute("UPDATE discovery_attempts SET finished=?,status=? WHERE id=?", (utc_now(), outcome, aid))


def _save(store, sid, c, kind, data, *, observed=None, source="", certainty="confirmed", source_sha256=""):
    if kind not in KINDS:
        reject()
    data = parse(canonical(data))
    safe_data(data)
    bound_scope = c.get("_collection_scope", scope(store, sid, c))
    body = {"schema_version": 1, "scope": bound_scope, "observed_utc": observed or utc_now(),
            "source": source, "source_sha256": source_sha256, "certainty": certainty, "data": data}
    if len(canonical(body).encode()) > 8 * MAX_BYTES:
        reject()
    eid = new_id()
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT config_hash FROM sites WHERE id=?", (sid,)).fetchone()[0] != bound_scope["profile_hash"]:
            raise ValueError("Site profile changed during discovery; refresh using the current configuration")
        version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM discovery_evidence WHERE connection_id=?", (c["id"],)).fetchone()[0]
        db.execute("INSERT INTO discovery_evidence VALUES (?,?,?,?,?,?,?)", (eid, sid, c["id"], version, kind, utc_now(), canonical({"body": body, "sha256": digest(body)})))
    # Save the advisory result as it stood then. Consumers always recalculate freshness.
    report = compatibility(store, sid, c["id"])
    if report["scope"] != bound_scope:
        report = {"scope": bound_scope, "publishing_compatible": False,
                  "blockers": ["Site profile changed after collection; this historical result is invalidated"]}
    with store.db() as db:
        db.execute("UPDATE discovery_evidence SET payload=? WHERE id=?", (canonical({"body": body, "sha256": digest(body), "compatibility_at_collection": report}), eid))
    return eid


def refresh(store, sid, cid, page_ids=(), *, client_factory=DiscoveryReader):
    store.require_private_write()
    if (len(page_ids) > 10 or len(set(page_ids)) != len(page_ids)
            or any(type(n) is not int or n < 1 or n > 2147483647 for n in page_ids)):
        raise ValueError("Choose at most ten distinct positive page IDs")
    with run_lock(workspace_lock(store.root)):
        c = active(store, sid, cid)
        results, client = [], None
        # Persist failures even if the credential store/client cannot be opened.
        aid = _start(store, sid, c, "public")
        try:
            client = client_factory(c)
            data = client.public(page_ids)
            results.append(_save(store, sid, c, "public", data, source="WordPress public HTML and REST view; clues are inferred"))
            _finish(store, aid, "success")
        except Exception:
            _finish(store, aid, "failed")
            if client:
                client.close()
            raise ValueError("Discovery refresh failed. Previous successful evidence is preserved with its original age") from None
        try:
            if c["method"] == "wordpress_rest":
                aid = _start(store, sid, c, "authenticated")
                try:
                    data = client.authenticated(page_ids)
                    results.append(_save(store, sid, c, "authenticated", data, source="Authenticated WordPress REST GET (current account permissions)"))
                    _finish(store, aid, "partial" if data.get("missing") else "success")
                except Exception:
                    _finish(store, aid, "failed")
                    raise ValueError("Authenticated discovery failed. Public evidence and earlier successful inventory are preserved") from None
        finally:
            client.close()
        return results


def _protected_input(path):
    path = private_location(Path(path))
    require_protected(path.parent)
    if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > MAX_BYTES:
        reject()
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        reject()
    return raw


def validate_export(raw, store, sid, c):
    try:
        value = parse(raw)
        safe_data(value)
        bundle = AdministratorExport.model_validate(value)
        expected = scope(store, sid, c)
        if not c["installation_id"]:
            reject()
        for key in ("site_id", "site_url", "profile_hash", "cms_url", "environment", "installation_id"):
            if getattr(bundle, key) != expected[key]:
                reject()
        timestamp(bundle.collected_utc)
        if len({p.id for p in bundle.pages}) != len(bundle.pages) or len({p.url for p in bundle.pages}) != len(bundle.pages):
            reject()
        if len({(s.kind, s.name) for s in bundle.software}) != len(bundle.software):
            reject()
        roles = [s.table_role for s in bundle.software if s.table_role is not None]
        if len(set(roles)) != len(roles) or any(s.table_role is not None and s.kind != "table_engine" for s in bundle.software):
            reject()
        if len({h.area for h in bundle.host}) != len(bundle.host):
            reject()
        rows = set()
        for page in bundle.pages:
            page_url(c["url"], page.url)
            if any(type(n) is not int or n < 1 for n in page.shared_ids):
                reject()
            if len({m.key for m in page.metadata}) != len(page.metadata):
                reject()
            for meta in page.metadata:
                if meta.row_id in rows:
                    reject()
                rows.add(meta.row_id)
                if meta.key in {"_elementor_data", "_elementor_page_settings"}:
                    safe_data(parse(meta.value))
        return bundle.model_dump()
    except Exception:
        reject()


def import_evidence(store, sid, cid, path):
    store.require_private_write()
    with run_lock(workspace_lock(store.root)):
        c = active(store, sid, cid)
        aid = _start(store, sid, c, "administrator_export")
        try:
            raw = _protected_input(path)
            value = validate_export(raw, store, sid, c)
            eid = _save(store, sid, c, "administrator_export", value, observed=value["collected_utc"],
                        source=value["source_reference"], certainty="administrator_asserted", source_sha256=hashlib.sha256(raw).hexdigest())
            _finish(store, aid, "success")
            return eid
        except Exception:
            _finish(store, aid, "failed")
            raise ValueError("Protected import rejected. Check schema, exact site/profile/environment/installation, dates and excluded sensitive data") from None


def export_template(store, sid, cid):
    c = connection(store, sid, cid)
    s = scope(store, sid, c)
    return {"schema_version": 1, **{k: s[k] for k in ("site_id", "site_url", "profile_hash", "cms_url", "environment", "installation_id")},
            "collected_utc": utc_now(), "source_reference": "Replace with administrator evidence reference",
            "software": [], "complete_inventory": [], "pages": [], "host": []}


def export_file(store, sid, cid, path, *, template=False):
    store.require_private_write()
    with run_lock(workspace_lock(store.root)):
        connection(store, sid, cid)
        path = private_location(Path(path))
        require_protected(path.parent)
        if path.suffix.lower() != ".json":
            reject()
        value = export_template(store, sid, cid) if template else {
            "format": "cms-discovery-history/1", "history_only": True,
            "evidence": records(store, sid, cid), "compatibility": compatibility(store, sid, cid)}
        raw = canonical(value).encode()
        if len(raw) > 20 * MAX_BYTES:
            raise ValueError("Discovery history export exceeds limit")
        # Explicit local protected export, no browser download of private host evidence.
        with path.open("xb") as handle:
            handle.write(raw)
        return path


def compatibility(store, sid, cid):
    from .publisher_preflight import inspect_inventory
    c = connection(store, sid, cid)
    rows = records(store, sid, cid)
    current = {}
    for row in rows:
        if row["kind"] not in current:
            current[row["kind"]] = row if status(store, sid, cid, row) == "current" else None
    def data(kind):
        return current[kind]["payload"]["body"]["data"] if current.get(kind) else {}
    confirmed, inferred, asserted, missing = [], [], [], []
    public, auth, admin = data("public"), data("authenticated"), data("administrator_export")
    for p in public.get("pages", []):
        confirmed.append(f"Public REST page {p['id']}: {p['url']} · template {p['template'] or '(default)'}")
    inferred.extend(f"{x['kind']}: {x['value']} (public clue only)" for x in public.get("clues", []))
    for s in auth.get("software", []):
        confirmed.append(f"REST {s['kind']}: {s['name']} {s['version']} · active={s['active']}")
    for p in auth.get("pages", []):
        confirmed.append(f"Authenticated page {p['id']}: raw content/excerpt {'available' if p.get('raw_content') is not None and p.get('raw_excerpt') is not None else 'incomplete'}")
    for s in admin.get("software", []):
        asserted.append(f"Administrator {s['kind']}: {s['name']} {s['version']} · active={s['active']}")
    for item in ("core", "php", "database", "table_engine", "theme", "plugin", "mu_plugin", "dropin"):
        known = [s for s in admin.get("software", []) if s["kind"] == item]
        if (item not in admin.get("complete_inventory", [])
                or item in {"core", "php", "database", "table_engine", "theme"} and not known):
            missing.append("Complete " + item + " inventory")
        elif any(not s["version"] for s in known if item != "table_engine"):
            missing.append(item + " versions")
    for item in HOST_EFFECTS:
        if not any(h["area"] == item and h["result"] == "observed" for h in admin.get("host", [])):
            missing.append("Host " + item + " evidence")
    if not c["installation_id"]:
        missing.append("Independent installation identity")
    if not admin.get("pages"):
        missing.append("Administrator page/template/raw excerpt/metadata row and shared reference evidence")
    missing += public.get("missing", []) + auth.get("missing", [])
    isolation = isolation_status(store, sid, cid, current)
    blocker = "Discovery alone does not certify a writable installation. A matching pinned publisher endpoint and fresh host/staging validation are required."
    has_elementor = any("elementor" in s["name"].lower() for s in admin.get("software", []) + auth.get("software", [])) or any("elementor" in x["value"].lower() for x in public.get("clues", []))
    blockers = [blocker]
    for s in auth.get("software", []) + admin.get("software", []):
        if not has_elementor and s["active"] is True and ((s["kind"] == "plugin" and s["name"] != "local-seo-publisher/local-seo-publisher.php")
                                    or s["kind"] == "theme" and s["name"] != "twentytwentyfive"
                                    or s["kind"] in {"mu_plugin", "dropin"}):
            blockers.append(f"Recorded active {s['kind']} {s['name']} is outside the version 1 core-heading contract (see source certainty).")
    if has_elementor:
        blockers.append("Elementor mapping alone cannot enable publication. The separate pinned canvas-heading adapter requires matching fresh runtime and independently reviewed host/staging evidence; other stacks remain unsupported.")
    if not public:
        blockers.append("Refresh current public REST identities before cross-checking any imported page mapping.")
    pinned = inspect_inventory(admin, authenticated=auth)
    if has_elementor:
        blockers.extend(pinned["conflicts"])
    return {"schema_version": 1, "scope": scope(store, sid, c), "evaluated_utc": utc_now(),
            "publishing_compatible": False, "confirmed": confirmed, "inferred": inferred,
            "administrator_asserted": asserted, "missing": missing,
            "stale_or_invalidated": [{"id": r["id"], "version": r["version"], "kind": r["kind"], "status": status(store, sid, cid, r)} for r in rows if status(store, sid, cid, r) != "current"],
            "blockers": blockers, "staging": isolation, "elementor_preflight": pinned, "elementor_detected": has_elementor,
            "supported_combinations": [{"adapter": "core-heading/1", "validated_fixture": "WordPress 7.1.3 / PHP 8.3 / MariaDB 11.4 / Twenty Twenty-Five",
                "requirements": "Only the publisher companion active; no MU/drop-ins/multisite/custom/shared templates; flat core blocks, unique explicit heading anchor and explicit excerpt. Fresh server checks and host validation required.",
                "installation_status": "not_certified_by_discovery"}, {"adapter": "elementor-heading/1", "installation_status": "requires_separate_certified_endpoint_and_host_review",
                "requirements": "Pinned Elementor 3.31.3 canvas/static heading fixture only. No shared/dynamic widgets, custom settings, SEO/cache plugins or unverified host effects. See docs/elementor-publishing.md."}],
            "next_steps": ["Refresh selected page IDs; import sanitized administrator evidence for missing facts.",
                           "Independently review host isolation evidence; unknown isolation keeps work local.",
                           "Use separate exact publication review and approvals only for a supported certified adapter."],
            "evidence_ids": [r["id"] for r in current.values() if r]}


def isolation_status(store, sid, cid, current=None):
    c = connection(store, sid, cid)
    row = latest(store, sid, cid, "administrator_export") if current is None else current.get("administrator_export")
    review = latest(store, sid, cid, "isolation_review") if current is None else current.get("isolation_review")
    facts = row["payload"]["body"]["data"].get("host", []) if row else []
    production = [p for p in connections(store, sid) if p["environment"] == "production" and p["enabled"]]
    production_ids = {p["installation_id"] for p in production}
    identity_binding = [{k: p[k] for k in ("id", "generation", "installation_id")} for p in production]
    valid, missing = [], []
    for area in ISOLATION:
        f = next((h for h in facts if h["area"] == area), None)
        # Distinct concrete resource IDs plus an observation and external reference.
        ok = (f and f["result"] == "isolated" and len(f["observation"].strip()) >= 20
              and len(f["source_reference"].strip()) >= 5 and f["production_resource"].strip()
              and f["environment_resource"].strip() and f["production_resource"] != f["environment_resource"])
        if area == "installation_identity":
            ok = (ok and len(production_ids) == 1 and "" not in production_ids and c["installation_id"]
                  and c["installation_id"] not in production_ids and f["production_resource"] in production_ids
                  and f["environment_resource"] == c["installation_id"])
        (valid if ok else missing).append(area)
    verified = bool(c["environment"] != "production" and not missing and review and row
                    and review["payload"]["body"]["data"]["evidence_id"] == row["id"]
                    and review["payload"]["body"]["data"].get("production_identity_binding") == identity_binding)
    return {"status": "human_reviewed_isolation" if verified else "unknown_keep_work_local", "supported_conditions": valid,
            "missing_or_unverified": missing, "evidence_id": row["id"] if row else None,
            "production_identity_binding": identity_binding,
            "note": "Imported claims require independent human host review. This record never enables publishing or creates approval."}


def review_isolation(store, sid, cid, *, human_clicked, source):
    store.require_private_write()
    with run_lock(workspace_lock(store.root)):
        c = active(store, sid, cid)
        c["_collection_scope"] = scope(store, sid, c)
        state = isolation_status(store, sid, cid)
        if human_clicked is not True or c["environment"] == "production" or state["missing_or_unverified"] or len(source.strip()) < 10 or len(source) > 300:
            raise ValueError("Every isolation condition needs current concrete resource evidence and independent human review")
        return _save(store, sid, c, "isolation_review", {"evidence_id": state["evidence_id"], "human_review_source": source,
                     "production_identity_binding": state["production_identity_binding"]},
                     source="Human review of host evidence", certainty="human_reviewed")


def prepare_mapping(store, sid, cid, page_id, element_id, proposed):
    """Cross-check an imported metadata row against independent REST and rendering.

    Metadata row identity remains administrator-asserted, not verified by HTML.
    Never emits a publisher mapping or an executable review/authorization.
    """
    from .elementor import map_heading, bind_rendered_heading, preview_heading
    store.require_private_write()
    with run_lock(workspace_lock(store.root)):
        c = active(store, sid, cid)
        c["_collection_scope"] = scope(store, sid, c)
        public, admin = latest(store, sid, cid, "public"), latest(store, sid, cid, "administrator_export")
        if not public or not admin:
            raise ValueError("Current independently collected REST/rendered evidence and administrator metadata are required")
        pd, ad = (r["payload"]["body"]["data"] for r in (public, admin))
        page = next((p for p in ad["pages"] if p["id"] == page_id and p["type"] == "page"), None)
        rest = next((p for p in pd["pages"] if p["id"] == page_id), None)
        capture = next((p for p in pd["captures"] if p["page_id"] == page_id), None)
        if (not page or not rest or not capture or page["url"] != rest["url"] or page["url"] != capture["url"]
                or page["template"] != rest["template"] or page["shared_ids"] or page["raw_excerpt"] is None):
            raise ValueError("CMS page identity/template/excerpt or shared references cannot be independently reconciled")
        meta = [m for m in page["metadata"] if m["key"] == "_elementor_data"]
        if len(meta) != 1:
            raise ValueError("One exact administrator-sourced Elementor metadata row is required")
        mapping = map_heading(meta[0]["value"], page_id=page_id, element_id=element_id)
        result = bind_rendered_heading(capture["html"], mapping)
        candidate = preview_heading(meta[0]["value"], mapping, proposed)
        return _save(store, sid, c, "mapping", {"mapping": asdict(mapping), "metadata_row_id": meta[0]["row_id"],
            "metadata_identity_certainty": "administrator_asserted", "public_evidence_id": public["id"], "administrator_evidence_id": admin["id"],
            "render_check": result, "candidate": candidate, "publishing_compatible": False},
            observed=min(public["payload"]["body"]["observed_utc"], admin["payload"]["body"]["observed_utc"]),
            source="Offline cross-check of REST page, administrator metadata and public rendered widget", certainty="cross_checked_not_certified")


def sanitize_backup(db):
    """Called on backup copy AND restore. Preserve journals, detach active access."""
    for cid, raw in db.execute("SELECT id,payload FROM discovery_connections").fetchall():
        c = json.loads(raw)
        c.update(enabled=False, credential_id=None, generation=new_id())
        db.execute("UPDATE discovery_connections SET payload=? WHERE id=?", (canonical(c), cid))
    for eid, raw in db.execute("SELECT id,payload FROM discovery_evidence").fetchall():
        payload = json.loads(raw)
        if digest(payload["body"]) != payload["sha256"]:
            raise ValueError("Invalid discovery backup evidence hash")
        payload["body"]["history_only"] = True
        payload["sha256"] = digest(payload["body"])
        db.execute("UPDATE discovery_evidence SET payload=? WHERE id=?", (canonical(payload), eid))


def validate_restored(store):
    with store.db() as db:
        sanitize_backup(db)
    for site in store.sites():
        sid = site["id"]
        for c in connections(store, sid):
            try:
                checked_id(c["id"])
                Connection.model_validate({k: c[k] for k in Connection.model_fields})
                destination_url(c["url"], c["environment"])
                for r in records(store, sid, c["id"]):
                    b = r["payload"]["body"]
                    if r["kind"] not in KINDS or b["scope"]["site_id"] != sid or b["scope"]["connection_id"] != c["id"]:
                        reject()
                    timestamp(b["observed_utc"])
                    safe_data(b["data"])
            except Exception:
                raise ValueError("Invalid inert discovery backup history") from None
