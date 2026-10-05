from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Iterable

import pandas as pd
from googleapiclient.discovery import build

from .auth import get_credentials

ROW_LIMIT = 25_000

def services(secret_dir: Path):
    creds = get_credentials(secret_dir)
    searchconsole = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    return searchconsole

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
            clicks=row.get("clicks", 0),
            impressions=row.get("impressions", 0),
            ctr=row.get("ctr", 0),
            position=row.get("position", 0),
        )
        records.append(record)
    return pd.DataFrame(records, columns=dimensions + ["clicks", "impressions", "ctr", "position"])

def export_performance(
    secret_dir: Path,
    site_url: str,
    out_dir: Path,
    days: int = 90,
    lag_days: int = 3,
) -> dict:
    svc = services(secret_dir)
    if days < 1 or lag_days < 0:
        raise ValueError("days must be positive and lag_days must be nonnegative")
    end = datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=lag_days)
    start = end - timedelta(days=days - 1)
    start_s, end_s = start.isoformat(), end.isoformat()

    datasets = {
        "query_page": ["query", "page"],
        "queries": ["query"],
        "pages": ["page"],
        "daily": ["date"],
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

    return {"start": start_s, "end": end_s, "counts": counts}

def list_sitemaps(secret_dir: Path, site_url: str) -> list[dict]:
    svc = services(secret_dir)
    return svc.sitemaps().list(siteUrl=site_url).execute().get("sitemap", [])

def inspect_urls(
    secret_dir: Path,
    site_url: str,
    urls: Iterable[str],
    out_path: Path,
    limit: int = 100,
) -> int:
    creds = get_credentials(secret_dir)
    inspection = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
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
        except Exception as exc:
            records.append({"url": url, "error": str(exc)})
    pd.DataFrame(records).to_csv(out_path, index=False)
    return len(records)
