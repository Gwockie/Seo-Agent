"""Local hypotheses and append-only outcome reviews, never publication approval."""
from __future__ import annotations

import json
import math
from datetime import date

from pydantic import Field

from .config import StrictModel, SiteConfig, within_site
from .metrics import totals, classify
from .rules import read_csv
from .storage import checked_id, new_id, utc_now

METRICS = ["Page impressions", "Page clicks", "Page CTR", "Page position", "Target non-branded impressions", "Indexing / correct landing page", "Content accuracy / user experience"]


class Plan(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    why: str = Field(min_length=1, max_length=4000)
    expected_effect: str = Field(min_length=1, max_length=4000)
    measurement: str = Field(min_length=1, max_length=4000)
    metric: str
    url: str = Field(default="", max_length=2048)
    current: str = Field(default="", max_length=8000)
    proposed: str = Field(default="", max_length=8000)


def validate_plan(value, config):
    value = Plan.model_validate(value)
    if value.metric not in METRICS or any(not getattr(value, k).strip() for k in ("title", "why", "expected_effect", "measurement")):
        raise ValueError("Describe the change, reason, expected effect and measurement.")
    if value.url and not within_site(config.url, value.url):
        raise ValueError("Track a page belonging to this selected site.")
    if value.metric.startswith("Page ") and not value.url:
        raise ValueError("A page measurement needs its exact URL.")
    return value.model_dump()


def create_plan(store, sid, aid, value):
    store.require_private_write()
    audit = store.audit(sid, aid)
    value = validate_plan(value, SiteConfig.model_validate_json(audit["config"]))
    pid = new_id()
    with store.db() as db:
        db.execute("INSERT INTO change_plans VALUES (?,?,?,?,?,NULL)", (pid, sid, aid, utc_now(), json.dumps(value)))
    return pid


def plans(store, sid):
    store.site(sid)
    with store.db() as db:
        rows = db.execute("SELECT * FROM change_plans WHERE site_id=? ORDER BY created DESC,id", (sid,)).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]


def plan(store, sid, pid):
    checked_id(pid)
    found = next((p for p in plans(store, sid) if p["id"] == pid), None)
    if not found:
        raise ValueError("This plan does not belong to the selected site.")
    return found


def link_change(store, sid, pid, cid):
    store.require_private_write()
    record = plan(store, sid, pid)
    change = next((c for c in store.changes(sid) if c["id"] == checked_id(cid)), None)
    if not change:
        raise ValueError("The change record belongs to another site.")
    if record["payload"]["url"] and change["url"] != record["payload"]["url"]:
        raise ValueError("The recorded implementation must identify this exact page. A general or different-page observation cannot establish its publication date.")
    with store.db() as db:
        if db.execute("UPDATE change_plans SET change_id=? WHERE id=? AND site_id=? AND change_id IS NULL", (cid, pid, sid)).rowcount != 1:
            raise ValueError("A recorded implementation is already attached. Preserve it and create a separate plan for another change.")


def explanation(action, node_tag=""):
    """Generic hypotheses; action rationale and facts remain the saved evidence."""
    if action["kind"] == "href":
        return {"expected_effect": "Help visitors reach the intended page and make the internal navigation path clearer. A ranking or traffic increase is a hypothesis, not a promised result.",
                "metric": "Page clicks", "measurement": "Verify the exact link destination after approved publication, then compare the affected page's clicks in equal complete periods. Review indexing and other changes separately."}
    if action["kind"] == "title":
        return {"expected_effect": "Make the page's offering clearer in search results. This may improve relevance or click-through rate when the title is shown; Google may display a different title.",
                "metric": "Page CTR", "measurement": "Compare page CTR, impressions and position in equal complete reporting periods after publication. Review relevant query-to-page matches; a CTR change alone does not prove the title caused it."}
    if node_tag in ("h1", "h2", "h3"):
        return {"expected_effect": "Help visitors and search engines recognize the page's confirmed service and location. More relevant visibility is a hypothesis that needs later evidence.",
                "metric": "Page impressions", "measurement": "Compare this page's impressions in equal complete periods, then check relevant queries, landing-page alignment and clicks. Account for other changes and seasonal demand."}
    return {"expected_effect": "Improve the accuracy or clarity of the wording for readers. This is not an established ranking benefit and factual review is still required.",
            "metric": "Content accuracy / user experience", "measurement": "Confirm the wording with the responsible business owner or clinician and review the published context. Record that review separately from SEO traffic outcomes."}


def _window(audit):
    manifest = json.loads(audit["manifest"])
    if manifest.get("stages", {}).get("gsc_current", {}).get("status") != "complete":
        raise ValueError("This audit does not have a complete current Google data collection.")
    window = manifest["windows"]["current"]
    meta = manifest["stages"]["gsc_current"].get("metadata", {})
    if meta.get("data_state") != "final" or meta.get("search_type") != "web" or meta.get("start") != window["start"] or meta.get("end") != window["end"] or meta.get("timezone") != "America/Los_Angeles":
        raise ValueError("Complete final web-search metadata must match the saved reporting window.")
    start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
    if start > end or manifest["windows"].get("timezone") != "America/Los_Angeles":
        raise ValueError("The Google reporting dates could not be validated.")
    return {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1, "timezone": "America/Los_Angeles", "synthetic": bool(manifest.get("synthetic"))}


def _value(store, sid, aid, payload, config):
    field = {"Page clicks": "clicks", "Page impressions": "impressions", "Page CTR": "ctr", "Page position": "position", "Target non-branded impressions": "impressions"}[payload["metric"]]
    source = "gsc_pages.csv" if payload["metric"].startswith("Page ") else "gsc_queries.csv"
    frame = read_csv(store.audit_file(sid, aid, "data", source))
    if source == "gsc_pages.csv":
        if "page" not in frame:
            raise ValueError("Page rows are unavailable in this audit.")
        selected = frame[frame["page"].eq(payload["url"])]
    else:
        if "query" not in frame or not config.brand_aliases or not any(p.active for p in config.phrases):
            raise ValueError("Non-branded measurement requires configured brand names, active targets and visible query data.")
        matched = frame["query"].map(lambda q: classify(q, config))
        selected = frame[matched.map(lambda m: bool(m["groups"]) and not m["branded"])]
    if selected.empty:
        raise ValueError("No matching visible rows were returned. Missing rows mean unavailable evidence, not zero performance.")
    for column in ("clicks", "impressions", "position"):
        if column not in selected or any(not math.isfinite(float(v)) or float(v) < 0 for v in selected[column]):
            raise ValueError("Saved performance values could not be validated.")
    dimension = "page" if source == "gsc_pages.csv" else "query"
    if selected[dimension].duplicated().any():
        raise ValueError("Repeated dimension rows cannot be safely aggregated for this measurement.")
    value = totals(selected)[field]
    if value is None or not math.isfinite(value):
        raise ValueError("This metric is unavailable in the saved rows.")
    return {"value": value, "file": source, "aggregation": "byPage" if source == "gsc_pages.csv" else "byProperty query rows", "visible_rows": len(selected)}


def compare(store, sid, pid, followup_aid):
    record = plan(store, sid, pid)
    baseline = store.audit(sid, record["audit_id"])
    followup = store.audit(sid, followup_aid)  # Always validate site even when not ready.
    payload = record["payload"]
    if not record["change_id"]:
        return {"status": "not ready", "reason": "No published implementation has been recorded for this plan. Local previews cannot produce live SEO results."}
    change = next((c for c in store.changes(sid) if c["id"] == record["change_id"]), None)
    if not change:
        raise ValueError("The implementation record could not be located for this site.")
    if payload["metric"] in METRICS[-2:]:
        return {"status": "manual review", "reason": "This outcome needs direct inspection or factual review. Traffic metrics cannot verify it."}
    try:
        before_window, after_window = _window(baseline), _window(followup)
        publication = date.fromisoformat(change["date"])
        if before_window["synthetic"] != after_window["synthetic"]:
            raise ValueError("Synthetic and live evidence cannot be compared.")
        if before_window["days"] != after_window["days"]:
            raise ValueError("Choose equal-length reporting windows.")
        if not date.fromisoformat(before_window["end"]) < publication < date.fromisoformat(after_window["start"]):
            raise ValueError("Use a baseline ending before publication and a follow-up window starting after it. Overlapping or mixed windows are not comparable.")
        config = SiteConfig.model_validate_json(baseline["config"])
        after_config = SiteConfig.model_validate_json(followup["config"])
        if config.url != after_config.url or config.gsc_property != after_config.gsc_property:
            raise ValueError("The audits use different website/property identities.")
        before = {**_value(store, sid, baseline["id"], payload, config), "window": before_window, "audit_id": baseline["id"]}
        # Freeze the baseline's target/brand definitions for both windows.
        after = {**_value(store, sid, followup["id"], payload, config), "window": after_window, "audit_id": followup["id"]}
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "unavailable", "reason": str(exc)}
    others = [{"date": c["date"], "action": c["action"], "verification": c["verification"]} for c in store.changes(sid)
              if c["id"] != change["id"] and before_window["start"] <= c["date"] <= after_window["end"]]
    return {"status": "comparable", "baseline": before, "followup": after, "difference": after["value"] - before["value"], "other_changes": others,
            "reason": "Observed association only. Publication is user-reported; demand, other edits and Google's changes may explain the difference. No automatic rule changes are made."}


def save_review(store, sid, pid, aid, notes):
    store.require_private_write()
    if not isinstance(notes, str) or not notes.strip() or len(notes) > 4000:
        raise ValueError("Record a lesson or uncertainty, up to 4,000 characters.")
    comparison = compare(store, sid, pid, aid)
    rid = new_id()
    with store.db() as db:
        db.execute("INSERT INTO result_reviews VALUES (?,?,?,?,?,?)", (rid, pid, sid, aid, utc_now(), json.dumps({"comparison": comparison, "notes": notes})))
    return rid


def reviews(store, sid, pid):
    plan(store, sid, pid)
    with store.db() as db:
        rows = db.execute("SELECT * FROM result_reviews WHERE site_id=? AND plan_id=? ORDER BY created DESC,id", (sid, pid)).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]
