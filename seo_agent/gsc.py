from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Iterable

import pandas as pd
from googleapiclient.discovery import build
import httplib2
import google_auth_httplib2
import time
from email.utils import parsedate_to_datetime
from datetime import timezone

from .auth import get_credentials
from .config import validate_property

ROW_LIMIT = 25_000


class AccessError(ValueError):
    pass


class RetryDeferredError(ValueError):
    def __init__(self, seconds):
        self.retry_after_seconds = max(0, int(seconds))
        super().__init__("Google retry deferred until the server's Retry-After")


def execute(request):
    """At most three calls; Retry-After beyond one minute defers to job retry."""
    from googleapiclient.errors import HttpError
    for attempt in range(3):
        try:
            return request.execute()
        except HttpError as exc:
            code = int(exc.resp.status)
            if code in (401, 403) and b'quota' not in exc.content.lower() and b'ratelimit' not in exc.content.lower():
                raise AccessError("Exact read-only property access unavailable; reconnect selected connection") from None
            if code not in (403, 429, 500, 502, 503, 504):
                raise ValueError("Google source temporarily unavailable") from None
            delay = 2 ** attempt
            raw = exc.resp.get("retry-after")
            if raw:
                try:
                    delay = max(delay, int(raw))
                except ValueError:
                    try:
                        delay = max(delay, (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError):
                        raise ValueError("Invalid retry policy") from None
            if delay > 60:
                raise RetryDeferredError(delay) from None
            if attempt == 2:
                raise ValueError("Google source temporarily unavailable") from None
            time.sleep(delay)
        except (OSError, httplib2.HttpLib2Error):
            if attempt == 2:
                raise ValueError("Google network unavailable") from None
            time.sleep(2 ** attempt)


def services(secret_dir: Path):
    creds = get_credentials(secret_dir)
    return service_for_credentials(creds)


def service_for_credentials(creds):
    from .credentials import validate_credentials
    validate_credentials(creds)
    http = httplib2.Http(timeout=20)
    transport = google_auth_httplib2.AuthorizedHttp(creds, http=http)
    return build("searchconsole", "v1", http=transport, cache_discovery=False)


def validate_access(svc, property_url, public_url):
    validate_property(property_url, public_url)
    entries = execute(svc.sites().list()).get("siteEntry", [])
    if not any(r.get("siteUrl") == property_url and r.get("permissionLevel") in {"siteOwner", "siteFullUser", "siteRestrictedUser"} for r in entries):
        raise AccessError("Selected Google connection lacks access to the exact property")

def list_sites(secret_dir: Path) -> list[dict]:
    svc = services(secret_dir)
    return execute(svc.sites().list()).get("siteEntry", [])

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
        resp = execute(svc.searchanalytics().query(siteUrl=site_url, body=body))
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
    return execute(svc.sitemaps().list(siteUrl=site_url)).get("sitemap", [])

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
            resp = execute(inspection.urlInspection().index().inspect(
                body={
                    "inspectionUrl": url,
                    "siteUrl": site_url,
                    "languageCode": "en-US",
                }
            ))
            result = resp.get("inspectionResult", {})
            idx = result.get("indexStatusResult", {})
            if not idx:
                raise ValueError("Inspection source missing")
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
        except (AccessError, RetryDeferredError):
            raise
        except Exception as exc:
            from .credentials import ConnectionError
            if isinstance(exc, ConnectionError):
                raise
            records.append({"url": url, "error": "Google inspection unavailable; check access/quota/connectivity"})
        finally:
            pd.DataFrame(records, columns=["url", "verdict", "coverage_state", "robots_txt_state", "indexing_state", "last_crawl_time", "page_fetch_state", "google_canonical", "user_canonical", "crawled_as", "referring_urls", "error"]).to_csv(out_path, index=False)
    return len(records)
