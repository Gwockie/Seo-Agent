"""Inert proposals, exact human approvals and append-only execution receipts.

This module has no CMS/network writer. Receipt imports never create approvals.
The single-user UI is the human approval boundary, not an imported text field.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import Field

from .config import StrictModel, ID_PATTERN, public_url, within_site
from .learning import METRICS, create_plan, plan
from .storage import checked_id, new_id, utc_now

MAX_DOCUMENT = 2 * 1024 * 1024


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("An ISO UTC timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("An ISO UTC timestamp is required") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0) or parsed > datetime.now(timezone.utc):
        raise ValueError("Timestamp must be UTC and cannot be in the future")
    return parsed.isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_document(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_DOCUMENT:
        raise ValueError("Tracking input must be at most 2 MiB")
    text = raw.decode("utf-8-sig")
    if not text.lstrip().startswith("{"):
        blocks = re.findall(r"^```json\s*\n(.*?)^```\s*$", text, re.M | re.S)
        if len(blocks) != 1:
            raise ValueError("Supply JSON or one fenced JSON proposal")
        text = blocks[0]
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("Duplicate JSON field")
            out[k] = v
        return out
    return json.loads(text, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


class Confirmation(StrictModel):
    item: str = Field(min_length=1, max_length=2000)
    status: Literal["pending", "confirmed"]
    source: str | None = Field(max_length=2000)


class Evidence(StrictModel):
    file: str = Field(min_length=1, max_length=150)
    row: int | None = Field(ge=2)
    revision: int | None = Field(ge=1, le=20)
    node_id: str | None = Field(max_length=80)


class Action(StrictModel):
    action_id: str = Field(pattern=ID_PATTERN)
    url: str = Field(max_length=2048)
    action_kind: Literal["title", "text", "href", "canonical", "index_directive", "setting"]
    current: str | None = Field(max_length=8000)
    proposed: str = Field(min_length=1, max_length=8000)
    current_source: str = Field(min_length=1, max_length=4000)
    capture_time_utc: str | None
    rationale: str = Field(min_length=1, max_length=4000)
    expected_effect: str = Field(min_length=1, max_length=4000)
    primary_measure: str
    measurement: str = Field(min_length=1, max_length=4000)
    confirmations: list[Confirmation] = Field(max_length=50)
    validation: str = Field(min_length=1, max_length=4000)
    rollback: str = Field(min_length=1, max_length=4000)
    evidence: list[Evidence] = Field(max_length=50)
    recommendation_id: str | None = Field(default=None, pattern=ID_PATTERN)
    revision_note: str = Field(default="", max_length=4000)
    restored_from: int | None = Field(default=None, ge=1, le=100)


class Handoff(StrictModel):
    schema_version: Literal["seo-change-handoff/1"] = Field(alias="schema")
    kind: Literal["proposal"]
    site_id: str = Field(pattern=ID_PATTERN)
    audit_id: str = Field(pattern=ID_PATTERN)
    prepared_utc: str
    actions: list[Action] = Field(min_length=1, max_length=100)


def validate_action(store, sid, aid, raw):
    store.audit(sid, aid)
    a = Action.model_validate(raw).model_dump(exclude_unset=True)
    if a.get("recommendation_id") and not any(r["id"] == a["recommendation_id"] for r in store.findings(sid, aid)):
        raise ValueError("Recommendation must belong to this site/audit")
    if public_url(a["url"]) != a["url"] or not within_site(store.site(sid).url, a["url"]):
        raise ValueError("Exact selected-site URL required")
    if a["primary_measure"] not in METRICS:
        raise ValueError("Unknown measurement")
    for k in ("proposed", "current_source", "rationale", "expected_effect", "measurement", "validation", "rollback"):
        if not a[k].strip():
            raise ValueError("Action descriptions cannot be blank")
    if a["current"] == a["proposed"]:
        raise ValueError("Action does not change a value")
    if a["capture_time_utc"]:
        a["capture_time_utc"] = timestamp(a["capture_time_utc"])
    for c in a["confirmations"]:
        if not c["item"].strip() or (c["status"] == "confirmed" and not (c["source"] or "").strip()):
            raise ValueError("Confirmation assertion requires an item and source")
    for ref in a["evidence"]:
        kind = "reports" if ref["file"].endswith(".md") else "data"
        path = store.audit_file(sid, aid, kind, ref["file"])
        if not path.is_file() or path.stat().st_size > 40 * 1024 * 1024:
            raise ValueError("Own-audit evidence is missing or oversized")
        if ref["row"] is not None:
            import csv
            if path.suffix != ".csv":
                raise ValueError("Rows require CSV evidence")
            with path.open(encoding="utf-8-sig", newline="") as handle:
                if sum(1 for _ in csv.reader(handle)) < ref["row"]:
                    raise ValueError("Evidence row does not exist")
        if ref["revision"] is not None or ref["node_id"] is not None:
            from .previews import load_preview, walk
            bundle = load_preview(store, sid, aid, revision=ref["revision"])
            if not bundle or not any(p["url"] == a["url"] and (not ref["node_id"] or any(n.get("id") == ref["node_id"] for n in walk(p["tree"]))) for p in bundle["pages"]):
                raise ValueError("Capture revision/node cannot be resolved")
    return a


def rows(store, table, sid):
    if table not in {"tracking_actions", "handoff_imports", "publication_batches", "human_approvals", "implementation_receipts", "public_snapshots", "outside_changes", "tracking_checks", "trend_sources", "tracking_reviews", "approval_invalidations", "proposal_evaluations"}:
        raise ValueError("Unsupported tracking source")
    store.site(sid)
    with store.db() as db:
        result = db.execute(f"SELECT * FROM {table} WHERE site_id=? ORDER BY rowid", (sid,)).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload"])} for r in result]


def actions(store, sid, *, latest=True):
    result = rows(store, "tracking_actions", sid)
    if latest:
        chosen = {}
        for row in result:
            chosen[row["action_id"]] = row
        return list(chosen.values())
    return result


def action(store, sid, action_id, revision):
    checked_id(action_id)
    if type(revision) is not int:
        raise ValueError("Integer revision required")
    result = next((r for r in actions(store, sid, latest=False) if r["action_id"] == action_id and r["revision"] == revision), None)
    if result is None:
        raise ValueError("Action/revision does not belong to this site")
    return result


def save_action(store, sid, aid, raw, *, revision=1, plan_id=None):
    store.require_private_write()
    a = validate_action(store, sid, aid, raw)
    previous = next((r for r in actions(store, sid) if r["action_id"] == a["action_id"]), None)
    if type(revision) is not int or revision != (previous["revision"] + 1 if previous else 1) or revision > 100:
        raise ValueError("Append the next revision; history cannot be replaced")
    if previous and (previous["audit_id"] != aid or previous["payload"]["url"] != a["url"] or previous["payload"]["action_kind"] != a["action_kind"] or previous["payload"].get("recommendation_id") != a.get("recommendation_id")):
        raise ValueError("Action identity is immutable")
    if plan_id:
        p = plan(store, sid, plan_id)
        if p["audit_id"] != aid or p["payload"]["url"] != a["url"]:
            raise ValueError("Action must match the plan's site/audit/page")
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        latest_revision = db.execute("SELECT MAX(revision) FROM tracking_actions WHERE site_id=? AND action_id=?", (sid, a["action_id"])).fetchone()[0] or 0
        if revision != latest_revision + 1:
            raise ValueError("Proposal changed while saving; reopen the latest revision")
        if db.execute("SELECT 1 FROM tracking_actions WHERE action_id=? AND site_id<>?", (a["action_id"], sid)).fetchone():
            raise ValueError("Action ID belongs to another site")
        db.execute("INSERT INTO tracking_actions VALUES (?,?,?,?,?,?,?)", (a["action_id"], sid, revision, aid, plan_id or (previous["plan_id"] if previous else None), utc_now(), canonical(a)))
    return a["action_id"]


def import_handoff(store, sid, aid, raw):
    store.require_private_write()
    h = Handoff.model_validate(load_document(raw)).model_dump(by_alias=True, exclude_unset=True)
    if h["site_id"] != sid or h["audit_id"] != aid:
        raise ValueError("Handoff belongs to a different site/audit")
    h["prepared_utc"] = timestamp(h["prepared_utc"])
    h["actions"] = [validate_action(store, sid, aid, a) for a in h["actions"]]
    if len({a["action_id"] for a in h["actions"]}) != len(h["actions"]):
        raise ValueError("Duplicate action identities")
    for a in h["actions"]:
        if a["capture_time_utc"] and a["capture_time_utc"] > h["prepared_utc"]:
            raise ValueError("Capture is later than preparation")
    key, iid = digest(h), new_id()
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT id FROM handoff_imports WHERE digest=?", (key,)).fetchone()
        if old:
            return old[0]
        for a in h["actions"]:
            if db.execute("SELECT 1 FROM tracking_actions WHERE action_id=?", (a["action_id"],)).fetchone():
                raise ValueError("Action already exists; append a reviewed revision instead")
            db.execute("INSERT INTO tracking_actions VALUES (?,?,1,?,NULL,?,?)", (a["action_id"], sid, aid, utc_now(), canonical(a)))
        db.execute("INSERT INTO handoff_imports VALUES (?,?,?,?,?,?)", (iid, sid, aid, key, utc_now(), canonical(h)))
    return iid


def from_preview(store, sid, aid, revision):
    from .previews import load_preview, walk, preview_filename
    from .learning import explanation
    bundle = load_preview(store, sid, aid, revision=revision)
    if not bundle:
        raise ValueError("No saved preview")
    result = []
    for p in bundle["pages"]:
        nodes = {n.get("id"): n.get("tag") for n in walk(p["tree"])}
        for index, a in enumerate(p["actions"]):
            expected = explanation(a, nodes.get(a.get("node_id"), ""))
            target = f"{a['kind']}:{a.get('node_id', '')}:{a.get('text_child', '')}"
            identity = hashlib.sha256(f"{sid}:{aid}:{p['url']}:{target}".encode()).hexdigest()[:32]
            result.append({"action_id": identity, "url": p["url"], "action_kind": a["kind"], "current": a["current"], "proposed": a["proposed"],
                "current_source": f"Local preview revision {revision}", "capture_time_utc": p["captured_utc"], "rationale": a["rationale"],
                "expected_effect": expected["expected_effect"], "primary_measure": expected["metric"], "measurement": expected["measurement"],
                "confirmations": [{"item": a["confirmations"] or "Confirm service/location and all business or clinical claims", "status": "pending", "source": None}],
                "validation": a["validation"], "rollback": a["rollback"], "evidence": [{"file": preview_filename(revision), "row": None, "revision": revision, "node_id": a.get("node_id")} ]})
    prepared = max(timestamp(p["captured_utc"]) for p in bundle["pages"])
    return import_handoff(store, sid, aid, canonical({"schema": "seo-change-handoff/1", "kind": "proposal", "site_id": sid, "audit_id": aid, "prepared_utc": prepared, "actions": result}).encode())


def from_plan(store, sid, pid, kind, confirmations, validation, rollback):
    p = plan(store, sid, pid)
    a = p["payload"]
    raw = {"action_id": new_id(), "url": a["url"], "action_kind": kind, "current": a["current"] or None, "proposed": a["proposed"],
        "current_source": "Existing saved tracking plan; current public value needs refresh", "capture_time_utc": None,
        "rationale": a["why"], "expected_effect": a["expected_effect"], "primary_measure": a["metric"], "measurement": a["measurement"],
        "confirmations": [{"item": confirmations, "status": "pending", "source": None}], "validation": validation, "rollback": rollback, "evidence": []}
    return save_action(store, sid, p["audit_id"], raw, plan_id=pid)


_CAPTURE_TARGET = object()


def readiness(store, sid, record, *, now=None, target=_CAPTURE_TARGET, check_assessment=True):
    from .page_tracking import latest_snapshot, observed_value, capture_target
    a = record["payload"]
    if target is _CAPTURE_TARGET:
        target = capture_target(store, sid, record) if a["action_kind"] in ("text", "href") else None
    now = now or datetime.now(timezone.utc)
    snapshot = latest_snapshot(store, sid, a["url"])
    reasons = []
    if not snapshot or snapshot["status"] != "complete":
        reasons.append("Current public source is unavailable")
    elif now - datetime.fromisoformat(snapshot["checked"]) > timedelta(hours=24):
        reasons.append("Refresh public values; capture is older than 24 hours")
    elif a["current"] is None or observed_value(snapshot["payload"]["values"], a, target=target, html=snapshot["payload"]["html"]) != a["current"]:
        reasons.append("Current public target/value is unknown, ambiguous or differs from the proposal; text/link actions need matching captured target evidence")
    if not a["confirmations"] or any(c["status"] != "confirmed" for c in a["confirmations"]):
        reasons.append("Supplied factual assertions still need explicit human confirmation")
    if a["action_kind"] == "setting":
        reasons.append("Settings cannot be verified by public-page capture")
    if a["current"] is None or not a["capture_time_utc"]:
        reasons.append("Capture time/current value is missing; append a refreshed revision")
    from .proposal_review import mandatory_blockers, constraint_blockers
    reasons.extend(mandatory_blockers(store, sid, record) if check_assessment else constraint_blockers(store, sid, record))
    return {"ready": not reasons, "reasons": reasons, "snapshot_id": snapshot["id"] if snapshot else None, "target": target}


def freeze_batch(store, sid, selected):
    from .proposal_review import context_binding
    store.require_private_write()
    if not selected or len(selected) > 100 or len(set(selected)) != len(selected):
        raise ValueError("Select 1–100 distinct exact actions")
    frozen = []
    latest = {r["action_id"]: r for r in actions(store, sid)}
    targets = set()
    for identity, revision in selected:
        r = action(store, sid, identity, revision)
        if latest[identity]["revision"] != revision:
            raise ValueError("Only the latest revision can be frozen")
        ready = readiness(store, sid, r)
        if not ready["ready"]:
            raise ValueError("; ".join(ready["reasons"]))
        a = r["payload"]
        target = (a["url"], a["action_kind"], a["current"])
        if target in targets or (a["action_kind"] in ("title", "canonical", "index_directive") and any(t[:2] == target[:2] for t in targets)):
            raise ValueError("Overlapping actions cannot be approved together")
        targets.add(target)
        frozen.append({"action_id": identity, "revision": revision, "audit_id": r["audit_id"], "snapshot_id": ready["snapshot_id"], "action": a,
                       "assessment_context": context_binding(store, sid, r),
                       **({"target": ready["target"]} if ready["target"] is not None else {})})
    payload = {"actions": frozen, "fingerprint": digest(frozen)}
    bid = new_id()
    with store.db() as db:
        db.execute("INSERT INTO publication_batches VALUES (?,?,?,?)", (bid, sid, utc_now(), canonical(payload)))
    return bid


def batch(store, sid, bid):
    checked_id(bid)
    b = next((r for r in rows(store, "publication_batches", sid) if r["id"] == bid), None)
    if b is None:
        raise ValueError("Batch does not belong to the selected site")
    return b


def batch_validity(store, sid, bid):
    b = batch(store, sid, bid)
    invalid = []
    latest = {r["action_id"]: r for r in actions(store, sid)}
    for a in b["payload"]["actions"]:
        r = latest[a["action_id"]]
        approvals = [v["id"] for v in rows(store, "human_approvals", sid) if v["batch_id"] == bid]
        invalidated = any(v["approval_id"] in approvals and v["action_id"] == a["action_id"] for v in rows(store, "approval_invalidations", sid))
        # Fail closed for contradictory failures saved before the receipt guard.
        changed_failure = any(v["payload"]["approval_id"] in approvals and v["action_id"] == a["action_id"] and v["revision"] == a["revision"]
                              and v["payload"]["environment"] == "production" and v["payload"]["outcome"] == "failed"
                              and v["payload"]["actual"] is not None and v["payload"]["actual"] != v["payload"]["current"]
                              for v in rows(store, "implementation_receipts", sid))
        from .proposal_review import context_binding
        # A new independent capture alone does not revoke an unaffected exact action.
        # Readiness still rechecks its frozen target/value. Assessments bind the full capture.
        context_changed = "assessment_context" in a and {k: v for k, v in a["assessment_context"].items() if k != "snapshot_hash"} != {k: v for k, v in context_binding(store, sid, r).items() if k != "snapshot_hash"}
        # Pending approval needs a current assessment. An already approved exact
        # action survives a capture refresh only while its frozen value/target,
        # evidence/configuration and mandatory factual/technical checks still hold.
        ready = readiness(store, sid, r, target=a.get("target"), check_assessment=not approvals)
        if r["revision"] != a["revision"] or context_changed or not ready["ready"] or invalidated or changed_failure:
            invalid.append(a["action_id"])
    return invalid


def approve_from_human_ui(store, sid, bid, *, human_clicked, statement, confirmation_source):
    """Only call in the explicit Streamlit human approval submit handler.

    No CLI/import route exists. Local same-user Python access is not a separate
    authentication boundary; imported authorization claims must never call this.
    """
    store.require_private_write()
    if human_clicked is not True or statement != "I approve this exact publication batch" or not confirmation_source.strip() or len(confirmation_source) > 4000:
        raise ValueError("Explicit human authorization and factual confirmation source required")
    apid = new_id()
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        b = batch(store, sid, bid)
        if batch_validity(store, sid, bid):
            raise ValueError("Proposal/current value changed; prepare a new review")
        if db.execute("SELECT 1 FROM human_approvals WHERE site_id=? AND batch_id=?", (sid, bid)).fetchone():
            raise ValueError("This exact batch already has human approval")
        db.execute("INSERT INTO human_approvals VALUES (?,?,?,?,?)", (apid, sid, bid, utc_now(), canonical({"origin": "explicit human UI submission", "statement": statement, "confirmation_source": confirmation_source, "fingerprint": b["payload"]["fingerprint"]})))
    return apid


class Receipt(StrictModel):
    schema_version: Literal["seo-implementation-receipt/1"] = Field(alias="schema")
    receipt_id: str = Field(pattern=ID_PATTERN)
    site_id: str = Field(pattern=ID_PATTERN)
    action_id: str = Field(pattern=ID_PATTERN)
    revision: int = Field(ge=1, le=100)
    attempt_id: str = Field(pattern=ID_PATTERN)
    environment: Literal["local", "staging", "production"]
    outcome: Literal["attempted", "reported_applied", "failed", "partial", "rolled_back", "verification", "correction"]
    occurred_utc: str
    current: str | None = Field(max_length=8000)
    proposed: str = Field(max_length=8000)
    actual: str | None = Field(max_length=8000)
    approval_id: str | None = Field(pattern=ID_PATTERN)
    source: str = Field(min_length=1, max_length=4000)
    verification: str = Field(max_length=4000)
    verification_snapshot_id: str | None = Field(default=None, pattern=ID_PATTERN)
    corrects: str | None = Field(pattern=ID_PATTERN)


def record_receipt(store, sid, raw):
    store.require_private_write()
    r = Receipt.model_validate(load_document(raw) if isinstance(raw, bytes) else raw).model_dump(by_alias=True)
    if r["site_id"] != sid:
        raise ValueError("Receipt belongs to another site")
    r["occurred_utc"] = timestamp(r["occurred_utc"])
    a = action(store, sid, r["action_id"], r["revision"])
    if r["current"] != a["payload"]["current"] or r["proposed"] != a["payload"]["proposed"] or not r["source"].strip():
        raise ValueError("Receipt must preserve the exact proposal values and source")
    if r["occurred_utc"] < a["created"]:
        raise ValueError("Receipt predates the proposal")
    if r["outcome"] == "reported_applied" and r["actual"] != r["proposed"]:
        raise ValueError("Mismatched actual value must be reported as partial")
    if r["outcome"] == "rolled_back" and r["actual"] != r["current"]:
        raise ValueError("Rollback must report the original value")
    if r["outcome"] == "attempted" and r["actual"] is not None:
        raise ValueError("An attempt is not an outcome")
    if r["outcome"] == "partial" and r["actual"] is None:
        raise ValueError("Partial work needs the actual value")
    if r["outcome"] == "failed" and r["actual"] is not None and r["actual"] != r["current"]:
        raise ValueError("Failed work with a changed actual value must be reported as partial")
    if r["outcome"] == "verification" and not r["verification"].strip():
        raise ValueError("Verification requires evidence text")
    if r["verification_snapshot_id"]:
        from .page_tracking import observed_value
        snapshot = next((s for s in rows(store, "public_snapshots", sid) if s["id"] == r["verification_snapshot_id"]), None)
        approval = next((v for v in rows(store, "human_approvals", sid) if v["id"] == r["approval_id"]), None)
        frozen = next((v for v in batch(store, sid, approval["batch_id"])["payload"]["actions"] if v["action_id"] == r["action_id"] and v["revision"] == r["revision"]), None) if approval else None
        if r["outcome"] != "verification" or r["environment"] != "production" or not frozen or not snapshot or snapshot["status"] != "complete" or snapshot["url"] != a["payload"]["url"] or snapshot["checked"] > r["occurred_utc"] or observed_value(snapshot["payload"]["values"], a["payload"], proposed=True, target=frozen.get("target"), html=snapshot["payload"]["html"]) != r["actual"] or r["actual"] != r["proposed"]:
            raise ValueError("Public verification must match an exact successful own-site snapshot and actual proposal value")
    if r["environment"] != "production" and r["approval_id"] is not None:
        raise ValueError("Local/staging receipts do not consume production approval")
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM implementation_receipts WHERE id=?", (r["receipt_id"],)).fetchone()
        if existing:
            raise ValueError("Duplicate/replayed receipt")
        all_receipts = [json.loads(row[0]) for row in db.execute("SELECT payload FROM implementation_receipts WHERE site_id=? AND action_id=? AND revision=? ORDER BY rowid", (sid, r["action_id"], r["revision"]))]
        prior = [v for v in all_receipts if v["attempt_id"] == r["attempt_id"]]
        replay_fields = ("environment", "outcome", "occurred_utc", "actual", "approval_id", "source", "verification", "corrects", "verification_snapshot_id")
        if any(all(v.get(k) == r.get(k) for k in replay_fields) for v in all_receipts):
            raise ValueError("Replayed submission with changed receipt/attempt IDs")
        if r["verification_snapshot_id"] and any(v.get("verification_snapshot_id") == r["verification_snapshot_id"] and v["attempt_id"] == r["attempt_id"] for v in prior):
            raise ValueError("This public verification source is already recorded for the attempt")
        if db.execute("SELECT 1 FROM implementation_receipts WHERE json_extract(payload,'$.attempt_id')=? AND (site_id<>? OR action_id<>? OR revision<>?)", (r["attempt_id"], sid, r["action_id"], r["revision"])).fetchone():
            raise ValueError("Attempt identity cannot cross actions/revisions/sites")
        if prior and any(v["environment"] != r["environment"] or v["approval_id"] != r["approval_id"] for v in prior):
            raise ValueError("Attempt environment/approval is immutable")
        if prior and r["occurred_utc"] < prior[-1]["occurred_utc"]:
            raise ValueError("Receipt timestamp precedes the previous event")
        if prior and r["verification_snapshot_id"] and snapshot["checked"] < prior[0]["occurred_utc"]:
            raise ValueError("Verification source predates the implementation attempt")
        if any(v["outcome"] == r["outcome"] and v["actual"] == r["actual"] and v["occurred_utc"] == r["occurred_utc"] for v in prior):
            raise ValueError("Replayed event with a different receipt ID")
        if r["outcome"] == "attempted":
            if prior or r["corrects"]:
                raise ValueError("Attempt already exists")
            attempts = {v["attempt_id"]: v for v in all_receipts if v["environment"] == r["environment"]}
            if any(v["outcome"] == "attempted" for v in attempts.values()):
                raise ValueError("Close the previous attempt with an outcome before starting another")
            if r["environment"] == "production":
                if any(v["outcome"] == "reported_applied" and v["approval_id"] == r["approval_id"] for v in all_receipts):
                    raise ValueError("Applied publication cannot be attempted again under the same approval")
                approval = db.execute("SELECT * FROM human_approvals WHERE id=? AND site_id=?", (r["approval_id"], sid)).fetchone()
                if not approval or json.loads(approval["payload"]).get("history_only") or r["occurred_utc"] < approval["created"]:
                    raise ValueError("Production attempt needs prior explicit human approval")
                b = batch(store, sid, approval["batch_id"])
                if not any(v["action_id"] == r["action_id"] and v["revision"] == r["revision"] for v in b["payload"]["actions"]) or r["action_id"] in batch_validity(store, sid, b["id"]):
                    raise ValueError("Approval is stale or covers a different action/revision")
        elif not prior:
            raise ValueError("Record the attempt first; outcomes cannot grant approval")
        elif r["outcome"] in {"reported_applied", "failed", "partial"}:
            if prior[-1]["outcome"] != "attempted" or r["corrects"]:
                raise ValueError("Attempt already has an outcome; append a correction or new attempt")
        elif r["outcome"] == "rolled_back":
            if not any(v["outcome"] in {"reported_applied", "partial"} for v in prior) or any(v["outcome"] == "rolled_back" for v in prior) or r["corrects"]:
                raise ValueError("Rollback requires reported applied/partial work")
        elif r["outcome"] == "verification":
            if prior[-1]["outcome"] == "attempted" or r["corrects"]:
                raise ValueError("Verification follows an outcome")
        elif r["outcome"] == "correction":
            if not r["corrects"] or not any(v["receipt_id"] == r["corrects"] and v["outcome"] != "attempted" for v in prior):
                raise ValueError("Correction must reference an outcome in this exact attempt")
        db.execute("INSERT INTO implementation_receipts VALUES (?,?,?,?,?,?)", (r["receipt_id"], sid, r["action_id"], r["revision"], utc_now(), canonical(r)))
        if r["environment"] == "production" and r["outcome"] in {"partial", "correction", "rolled_back"}:
            db.execute("INSERT INTO approval_invalidations VALUES (?,?,?,?,?,?,?)", (new_id(), sid, r["approval_id"], r["action_id"], r["revision"], utc_now(), canonical({"reason": "Reported partial work, correction or rollback requires renewed exact review before another attempt", "receipt_id": r["receipt_id"]})))
    return r["receipt_id"]


def record_review(store, sid, identity, revision, aid, notes):
    store.require_private_write()
    r = action(store, sid, identity, revision)
    store.audit(sid, aid)
    if not notes.strip() or len(notes) > 4000:
        raise ValueError("Review requires 1–4,000 characters")
    from .trends import compare_action
    value = {"notes": notes, "comparison": compare_action(store, sid, identity, revision, aid)}
    rid = new_id()
    with store.db() as db:
        db.execute("INSERT INTO tracking_reviews VALUES (?,?,?,?,?,?,?)", (rid, sid, identity, r["revision"], aid, utc_now(), canonical(value)))
    return rid


def packet(store, sid, aid):
    """An inert JSON supplement, restricted to this audit and its related sources."""
    store.audit(sid, aid)
    store.require_private_write()  # Fresh protection gate on private export.
    selected = [r for r in actions(store, sid, latest=False) if r["audit_id"] == aid]
    identities = {r["action_id"] for r in selected}
    urls = {r["payload"]["url"] for r in selected}
    batches = [b for b in rows(store, "publication_batches", sid) if all(a["audit_id"] == aid for a in b["payload"]["actions"])]
    bids = {b["id"] for b in batches}
    receipts = [r for r in rows(store, "implementation_receipts", sid) if r["action_id"] in identities]
    outside = [r for r in rows(store, "outside_changes", sid) if r["url"] in urls and r["payload"].get("audit_id") in (None, aid)]
    snapshot_ids = {a["snapshot_id"] for b in batches for a in b["payload"]["actions"]}
    snapshot_ids.update(r["payload"].get("verification_snapshot_id") for r in receipts)
    snapshot_ids.update(r["payload"][key] for r in outside for key in ("before_snapshot", "after_snapshot"))
    return canonical({"schema": "seo-tracking-packet/1", "site_id": sid, "audit_id": aid, "actions": selected,
        "handoffs": [h for h in rows(store, "handoff_imports", sid) if h["audit_id"] == aid], "batches": batches,
        "approval_history_not_reusable_permission": [a for a in rows(store, "human_approvals", sid) if a["batch_id"] in bids],
        "approval_invalidations": [r for r in rows(store, "approval_invalidations", sid) if r["action_id"] in identities],
        "receipts": receipts,
        "reviews": [r for r in rows(store, "tracking_reviews", sid) if r["action_id"] in identities],
        "assessments": [r for r in rows(store, "proposal_evaluations", sid) if r["action_id"] in identities],
        "snapshots": [r for r in rows(store, "public_snapshots", sid) if r["audit_id"] == aid or r["id"] in snapshot_ids],
        "outside_changes": outside,
        "trends": [r for r in rows(store, "trend_sources", sid) if r["audit_id"] == aid]}).encode("utf-8")


def validate_restored_tracking(store):
    """Validate inert tracking history; restored approval is history, not authority."""
    from .page_tracking import extract, Settings
    for site in store.sites():
        sid = site["id"]
        for a in actions(store, sid, latest=False):
            checked_id(a["action_id"])
            timestamp(a["created"])
            validate_action(store, sid, a["audit_id"], a["payload"])
            if a["plan_id"]:
                p = plan(store, sid, a["plan_id"])
                if p["audit_id"] != a["audit_id"]:
                    raise ValueError("Restored plan relationship invalid")
        for r in rows(store, "implementation_receipts", sid):
            v = Receipt.model_validate(r["payload"]).model_dump(by_alias=True)
            if v["site_id"] != r["site_id"] or v["receipt_id"] != r["id"] or v["action_id"] != r["action_id"] or v["revision"] != r["revision"]:
                raise ValueError("Restored receipt identity differs from its database association")
            a = action(store, sid, r["action_id"], r["revision"])
            if v["current"] != a["payload"]["current"] or v["proposed"] != a["payload"]["proposed"]:
                raise ValueError("Restored receipt association invalid")
            timestamp(v["occurred_utc"])
        for r in rows(store, "public_snapshots", sid):
            timestamp(r["checked"])
            if not within_site(store.site(sid).url, r["url"]) or len(canonical(r["payload"]).encode()) > 3 * 1024 * 1024 or r["status"] not in {"complete", "unavailable"}:
                raise ValueError("Restored snapshot invalid")
            p = r["payload"]
            if r["status"] == "complete" and (p.get("values") != extract(p["html"], r["url"], p.get("headers", {})) or p.get("http_status") != 200 or p.get("final_url") != r["url"]):
                raise ValueError("Restored snapshot is incomplete")
        snapshots = {r["id"]: r for r in rows(store, "public_snapshots", sid)}
        for r in rows(store, "outside_changes", sid):
            p = r["payload"]
            before, after = snapshots.get(p["before_snapshot"]), snapshots.get(p["after_snapshot"])
            if not before or not after or before["status"] != "complete" or after["status"] != "complete" or before["url"] != r["url"] or after["url"] != r["url"] or before["checked"] >= after["checked"] or p["last_known_before_utc"] != before["checked"] or p["first_observed_after_utc"] != after["checked"] or r["first_seen"] != after["checked"] or p["approval"] is not None or p["action_id"] is not None or p["publication_time"] is not None:
                raise ValueError("Restored outside observation has invalid source relationships")
            for field, difference in p["diff"].items():
                if difference != {"before": before["payload"]["values"].get(field), "after": after["payload"]["values"].get(field)}:
                    raise ValueError("Restored outside diff differs from its sources")
        for b in rows(store, "publication_batches", sid):
            if digest(b["payload"]["actions"]) != b["payload"]["fingerprint"]:
                raise ValueError("Restored frozen batch fingerprint differs")
            for a in b["payload"]["actions"]:
                r = action(store, sid, a["action_id"], a["revision"])
                if r["payload"] != a["action"] or r["audit_id"] != a["audit_id"]:
                    raise ValueError("Restored batch action differs")
                snapshot = snapshots.get(a["snapshot_id"])
                if not snapshot or snapshot["status"] != "complete" or snapshot["url"] != a["action"]["url"]:
                    raise ValueError("Restored frozen capture reference invalid")
                if "target" in a:
                    from .page_tracking import capture_target, observed_value
                    if a["target"] != capture_target(store, sid, r) or observed_value(snapshot["payload"]["values"], a["action"], target=a["target"], html=snapshot["payload"]["html"]) != a["action"]["current"]:
                        raise ValueError("Restored frozen target differs from its capture evidence")
        for a in rows(store, "human_approvals", sid):
            b = batch(store, sid, a["batch_id"])
            if a["payload"].get("fingerprint") != b["payload"]["fingerprint"] or a["payload"].get("origin") != "explicit human UI submission":
                raise ValueError("Restored approval provenance invalid")
            with store.db() as db:
                db.execute("UPDATE human_approvals SET payload=? WHERE id=?", (canonical({**a["payload"], "history_only": True}), a["id"]))
        approvals = {a["id"] for a in rows(store, "human_approvals", sid)}
        for r in rows(store, "approval_invalidations", sid):
            if r["approval_id"] not in approvals:
                raise ValueError("Restored invalidation belongs to another site's approval")
            action(store, sid, r["action_id"], r["revision"])
        for r in rows(store, "tracking_reviews", sid):
            action(store, sid, r["action_id"], r["revision"])
            store.audit(sid, r["audit_id"])
        for r in rows(store, "trend_sources", sid):
            store.audit(sid, r["audit_id"])
            if r["dataset"] not in {"property", "page"} or r["period"] not in {"current", "previous"} or len(canonical(r["payload"]).encode()) > 40 * 1024 * 1024:
                raise ValueError("Restored trend source invalid")
        with store.db() as db:
            s = db.execute("SELECT payload FROM tracking_settings WHERE site_id=?", (sid,)).fetchone()
            if s:
                value = Settings.model_validate_json(s[0])
                if any(not within_site(store.site(sid).url, u) or public_url(u) != u for u in value.urls):
                    raise ValueError("Restored tracking setting URL outside selected site")
