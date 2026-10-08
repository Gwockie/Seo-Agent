from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Iterable

import pandas as pd
from googleapiclient.discovery import build

from .auth import get_credentials
from .config import validate_property

ROW_LIMIT = 25_000

def services(secret_dir: Path):
    creds = get_credentials(secret_dir)
    return service_for_credentials(creds)


def service_for_credentials(creds):
    from .credentials import validate_credentials
    validate_credentials(creds)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def validate_access(svc, property_url, public_url):
    validate_property(property_url, public_url)
    entries = svc.sites().list().execute().get("siteEntry", [])
    if not any(r.get("siteUrl") == property_url and r.get("permissionLevel") in {"siteOwner", "siteFullUser", "siteRestrictedUser"} for r in entries):
        raise ValueError("Selected Google connection lacks access to the exact property")

def list_sites(secret_dir: Path) -> list[dict]:
    svc = services(secret_dir)
    return svc.sites().list().execute().get("siteEntry", [])

def _query_all(
    svc,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    data_state: str = "final",
) -> list[dict]:
    out = []
    start_row = 0
    while True:
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": ROW_LIMIT,
            "startRow": start_row,
            "dataState": data_state,
            "type": "web",
            "aggregationType": "byPage" if "page" in dimensions else "byProperty",
        }
        resp = svc.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows = resp.get("rows", [])
        if not rows:
            break
        out.extend(rows)
        if len(rows) < ROW_LIMIT:
            break
        start_row += ROW_LIMIT
        # Search Console exposes top rows and has its own data limits; this prevents
        # accidental runaway querying while still paging the documented API.
        if start_row >= 50_000:
            break
    return out

def rows_to_df(rows: list[dict], dimensions: list[str]) -> pd.DataFrame:
    records = []
    for row in rows:
        record = dict(zip(dimensions, row.get("keys", [])))
        record.update(
            clicks=row.get("clicks"),
            impressions=row.get("impressions"),
            ctr=row.get("ctr"),
            position=row.get("position"),
        )
        records.append(record)
    return pd.DataFrame(records, columns=dimensions + ["clicks", "impressions", "ctr", "position"])

def export_performance(
    secret_dir: Path,
    site_url: str,
    out_dir: Path,
    days: int = 90,
    lag_days: int = 3,
    *, svc=None, start_date=None, end_date=None,
) -> dict:
    svc = svc or services(secret_dir)
    if days < 1 or lag_days < 0:
        raise ValueError("days must be positive and lag_days must be nonnegative")
    end = datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=lag_days)
    start = end - timedelta(days=days - 1)
    start_s, end_s = start_date or start.isoformat(), end_date or end.isoformat()

    datasets = {
        "totals": [],
        "query_page": ["query", "page"],
        "queries": ["query"],
        "pages": ["page"],
        "daily": ["date"],
        "daily_pages": ["date", "page"],
        "device": ["device"],
        "country": ["country"],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, dims in datasets.items():
        rows = _query_all(svc, site_url, start_s, end_s, dims)
        df = rows_to_df(rows, dims)
        df.to_csv(out_dir / f"gsc_{name}.csv", index=False)
        counts[name] = len(df)

    pd.DataFrame([{
        "site_url": site_url,
        "start_date": start_s,
        "end_date": end_s,
        "days": days,
        "lag_days": lag_days,
    }]).to_csv(out_dir / "gsc_window.csv", index=False)

    return {"start": start_s, "end": end_s, "counts": counts, "data_state": "final", "search_type": "web", "timezone": "America/Los_Angeles", "row_limit": 50000, "aggregation": "byPage for page dimensions; otherwise byProperty", "daily_pages_aggregation": "byPage", "top_rows_only": True}

def list_sitemaps(secret_dir: Path, site_url: str, *, svc=None) -> list[dict]:
    svc = svc or services(secret_dir)
    return svc.sitemaps().list(siteUrl=site_url).execute().get("sitemap", [])

def inspect_urls(
    secret_dir: Path,
    site_url: str,
    urls: Iterable[str],
    out_path: Path,
    limit: int = 100,
    *, svc=None,
) -> int:
    inspection = svc or services(secret_dir)
    records = []
    for i, url in enumerate(dict.fromkeys(urls)):
        if i >= limit:
            break
        try:
            resp = inspection.urlInspection().index().inspect(
                body={
                    "inspectionUrl": url,
                    "siteUrl": site_url,
                    "languageCode": "en-US",
                }
            ).execute()
            result = resp.get("inspectionResult", {})
            idx = result.get("indexStatusResult", {})
            records.append({
                "url": url,
                "verdict": idx.get("verdict"),
                "coverage_state": idx.get("coverageState"),
                "robots_txt_state": idx.get("robotsTxtState"),
                "indexing_state": idx.get("indexingState"),
                "last_crawl_time": idx.get("lastCrawlTime"),
                "page_fetch_state": idx.get("pageFetchState"),
                "google_canonical": idx.get("googleCanonical"),
                "user_canonical": idx.get("userCanonical"),
                "crawled_as": idx.get("crawledAs"),
                "referring_urls": " | ".join(idx.get("referringUrls", [])),
            })
        except Exception:
            records.append({"url": url, "error": "Google inspection unavailable; check access/quota/connectivity"})
    pd.DataFrame(records, columns=["url", "verdict", "coverage_state", "robots_txt_state", "indexing_state", "last_crawl_time", "page_fetch_state", "google_canonical", "user_canonical", "crawled_as", "referring_urls", "error"]).to_csv(out_path, index=False)
    return len(records)
