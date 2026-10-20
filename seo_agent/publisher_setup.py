"""Bind publication to existing discovery evidence and separate host review.

Imported assertions alone never establish installation or staging compatibility.
Server evidence independently checks runtime identities; host facts remain an
explicit, dated human review of external provider records.
"""
from datetime import datetime, timezone, timedelta
import hashlib
from pathlib import Path
import io
import zipfile

from . import discovery as d
from .coordination import run_lock, workspace_lock
from .storage import utc_now
from .elementor_publishing import ADAPTER, CONTRACT, contract_manifest
from .publisher_preflight import inspect_inventory

HOST_CONDITIONS = (
    "No page cache, CDN HTML cache or persistent object cache; no hidden cache invalidation is needed.",
    "Host deployment is frozen during each publication; core/theme/plugin/configuration files cannot change during the transaction.",
    "No production synchronization, webhooks, external save jobs or customer messages are triggered by these scoped writes or verification GETs.",
    "The exact pinned mirror, generated assets, experiments, wp-config hash/bootstrap behavior and bypassed save lifecycle were independently checked against provider/CMS records.",
)


def host_requirements(store, sid, cid):
    c = d.active(store, sid, cid)
    admin, public = d.latest(store, sid, cid, "administrator_export"), d.latest(store, sid, cid, "public")
    if c["provider"].strip().casefold() in {"unknown", ""} or not c["installation_id"] or not admin or not public:
        raise ValueError("Identify the actual provider and installation; collect fresh public and protected administrator evidence first")
    data = admin["payload"]["body"]["data"]
    if set(data["complete_inventory"]) != {"core", "php", "database", "table_engine", "theme", "plugin", "mu_plugin", "dropin"}:
        raise ValueError("Complete versioned software, MU-plugin, drop-in and table-engine inventory is required")
    preflight = inspect_inventory(data, phase="installed")
    if preflight["missing"] or preflight["conflicts"]:
        raise ValueError("Pinned Elementor inventory is incomplete or incompatible: " +
                         "; ".join(preflight["conflicts"] + preflight["missing"]))
    facts = {h["area"]: h for h in data["host"]}
    for area in (*d.HOST_EFFECTS, "deployment", "no_sync", "no_jobs_webhooks", "no_customer_messages"):
        fact = facts.get(area)
        if (not fact or fact["result"] not in {"observed", "isolated"}
                or len(fact["observation"].strip()) < 20 or len(fact["source_reference"].strip()) < 5):
            raise ValueError("Missing concrete host evidence for " + area)
    return c, admin, public


def review_host(store, sid, cid, *, human_clicked, source, conditions):
    store.require_private_write()
    if human_clicked is not True or conditions != list(HOST_CONDITIONS) or not 10 <= len(source.strip()) <= 300:
        raise ValueError("Independent human review of every exact host effect condition and its source is required")
    with run_lock(workspace_lock(store.root)):
        c, admin, public = host_requirements(store, sid, cid)
        return d._save(store, sid, c, "publisher_host_review", {
            "evidence_id": admin["id"], "public_evidence_id": public["id"], "human_review_source": source,
            "contract": CONTRACT, "conditions": list(HOST_CONDITIONS)},
            source="Independent human review of provider/CMS records", certainty="human_reviewed")


def evidence_binding(store, sid, *, url, instance, environment, adapter, discovery_id):
    # Loopback can be a tunnel/proxy to production. An address is not isolation.
    if not discovery_id:
        if environment == "production" and adapter == "core-heading/1":
            return None  # Existing core protocol; no new Elementor authority implied.
        raise ValueError("Select the exact Hosting & CMS discovery environment with current reviewed evidence")
    c = d.active(store, sid, discovery_id)
    if (c["url"], c["installation_id"], c["environment"]) != (url, instance, environment):
        raise ValueError("Publication destination differs from the selected discovery installation")
    result = {"scope": d.scope(store, sid, c)}
    if environment in {"staging", "local"}:
        isolation = d.isolation_status(store, sid, discovery_id)
        if isolation["status"] != "human_reviewed_isolation":
            raise ValueError("Staging isolation lacks fresh independent host review; keep work local")
        result["isolation"] = isolation
        result["isolation_review_id"] = d.latest(store, sid, discovery_id, "isolation_review")["id"]
    if adapter == ADAPTER:
        _, admin, public = host_requirements(store, sid, discovery_id)
        review = d.latest(store, sid, discovery_id, "publisher_host_review")
        if not review:
            raise ValueError("Review the pinned adapter's exact host effect conditions in Hosting & CMS")
        result.update(administrator_evidence_id=admin["id"], public_evidence_id=public["id"], host_review_id=review["id"])
    return result


def validate_binding(store, sid, destination):
    old = destination.get("discovery_binding")
    cid = old["scope"]["connection_id"] if old else None
    actual = evidence_binding(store, sid, url=destination["url"], instance=destination["instance"],
                              environment=destination["environment"], adapter=destination.get("adapter", "core-heading/1"), discovery_id=cid)
    if actual != old:
        raise ValueError("Hosting/staging evidence changed; reconfigure and prepare a fresh CMS review")


def validate_installation(store, sid, destination, state):
    binding = destination["discovery_binding"]
    cid = binding["scope"]["connection_id"]
    admin = d.latest(store, sid, cid, "administrator_export")["payload"]["body"]["data"]
    public = d.latest(store, sid, cid, "public")["payload"]["body"]["data"]
    page = next((p for p in admin["pages"] if p["id"] == state["id"]), None)
    rest = next((p for p in public["pages"] if p["id"] == state["id"]), None)
    if (not page or not rest or page["url"] != state["url"] or rest["url"] != state["url"]
            or page["template"] != state["template"] or rest["template"] != state["template"]
            or page["raw_content"] != state["content"] or page["raw_excerpt"] != state["excerpt"] or page["shared_ids"]):
        raise ValueError("Administrator/REST page, template, mirror or excerpt conflicts with fresh independent adapter evidence")
    rows = [m for m in page["metadata"] if m["key"] == "_elementor_data"]
    if len(rows) != 1 or rows[0]["row_id"] != state["metadata_row_id"] or rows[0]["value"] != state["elementor_data"]:
        raise ValueError("Administrator metadata row/source differs from independent adapter evidence")
    inv = state["inventory"]
    software = {(s["kind"], s["name"]): s for s in admin["software"]}
    required = [("core", "WordPress", inv["wordpress"], inv["core_includes_php"]),
                ("theme", inv["theme"], contract_manifest()["theme_version"], inv["theme_files"]),
                ("plugin", "elementor/elementor.php", inv["elementor"], inv["elementor_files"]),
                ("plugin", "local-seo-publisher/local-seo-publisher.php", "0.2.0", inv["adapter_hash"])]
    for kind, name, version, sha in required:
        s = software.get((kind, name))
        if not s or s["version"] != version or s["sha256"] != sha or (kind in {"theme", "plugin"} and s["active"] is not True):
            raise ValueError("Imported runtime version/hash differs from the certified endpoint: " + kind + " " + name)
    for kind, expected in (("php", inv["php"]), ("database", inv["database"])):
        if not any(s["kind"] == kind and s["version"] == expected for s in admin["software"]):
            raise ValueError("Imported " + kind + " version differs from fresh runtime evidence")
    if any(s["kind"] in {"mu_plugin", "dropin"} or
           s["kind"] == "plugin" and s["active"] and s["name"] not in inv["plugins"] for s in admin["software"]):
        raise ValueError("Conflicting active plugin, MU-plugin or drop-in inventory")


def staging_proof(store, sid, destination, frozen, state, *, mapping=None):
    if destination["environment"] != "production":
        return None
    from . import publishing as p
    for attempt in reversed(p.rows(store, sid, "cms_attempts")):
        if (attempt["direction"] != "apply" or attempt["payload"].get("history_only")
                or attempt["action_id"] != frozen["action_id"] or attempt["revision"] != frozen["revision"]):
            continue
        review = p.record(store, sid, "cms_reviews", attempt["review_id"])["payload"]
        if review.get("history_only") or review["destination"]["environment"] not in {"staging", "local"}:
            continue
        a = next((a for a in review["actions"] if a["action_id"] == frozen["action_id"] and a["revision"] == frozen["revision"]), None)
        event = p.latest_event(store, sid, attempt["id"])
        if (a and a.get("adapter") == ADAPTER and a["current"] == frozen["action"]["current"] and a["proposed"] == frozen["action"]["proposed"]
                and all(a["before"][k] == state[k] for k in ("contract_hash", "elementor_data", "content", "excerpt", "template"))
                and event.get("write") == "succeeded" and event.get("verification") == "passed"):
            proof = {"attempt_id": attempt["id"], "review_id": attempt["review_id"], "destination": review["destination"],
                     "action_id": attempt["action_id"], "revision": attempt["revision"],
                     "request": attempt["payload"]["request"], "verified_utc": event["result"]["written_utc"],
                     "contract_hash": state["contract_hash"]}
            proof["destination"] = {k: v for k, v in proof["destination"].items() if k != "credential_id"}
            validate_staging_proof(store, sid, destination, {"staging_validation": proof,
                "action_id": frozen["action_id"], "revision": frozen["revision"],
                "current": frozen["action"]["current"], "proposed": frozen["action"]["proposed"],
                "before": state, "mapping": mapping})
            return proof
    raise ValueError("Production requires a successful verified staging Apply of this exact action revision on the matching certified stack")


def validate_staging_proof(store, sid, destination, action):
    if destination["environment"] != "production":
        return
    from . import publishing as p, elementor_publishing as ep
    proof = action.get("staging_validation")
    if not proof or datetime.now(timezone.utc) - d.timestamp(proof["verified_utc"]) > timedelta(hours=24):
        raise ValueError("Fresh matching staging verification is required before production review/apply")
    validate_binding(store, sid, proof["destination"])
    attempt = p.record(store, sid, "cms_attempts", proof["attempt_id"])
    review = p.record(store, sid, "cms_reviews", proof["review_id"])["payload"]
    redacted = {k: v for k, v in review["destination"].items() if k != "credential_id"}
    if (review.get("history_only") or review["fingerprint"] != p.t.digest({k: v for k, v in review.items() if k != "fingerprint"})
            or redacted != proof["destination"] or redacted["environment"] not in {"staging", "local"}
            or redacted.get("adapter") != ADAPTER or len(review["actions"]) != 1
            or attempt["destination_key"] != p.cms_destination_key(redacted)):
        raise ValueError("Staging proof destination/review lineage is invalid")
    if (attempt["payload"].get("history_only") or attempt["direction"] != "apply"
            or attempt["review_id"] != proof["review_id"] or attempt["action_id"] != proof["action_id"]
            or attempt["revision"] != proof["revision"] or attempt["payload"]["request"] != proof["request"]
            or action.get("action_id", proof["action_id"]) != proof["action_id"]
            or action.get("revision", proof["revision"]) != proof["revision"]):
        raise ValueError("Staging proof does not bind this exact action/revision/request")
    staged = review["actions"][0]
    auth = p.record(store, sid, "cms_authorizations", attempt["payload"]["authorization_id"])
    batch, approved = p.approval(store, sid, review["batch_id"])
    if (auth["payload"].get("history_only") or auth["review_id"] != proof["review_id"]
            or auth["payload"]["fingerprint"] != review["fingerprint"]
            or approved["id"] != review["approval_id"] or batch["payload"]["fingerprint"] != review["batch_fingerprint"]
            or staged["action_id"] != action.get("action_id") or staged["revision"] != action.get("revision")
            or staged.get("adapter") != ADAPTER or attempt["payload"]["object_id"] != staged["object_id"]
            or any(staged[k] != action.get(k) for k in ("current", "proposed"))
            or any(staged["before"][k] != action.get("before", {}).get(k)
                   for k in ("contract_hash", "elementor_data", "content", "excerpt", "template"))
            or proof["contract_hash"] != staged["before"]["contract_hash"]):
        raise ValueError("Staging validation does not match the approved action and certified source")
    if (not action.get("mapping") or any(d.canonical(staged["mapping"][k]) != d.canonical(action["mapping"].get(k))
            for k in ("element_id", "ancestor_ids", "path", "tag", "current", "source_sha256"))):
        raise ValueError("Staging validation targets a different widget/path")
    expected_request = {"request_id": attempt["id"], "instance": redacted["instance"], "url": staged["url"],
                        "token": staged["before"]["token"], "environment": redacted["environment"],
                        **ep.request_fields(staged, "apply"), "current": staged["current"], "proposed": staged["proposed"]}
    if proof["request"] != expected_request:
        raise ValueError("Staging request differs from the exact authorized write")
    event = p.latest_event(store, sid, proof["attempt_id"])
    if (event.get("write") != "succeeded" or event.get("verification") != "passed"
            or event.get("result", {}).get("request") != proof["request"]
            or event.get("result", {}).get("request_id") != proof["attempt_id"]
            or event.get("result", {}).get("status") != "applied"
            or event.get("result", {}).get("before_token") != staged["before"]["token"]
            or event.get("result", {}).get("written_utc") != proof["verified_utc"]):
        raise ValueError("Staging verification is no longer successful")


def package_bytes():
    """Reproducible install archive containing only the reviewed companion files."""
    base = Path(__file__).resolve().parent.parent / "wordpress/local-seo-publisher"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("elementor-contract.json", "elementor-publisher.php", "local-seo-publisher.php"):
            info = zipfile.ZipInfo("local-seo-publisher/" + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (base / name).read_bytes())
    return stream.getvalue()


def setup_packet(store, sid, cid=None):
    """Concrete inert package inventory. No installer or approval is invoked."""
    base = Path(__file__).resolve().parent.parent / "wordpress/local-seo-publisher"
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.iterdir()) if p.is_file()}
    c = d.connection(store, sid, cid) if cid else None
    report = d.compatibility(store, sid, cid) if c else None
    return {"schema": "publisher-setup/1", "history_only": True, "site_id": sid, "created_utc": utc_now(),
        "destination": c["url"] if c else store.site(sid).url, "environment": c["environment"] if c else "production",
        "provider": c["provider"] if c else "Unknown", "installation_id": c["installation_id"] if c else "Unknown",
        "package": "Local SEO Exact Heading Publisher 0.2.0", "package_sha256": hashlib.sha256(package_bytes()).hexdigest(),
        "files": files, "contract": contract_manifest(),
        "action": "Separately approve installing these exact files under wp-content/plugins/local-seo-publisher and activating the companion only after host compatibility is independently established.",
        "effects": ["Activation creates the InnoDB lseo_operations journal table and lseo_publisher role (read, lseo_publish_heading).",
                    "Separate exact setup action: dedicated user/application password; protected LSEO_INSTANCE, LSEO_ENVIRONMENT, LSEO_USER_ID, LSEO_PAGE_IDS and LSEO_ELEMENTOR_CONTRACT constants.",
                    "Do not change the existing theme, plugins, excerpts, cache settings or templates to fit this fixture certificate.",
                    "No whole-site deployment, staging database copy, DNS change or content publication is included."],
        "validation": "Verify backups, package hashes, exact allowlists, stock pinned runtime, minimal-account denial of core REST writes and read-only adapter checks; then separately validate isolated staging.",
        "recovery": "Before setup capture protected database/files/configuration baseline. On failure deactivate/remove only these new files, restore the prior constants and revoke only the new credential/account/role if unused. Retain the operation journal for reconciliation; never drop it to enable retries.",
        "blockers": ["Provider/account and installation evidence required"] if not report else list(dict.fromkeys(
            report["missing"] + report["blockers"] + report["elementor_preflight"]["missing"] +
            ["Administrator assertion: " + item for item in report["elementor_preflight"]["conflicts"]])),
        "inventory_preflight": report["elementor_preflight"] if report else None,
        "approval": "This is a review packet, not permission. No setup execution is provided by the app."}


def readiness(store, sid):
    from . import publishing as p
    connections = d.connections(store, sid)
    result = {"level": "local_preparation", "publishing_compatible": False,
              "next_action": "In Hosting & CMS, save the actual hosting provider, canonical production URL and existing authorized read access. Enter passwords only in the app password control.",
              "blockers": [], "mapped": False, "locally_validated": False, "staging_validated": False, "production_ready": False}
    if not connections:
        result["blockers"].append("No hosting provider/account, installation inventory or isolated staging evidence is configured.")
    for c in connections:
        if c["enabled"]:
            report = d.compatibility(store, sid, c["id"])
            result["blockers"].extend(c["label"] + ": " + item for item in dict.fromkeys(
                report["missing"] + report["blockers"] +
                (report["elementor_preflight"]["missing"] if report["elementor_detected"] else [])))
    result["mapped"] = any(d.latest(store, sid, c["id"], "mapping") for c in connections)
    reviews = p.rows(store, sid, "cms_reviews")
    for row in reviews:
        try:
            review = p.validate_review(store, sid, row)
            if p.t.batch_validity(store, sid, review["batch_id"]):
                continue
        except ValueError:
            continue
        result["locally_validated"] = True
        all_attempts = p.rows(store, sid, "cms_attempts")
        attempts = [a for a in all_attempts if a["review_id"] == row["id"] and a["direction"] == "apply"]
        if review["destination"]["environment"] in {"staging", "local"} and attempts and all(
                p.latest_event(store, sid, a["id"]).get("verification") == "passed" and
                p.latest_event(store, sid, a["id"]).get("write") == "succeeded" for a in attempts) and len(attempts) == len(review["actions"]):
            result["staging_validated"] = True
        consumed = any(a["destination_key"] == p.cms_destination_key(review["destination"]) and
                       any((a["action_id"], a["revision"]) == (v["action_id"], v["revision"]) for v in review["actions"])
                       for a in all_attempts)
        if review["destination"]["environment"] == "production" and not consumed and all(a.get("staging_validation") for a in review["actions"]):
            result.update(staging_validated=True, production_ready=True, publishing_compatible=True)
    for key, level in (("locally_validated", "locally_validated"), ("staging_validated", "staging_validated"),
                       ("production_ready", "production_review_ready")):
        if result[key]:
            result["level"] = level
    if connections:
        result["next_action"] = "Review the exact current proposal and CMS packet; separate human approvals and explicit Apply are still required." if result["production_ready"] else "Refresh selected page evidence, import protected administrator inventory and independently review host effects/isolation. Unsupported stacks stay blocked."
    return result
