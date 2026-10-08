"""Consistent within-dataset math; no query totals masquerading as property totals."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd


def windows(days=28, lag_days=3, *, today=None):
    if not 1 <= days <= 90 or not 3 <= lag_days <= 14:
        raise ValueError("Use 1–90 days and a 3–14 day final-data lag")
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    end = today - timedelta(days=lag_days)
    start = end - timedelta(days=days - 1)
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=days - 1)
    return {"current": {"start": start.isoformat(), "end": end.isoformat()}, "previous": {"start": prior_start.isoformat(), "end": prior_end.isoformat()}, "days": days, "timezone": "America/Los_Angeles", "lag_days": lag_days}


def totals(df: pd.DataFrame):
    if df.empty or not {"clicks", "impressions", "position"}.issubset(df.columns):
        return {"available": False, "clicks": None, "impressions": None, "ctr": None, "position": None}
    clicks = pd.to_numeric(df.clicks, errors="raise").sum()
    impressions = pd.to_numeric(df.impressions, errors="raise").sum()
    if clicks < 0 or impressions < 0:
        raise ValueError("Invalid negative GSC metrics")
    return {"available": True, "clicks": float(clicks), "impressions": float(impressions), "ctr": float(clicks / impressions) if impressions else None,
            "position": float((pd.to_numeric(df.position, errors="raise") * pd.to_numeric(df.impressions, errors="raise")).sum() / impressions) if impressions else None}


def classify(query, config):
    from .config import service_terms
    text = str(query).casefold()
    exact, groups = [], set()
    for p in config.phrases:
        if not p.active:
            continue
        if p.phrase.casefold() == text.strip():
            exact.append(p.phrase)
        terms = [p.phrase, *p.related_terms, *service_terms(config, p.group)]
        if any(term.casefold() in text for term in terms):
            groups.add(p.group)
    return {"exact": exact, "groups": sorted(groups), "branded": any(alias.casefold() in text for alias in config.brand_aliases)}


def query_groups(df, config):
    if df.empty or "query" not in df:
        return pd.DataFrame(columns=["group", "clicks", "impressions", "ctr", "position", "visible_queries"])
    rows = []
    classifications = df["query"].map(lambda q: classify(q, config))
    group_names = sorted({p.group for p in config.phrases if p.active})
    for name in ["all target non-branded (deduplicated)", *group_names]:
        selected = df[classifications.map(lambda v: not v["branded"] and (bool(v["groups"]) if name.startswith("all target") else name in v["groups"]))]
        rows.append({"group": name, **totals(selected), "visible_queries": len(selected)})
    return pd.DataFrame(rows)


def exact_queries(df, config):
    rows = []
    for phrase in config.phrases:
        if phrase.active:
            selected = df[df["query"].astype(str).str.casefold().eq(phrase.phrase.casefold())] if "query" in df else pd.DataFrame()
            rows.append({"phrase": phrase.phrase, "intended_page": phrase.landing_page, "observed_visible_row": not selected.empty, **totals(selected)})
    return pd.DataFrame(rows)
