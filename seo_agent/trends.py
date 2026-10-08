"""Persistent final daily sources, explicit overlap provenance and unknown gaps."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from .storage import new_id, utc_now
from .tracking import action, canonical, rows
from .rules import read_csv

DATASETS = {"property": ("gsc_daily.csv", "byProperty"), "page": ("gsc_daily_pages.csv", "byPage")}


def ingest_audits(store, sid):
    store.require_private_write()
    store.site(sid)
    for audit in store.audits(sid):
        if audit["status"] == "running":
            continue
        manifest = json.loads(audit["manifest"])
        for period in ("current", "previous"):
            stage = manifest.get("stages", {}).get("gsc_" + period, {})
            window = manifest.get("windows", {}).get(period)
            meta = stage.get("metadata", {})
            if not window:
                continue
            for dataset, (filename, aggregation) in DATASETS.items():
                with store.db() as db:
                    if db.execute("SELECT 1 FROM trend_sources WHERE site_id=? AND audit_id=? AND period=? AND dataset=?", (sid, audit["id"], period, dataset)).fetchone():
                        continue
                payload = {"status": "unavailable", "window": window, "aggregation": aggregation, "filename": filename,
                    "timezone": "America/Los_Angeles", "synthetic": bool(manifest.get("synthetic")), "collected_utc": audit["created"],
                    "rows": [], "reason": "Final daily source unavailable", "top_rows_only": True}
                try:
                    start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
                    if start > end or (end - start).days > 90:
                        raise ValueError("Invalid source window")
                    if stage.get("status") != "complete" or meta.get("data_state") != "final" or meta.get("search_type") != "web" or meta.get("timezone") != "America/Los_Angeles" or meta.get("start") != start.isoformat() or meta.get("end") != end.isoformat() or manifest.get("windows", {}).get("timezone") != "America/Los_Angeles":
                        raise ValueError("Incomplete final source metadata")
                    if dataset == "page" and meta.get("daily_pages_aggregation") != "byPage":
                        raise ValueError("Page daily aggregation metadata unavailable")
                    path = store.audit_file(sid, audit["id"], "data", filename, period=period)
                    if not path.is_file() or path.stat().st_size > 40 * 1024 * 1024:
                        raise ValueError("Missing or oversized daily export")
                    raw = path.read_bytes()
                    frame = read_csv(path)
                    dimensions = ["date"] + (["page"] if dataset == "page" else [])
                    if not set(dimensions + ["clicks", "impressions", "position"]).issubset(frame.columns) or len(frame) > 50000 or frame.duplicated(dimensions).any():
                        raise ValueError("Invalid daily export shape")
                    records = []
                    from .config import within_site
                    for row in frame.to_dict("records"):
                        d = date.fromisoformat(str(row["date"]))
                        if not start <= d <= end:
                            raise ValueError("Daily row outside its source window")
                        if dataset == "page" and not within_site(store.site(sid).url, row["page"]):
                            # Property may cover more than this selected URL-prefix.
                            continue
                        values = {k: float(row[k]) for k in ("clicks", "impressions", "position")}
                        if any(not math.isfinite(v) or v < 0 for v in values.values()) or values["clicks"] > values["impressions"]:
                            raise ValueError("Invalid daily metrics")
                        records.append({**{k: row[k] for k in dimensions}, **values, "ctr": values["clicks"] / values["impressions"] if values["impressions"] else None,
                                        "position": values["position"] if values["impressions"] else None})
                    payload.update(status="complete", rows=records, sha256=hashlib.sha256(raw).hexdigest(), reason="Final daily export; absent rows remain unknown")
                except (ValueError, KeyError, TypeError, OSError):
                    pass
                with store.db() as db:
                    db.execute("INSERT OR IGNORE INTO trend_sources VALUES (?,?,?,?,?,?,?)", (new_id(), sid, audit["id"], period, dataset, utc_now(), canonical(payload)))


def series(store, sid, *, page=None, synthetic=False, days=180):
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("Trend range must be 1–365 days")
    from .config import within_site
    if page and not within_site(store.site(sid).url, page):
        raise ValueError("Page belongs to another site")
    dataset = "page" if page else "property"
    sources = [r for r in rows(store, "trend_sources", sid) if r["dataset"] == dataset and r["payload"]["synthetic"] == synthetic]
    valid = []
    for r in sources:
        try:
            date.fromisoformat(r["payload"]["window"]["start"])
            date.fromisoformat(r["payload"]["window"]["end"])
            valid.append(r)
        except (ValueError, KeyError, TypeError):
            continue
    if not valid:
        return pd.DataFrame(columns=["date", "clicks", "impressions", "ctr", "position", "source_id", "audit_id", "aggregation", "status", "segment"])
    end = max(date.fromisoformat(r["payload"]["window"]["end"]) for r in valid)
    start = max(min(date.fromisoformat(r["payload"]["window"]["start"]) for r in valid), end - timedelta(days=days - 1))
    result, segment = [], 0
    indexed = {r["id"]: {(v["date"], v.get("page")): v for v in r["payload"]["rows"]} for r in valid}
    for i in range((end - start).days + 1):
        d = (start + timedelta(days=i)).isoformat()
        covering = [r for r in valid if r["payload"]["window"]["start"] <= d <= r["payload"]["window"]["end"]]
        usable = [r for r in covering if r["payload"]["status"] == "complete"]
        # Never sum overlapping exports. Newest complete audit wins; within one
        # audit prefer current. Prior exports remain in trend_sources unchanged.
        chosen = max(usable or covering, key=lambda r: (r["payload"]["collected_utc"], r["period"] == "current", r["audit_id"])) if covering else None
        value = indexed[chosen["id"]].get((d, page)) if chosen else None
        if not value:
            segment += 1
        result.append({"date": d, **({k: value[k] for k in ("clicks", "impressions", "ctr", "position")} if value else {k: None for k in ("clicks", "impressions", "ctr", "position")}),
            "source_id": chosen["id"] if chosen else None, "audit_id": chosen["audit_id"] if chosen else None,
            "aggregation": DATASETS[dataset][1], "status": "observed" if value else "unknown / collection gap", "segment": segment,
            "overlapping_sources": len(covering), "selection": "newest complete collection; current preferred; absent rows unknown"})
    return pd.DataFrame(result)


def markers(store, sid, *, page=None):
    found = []
    for c in store.changes(sid):
        if not page or c["url"] == page:
            found.append({"id": c["id"], "date": c["date"], "label": c["action"], "type": "legacy user-reported", "url": c["url"], "detail": c})
    all_actions = {(r["action_id"], r["revision"]): r for r in rows(store, "tracking_actions", sid)}
    for r in rows(store, "implementation_receipts", sid):
        v = r["payload"]
        a = all_actions[(r["action_id"], r["revision"])]
        if v["environment"] != "production" or v["outcome"] not in {"reported_applied", "partial", "rolled_back", "correction"} or (page and a["payload"]["url"] != page):
            continue
        approval = next((p for p in rows(store, "human_approvals", sid) if p["id"] == v["approval_id"]), None)
        found.append({"id": r["id"], "date": datetime.fromisoformat(v["occurred_utc"]).astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat(),
            "label": a["payload"]["action_kind"] + " · " + v["outcome"], "type": "reported implementation", "url": a["payload"]["url"],
            "detail": {"action": a, "receipt": r, "approval": approval, "verification": [x for x in rows(store, "implementation_receipts", sid) if x["payload"]["attempt_id"] == v["attempt_id"]],
                       "reviews": [x for x in rows(store, "tracking_reviews", sid) if x["action_id"] == a["action_id"] and x["revision"] == a["revision"]]}})
    for r in rows(store, "outside_changes", sid):
        if page and r["url"] != page:
            continue
        p = r["payload"]
        found.append({"id": r["id"], "date": datetime.fromisoformat(r["first_seen"]).astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat(),
            "date_before": datetime.fromisoformat(p["last_known_before_utc"]).astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat(),
            "label": "Outside edit first observed", "type": "uncertain interval", "url": r["url"], "detail": r})
    return found


def compare_action(store, sid, identity, revision, followup_aid):
    from .learning import _window, _value
    from .config import SiteConfig
    r = action(store, sid, identity, revision)
    baseline = store.audit(sid, r["audit_id"])
    followup = store.audit(sid, followup_aid)
    receipts = [v["payload"] for v in rows(store, "implementation_receipts", sid) if v["action_id"] == identity and v["revision"] == revision and v["payload"]["environment"] == "production"]
    applied = [v for v in receipts if v["outcome"] == "reported_applied"]
    if len(applied) != 1 or any(v["outcome"] in {"partial", "rolled_back", "correction"} for v in receipts):
        return {"status": "not ready", "reason": "A single exact reported publication date is required. Outside observation intervals, partial work, corrections and rollbacks cannot establish it."}
    a = r["payload"]
    if a["primary_measure"] in ("Indexing / correct landing page", "Content accuracy / user experience"):
        return {"status": "manual review", "reason": "This outcome needs direct inspection/factual review; traffic cannot verify it."}
    try:
        before, after = _window(baseline), _window(followup)
        publication = datetime.fromisoformat(applied[0]["occurred_utc"]).astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
        if before["days"] != after["days"] or not before["end"] < publication < after["start"] or before["synthetic"] != after["synthetic"]:
            raise ValueError("Require equal complete finalized windows strictly before/after the reported publication, with compatible sources")
        c = SiteConfig.model_validate_json(baseline["config"])
        f = SiteConfig.model_validate_json(followup["config"])
        if (c.url, c.gsc_property) != (f.url, f.gsc_property):
            raise ValueError("Property identities differ")
        p = {"metric": a["primary_measure"], "url": a["url"]}
        b, e = _value(store, sid, baseline["id"], p, c), _value(store, sid, followup["id"], p, c)
        others = [m for m in markers(store, sid) if before["start"] <= m["date"] <= after["end"] and m["id"] != applied[0]["receipt_id"]]
        return {"status": "comparable", "baseline": {**b, "window": before, "audit_id": baseline["id"]}, "followup": {**e, "window": after, "audit_id": followup["id"]},
            "difference": e["value"] - b["value"], "other_changes": [{k: v for k, v in m.items() if k != "detail"} for m in others],
            "reason": "Observed association only; publication time is reported, not independently established. Other edits, competition, privacy limits and demand may explain differences. No causality or automatic rule tuning."}
    except (ValueError, KeyError, TypeError):
        return {"status": "unavailable", "reason": "Equal complete final compatible before/after sources are not available yet"}
