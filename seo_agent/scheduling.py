"""Deterministic site-scoped weekly due state; no Task Scheduler or network side effects."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json

from pydantic import Field, field_validator

from .config import StrictModel
from .storage import checked_id, config_hash, new_id

UTC = timezone.utc
RETRIES = (timedelta(minutes=15), timedelta(hours=1))
REQUIRED = ("gsc_current", "gsc_previous", "sitemaps", "crawl", "inspection")


def instant(value):
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if dt.tzinfo is None:
        raise ValueError("An aware timestamp is required")
    return dt.astimezone(UTC)


def now_utc():
    return datetime.now(UTC)


class Schedule(StrictModel):
    enabled: bool = False
    weekday: int = Field(default=0, ge=0, le=6)
    local_time: str = "09:00"
    timezone: str = "America/New_York"
    days: int = Field(default=28, ge=28, le=28)
    lag_days: int = Field(default=3, ge=3, le=3)
    max_pages: int = Field(default=50, ge=1, le=50)
    inspect_limit: int = Field(default=20, ge=1, le=20)

    @field_validator("timezone")
    @classmethod
    def zone(cls, value):
        ZoneInfo(value)
        return value

    @field_validator("local_time")
    @classmethod
    def clock(cls, value):
        import re
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Use HH:MM local time")
        return value


def occurrence(s, date):
    """First fold on repeated time; advance nonexistent time to first valid minute."""
    s = Schedule.model_validate(s)
    hour, minute = map(int, s.local_time.split(":"))
    naive = datetime.combine(date, datetime.min.time()).replace(hour=hour, minute=minute)
    zone = ZoneInfo(s.timezone)
    for offset in range(181):
        local = (naive + timedelta(minutes=offset)).replace(tzinfo=zone, fold=0)
        utc = local.astimezone(UTC)
        if utc.astimezone(zone).replace(tzinfo=None) == local.replace(tzinfo=None):
            return utc
    raise ValueError("Unsupported local time transition")


def next_occurrence(s, after):
    s = Schedule.model_validate(s)
    after = instant(after)
    date = after.astimezone(ZoneInfo(s.timezone)).date()
    date += timedelta(days=(s.weekday - date.weekday()) % 7)
    candidate = occurrence(s.model_dump(), date)
    return candidate if candidate > after else occurrence(s.model_dump(), date + timedelta(days=7))


def schedule(store, sid):
    store.site(sid)
    with store.db() as db:
        row = db.execute("SELECT payload FROM weekly_schedules WHERE site_id=?", (sid,)).fetchone()
    if row:
        value = json.loads(row[0])
        Schedule.model_validate(value["settings"])
        return value
    return {"settings": Schedule().model_dump(), "next_due": None, "last_attempt": None,
            "last_complete": None, "retry_at": None, "failure": None, "stopped": False}


def persist(store, sid, value):
    store.require_private_write()
    with store.db() as db:
        db.execute("INSERT INTO weekly_schedules VALUES (?,?) ON CONFLICT(site_id) DO UPDATE SET payload=excluded.payload",
                   (sid, json.dumps(value, sort_keys=True)))


def save_schedule(store, sid, settings, *, now=None):
    from .coordination import run_lock, workspace_lock
    with run_lock(workspace_lock(store.root)):
        value = schedule(store, sid)
        validated = Schedule.model_validate(settings).model_dump()
        # Explicit review also binds the current saved connection/profile.
        value.update(settings=validated, config_hash=config_hash(store.site(sid)),
                     next_due=next_occurrence(validated, now or now_utc()).isoformat(),
                     retry_at=None, stopped=False, failure=None)
        persist(store, sid, value)
        return value


def disable(store, sid):
    from .coordination import run_lock, workspace_lock
    with run_lock(workspace_lock(store.root)):
        value = schedule(store, sid)
        value["settings"]["enabled"] = False
        persist(store, sid, value)


def attempts(store, sid):
    store.site(sid)
    with store.db() as db:
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in db.execute(
            "SELECT * FROM weekly_attempts WHERE site_id=? ORDER BY started,id", (sid,))]


def status(store, sid, *, now=None):
    value = schedule(store, sid)
    due = value["next_due"]
    value["overdue"] = bool(value["settings"]["enabled"] and due and instant(due) <= (now or now_utc()))
    return value


def claim(store, sid, *, now=None, manual=False, trigger_id=None):
    """Caller owns the workspace gate. Reconcile first; never overwrite evidence."""
    now = instant(now or now_utc())
    value = schedule(store, sid)
    previous = attempts(store, sid)
    if trigger_id:
        checked_id(trigger_id)
    if trigger_id and any(a["payload"].get("trigger_id") == trigger_id for a in previous):
        return None
    if any(a["finished"] is None for a in previous):
        return None
    if not manual and (not value["settings"]["enabled"] or value["stopped"] or not value["next_due"]
                       or instant(value["next_due"]) > now or (value["retry_at"] and instant(value["retry_at"]) > now)):
        return None
    scheduled = value["next_due"] if not manual else now.isoformat()
    same_due = [a for a in previous if a["scheduled"] == scheduled and not a["payload"].get("manual")]
    attempt_id, request_id = new_id(), new_id()
    payload = {"status": "running", "manual": manual, "trigger_id": trigger_id,
               "sequence": len(same_due) + 1, "failure": None, "sources": {}}
    store.require_private_write()
    with store.db() as db:
        db.execute("INSERT INTO weekly_attempts VALUES (?,?,?,?,NULL,?,NULL,?)",
                   (attempt_id, sid, scheduled, now.isoformat(), request_id, json.dumps(payload)))
    value["last_attempt"] = attempt_id
    persist(store, sid, value)
    return {"id": attempt_id, "site_id": sid, "scheduled": scheduled, "request_id": request_id, "payload": payload}


def completeness(store, sid, aid):
    """Collection completeness is distinct from a site's SEO/indexing health."""
    audit = store.audit(sid, aid)
    manifest = json.loads(audit["manifest"])
    stages = manifest.get("stages", {})
    sources = {name: stages.get(name, {}).get("status", "unavailable") for name in REQUIRED}
    complete = audit["status"] == "complete" and all(v == "complete" for v in sources.values())
    crawl = stages.get("crawl", {})
    inspection = stages.get("inspection", {})
    complete = complete and crawl.get("page_count", 0) > 0 and crawl.get("content_page_count", 0) > 0
    complete = complete and not crawl.get("unavailable_page_count", 0) and not crawl.get("missing_priority_count", 0)
    complete = complete and inspection.get("requested_count", 0) > 0 and inspection.get("result_count") == inspection.get("requested_count")
    return bool(complete), sources


def finish(store, attempt, *, audit_id=None, failure=None, retryable=False, retry_after_seconds=0, now=None):
    now = instant(now or now_utc())
    sid = attempt["site_id"]
    complete, sources = completeness(store, sid, audit_id) if audit_id else (False, {})
    if failure == "interrupted":
        complete = False
    payload = {**attempt["payload"], "status": "interrupted" if failure == "interrupted" else "complete" if complete else "partial" if audit_id else "failed",
               "sources": sources, "failure": None if complete else (failure or "collection_incomplete")}
    store.require_private_write()
    with store.db() as db:
        started = db.execute("SELECT started FROM weekly_attempts WHERE id=? AND site_id=?", (attempt["id"], sid)).fetchone()
        if started is None:
            raise ValueError("Unknown selected-site attempt")
        # A wall clock correction cannot create impossible history or an early retry.
        now = max(now, instant(started[0]))
        changed = db.execute("UPDATE weekly_attempts SET finished=?,audit_id=?,payload=? WHERE id=? AND site_id=? AND finished IS NULL",
                   (now.isoformat(), audit_id, json.dumps(payload), attempt["id"], sid))
        if not changed.rowcount:
            prior = db.execute("SELECT payload FROM weekly_attempts WHERE id=? AND site_id=?", (attempt["id"], sid)).fetchone()
            if prior is None:
                raise ValueError("Unknown selected-site attempt")
            return json.loads(prior[0])  # An old completion cannot change current due state.
    value = schedule(store, sid)
    value["failure"] = payload["failure"]
    if complete:
        value["last_complete"] = {"audit_id": audit_id, "finished": now.isoformat()}
        if not payload["manual"] or (value["next_due"] and instant(value["next_due"]) <= now):
            value.update(next_due=next_occurrence(value["settings"], now).isoformat(), retry_at=None, stopped=False)
    elif not payload["manual"]:
        index = payload["sequence"] - 1
        if retryable and index < len(RETRIES) and retry_after_seconds <= 7 * 86400:
            value["retry_at"] = (now + max(RETRIES[index], timedelta(seconds=retry_after_seconds))).isoformat()
        else:
            value.update(retry_at=None, stopped=True)
    persist(store, sid, value)
    return payload


def reconcile(store, *, now=None):
    """An acquired gate proves no coordinated collector remains. No fake completion."""
    for site in store.sites():
        sid = site["id"]
        for a in attempts(store, sid):
            if a["finished"] is None:
                aid = a["request_id"] if any(r["id"] == a["request_id"] for r in store.audits(sid)) else None
                if aid:
                    audit = store.audit(sid, aid)
                    if audit["status"] == "running":
                        m = json.loads(audit["manifest"])
                        path = store.audit_file(sid, aid, "data", "manifest.json")
                        if path.exists():
                            try:
                                checkpoint = json.loads(path.read_text(encoding="utf-8"))
                                if checkpoint.get("site_id") == sid and checkpoint.get("audit_id") == aid:
                                    m = checkpoint
                            except (OSError, ValueError):
                                pass  # Incomplete checkpoint is unavailable, never invented.
                        m.update(status="interrupted", message="Worker interrupted; completion not established")
                        store.finish_audit(sid, aid, "interrupted", m)
                # Even a finished audit interrupted before bookkeeping stays diagnostic.
                finish(store, a, audit_id=aid, failure="interrupted", retryable=True, now=now)
                if aid:
                    with store.db() as db:
                        db.execute("UPDATE weekly_attempts SET audit_id=? WHERE id=?", (aid, a["id"]))


def validate_restored(store):
    for site in store.sites():
        sid = site["id"]
        value = schedule(store, sid)
        Schedule.model_validate(value["settings"])
        for key in ("next_due", "retry_at"):
            if value.get(key):
                instant(value[key])
        for a in attempts(store, sid):
            for key in ("id", "request_id"):
                checked_id(a[key])
            instant(a["scheduled"]); instant(a["started"])
            if a["finished"]:
                if instant(a["finished"]) < instant(a["started"]):
                    raise ValueError("Attempt finish precedes its start")
            if a["audit_id"]:
                store.audit(sid, a["audit_id"])
                if a["audit_id"] != a["request_id"]:
                    raise ValueError("Attempt audit/request identity mismatch")
            p = a["payload"]
            if p.get("status") not in {"running", "complete", "partial", "failed", "interrupted"} or type(p.get("manual")) is not bool or type(p.get("sequence")) is not int or not 1 <= p["sequence"] <= 3:
                raise ValueError("Invalid attempt history")
            if p.get("trigger_id"):
                checked_id(p["trigger_id"])
            if (a["finished"] is None) != (p["status"] == "running"):
                raise ValueError("Attempt completion history mismatch")
        if value["last_attempt"] and not any(a["id"] == value["last_attempt"] for a in attempts(store, sid)):
            raise ValueError("Last attempt belongs to another site or is absent")
        if value["last_complete"]:
            store.audit(sid, value["last_complete"]["audit_id"])
            instant(value["last_complete"]["finished"])
        value["settings"]["enabled"] = False
        value.update(retry_at=None, stopped=True, failure="restored_review_required", config_hash=None)
        persist(store, sid, value)
