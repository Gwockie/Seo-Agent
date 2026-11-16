"""Manual page-title handoff and reporting using the existing approval journal."""
from . import page_tracking, tracking
from .coordination import run_lock, workspace_lock
from .storage import new_id, utc_now


def context(store, sid, bid, *, allow_history=False):
    batch = tracking.batch(store, sid, bid)
    frozen = batch["payload"]["actions"]
    if tracking.digest(frozen) != batch["payload"]["fingerprint"] or len(frozen) != 1:
        raise ValueError("Manual publication requires one intact frozen action")
    action = frozen[0]
    if not action["action"].get("manual_post_title"):
        raise ValueError("This action has no manual page title mapping")
    approval = next((r for r in tracking.rows(store, "human_approvals", sid) if r["batch_id"] == bid), None)
    if (not approval or (approval["payload"].get("history_only") and not allow_history)
            or approval["payload"]["fingerprint"] != batch["payload"]["fingerprint"]):
        raise ValueError("Fresh exact human approval is required")
    return action, approval


def history(store, sid, frozen, approval):
    return [r["payload"] for r in tracking.rows(store, "implementation_receipts", sid)
            if r["action_id"] == frozen["action_id"] and r["revision"] == frozen["revision"]
            and r["payload"]["approval_id"] == approval["id"] and r["payload"]["environment"] == "production"]


def _receipt(store, sid, frozen, approval, attempt, outcome, source, *, actual=None, occurred=None, snapshot=None):
    a = frozen["action"]
    return tracking.record_receipt(store, sid, {
        "schema": "seo-implementation-receipt/1", "receipt_id": new_id(), "site_id": sid,
        "action_id": frozen["action_id"], "revision": frozen["revision"], "attempt_id": attempt,
        "environment": "production", "outcome": outcome, "occurred_utc": occurred or utc_now(),
        "current": a["current"], "proposed": a["proposed"], "actual": actual, "approval_id": approval["id"],
        "source": source, "verification": "Exact public heading observed in saved HTML" if snapshot else "",
        "verification_snapshot_id": snapshot, "corrects": None,
    }, manual_operator=True)


def begin(store, sid, bid, *, preflight_confirmed, source):
    frozen, approval = context(store, sid, bid)
    if preflight_confirmed is not True or not source.strip():
        raise ValueError("Confirm current CMS evidence, scope and the preserved baseline before opening the editor")
    with run_lock(workspace_lock(store.root)):
        return _receipt(store, sid, frozen, approval, new_id(), "attempted", "Manual operator preflight · " + source.strip())


def report(store, sid, bid, *, outcome, source, occurred, partial_value=None):
    frozen, approval = context(store, sid, bid, allow_history=True)
    events = history(store, sid, frozen, approval)
    if len(events) != 1 or events[0]["outcome"] != "attempted":
        raise ValueError("A pending manual attempt is required")
    if outcome not in {"reported_applied", "failed", "partial"} or not source.strip() or not occurred.strip():
        raise ValueError("Supply the operator outcome, UTC event time and source")
    if outcome == "partial" and partial_value is None:
        raise ValueError("Enter the actual reported title for partial work")
    actual = {"reported_applied": frozen["action"]["proposed"], "partial": partial_value}.get(outcome)
    return _receipt(store, sid, frozen, approval, events[0]["attempt_id"], outcome, "Manual operator report · " + source.strip(), actual=actual, occurred=occurred)


def observation(store, sid, frozen, events):
    a = frozen["action"]
    snapshot = page_tracking.latest_snapshot(store, sid, a["url"])
    applied = next((v for v in events if v["outcome"] == "reported_applied"), None)
    if not applied or any(v["outcome"] in {"correction", "rolled_back", "manual_reconciliation"} for v in events):
        return None, "A current matching operator report is required"
    if not snapshot or snapshot["checked"] <= applied["occurred_utc"] or snapshot["status"] != "complete":
        return None, "Refresh tracked pages to collect successful public HTML after the reported publication time"
    if page_tracking.observed_value(snapshot["payload"]["values"], a, proposed=True, target=frozen.get("target"), html=snapshot["payload"]["html"]) != a["proposed"]:
        return None, "The latest public capture does not show the exact proposed heading at the frozen widget"
    return snapshot, "The public HTML shows the exact heading in the frozen widget"


def verify(store, sid, bid):
    frozen, approval = context(store, sid, bid, allow_history=True)
    events = history(store, sid, frozen, approval)
    snapshot, message = observation(store, sid, frozen, events)
    if snapshot is None:
        raise ValueError(message)
    return _receipt(store, sid, frozen, approval, events[0]["attempt_id"], "verification",
                    "Read-only public tracking capture", actual=frozen["action"]["proposed"], snapshot=snapshot["id"])


def reconcile(store, sid, bid, *, scope_checked, actual, source):
    frozen, approval = context(store, sid, bid, allow_history=True)
    events = history(store, sid, frozen, approval)
    if not events or scope_checked is not True or actual is None or not source.strip():
        raise ValueError("Confirm the current CMS title and shared effects from read-only evidence")
    return _receipt(store, sid, frozen, approval, events[0]["attempt_id"], "manual_reconciliation",
                    "Manual operator reconciliation · " + source.strip(), actual=actual)
