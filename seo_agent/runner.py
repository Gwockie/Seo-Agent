"""One read-only runner, used by CLI and UI; explicit context and bounded jobs."""
from __future__ import annotations
import json
import os
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import pandas as pd

from .analysis import build_opportunities
from .config import SiteConfig, resolve_rules, within_site, validate_property
from .crawl import crawl
from .credentials import load_connection
from .gsc import export_performance, inspect_urls, list_sitemaps, service_for_credentials, validate_access
from .metrics import windows
from .protection import require_protected
from .rules import generate, read_csv, write_reports
from .storage import Store, new_id, config_hash, utc_now

GLOBAL_LOCK = Path(__file__).resolve().parent.parent / ".tmp" / "audit.lock"


@dataclass(frozen=True)
class AuditContext:
    site_id: str
    audit_id: str
    config: SiteConfig
    data_dir: Path
    reports_dir: Path
    days: int = 28
    lag_days: int = 3
    max_pages: int = 50
    inspect: bool = True
    inspect_limit: int = 20


@contextmanager
def run_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("An audit is already running; wait for it to finish") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def run_snapshot(context: AuditContext, svc, *, progress=None, crawl_fn=crawl):
    """External caller must validate connection/property/protected storage first.

    All network stages here are read-only. A failed stage is recorded without
    placing exception text or HTTP response bodies into any artifact.
    """
    ctx = context
    if not 1 <= ctx.max_pages <= 200 or not 1 <= ctx.inspect_limit <= 100:
        raise ValueError("Invalid bounded audit settings")
    window = windows(ctx.days, ctx.lag_days)
    if any(p.exists() and (not p.is_dir() or any(p.iterdir())) for p in (ctx.data_dir, ctx.reports_dir)):
        raise ValueError("Audit output must be empty; historical or partial evidence cannot be overwritten")
    resolved = resolve_rules(ctx.config)
    stages = {}
    manifest = {"schema_version": 1, "site_id": ctx.site_id, "audit_id": ctx.audit_id, "created_utc": utc_now(),
        "site": ctx.config.gsc_property, "url": ctx.config.url, "config": ctx.config.model_dump(), "resolved": resolved,
        "config_hash": config_hash(ctx.config), "windows": window, "stages": stages, "status": "running"}
    ctx.data_dir.mkdir(parents=True, exist_ok=True)
    ctx.reports_dir.mkdir(parents=True, exist_ok=True)

    def stage(name, fn):
        if progress:
            progress(name)
        try:
            value = fn()
            stages[name] = {"status": "complete", "finished_utc": utc_now()}
            return value
        except Exception:
            stages[name] = {"status": "failed", "message": "Source unavailable; check selected account, property, network, quota and destination boundaries.", "finished_utc": utc_now()}
            return None

    for period, dates in (("gsc_current", window["current"]), ("gsc_previous", window["previous"])):
        destination = ctx.data_dir if period == "gsc_current" else ctx.data_dir / "comparison"
        if svc is not None:
            meta = stage(period, lambda d=destination, dates=dates: export_performance(None, ctx.config.gsc_property, d, ctx.days, ctx.lag_days, svc=svc, start_date=dates["start"], end_date=dates["end"]))
            if meta:
                stages[period]["metadata"] = meta
                if not meta["counts"].get("totals"):
                    stages[period]["observation"] = "empty export; demand unknown"
        else:
            stages[period] = {"status": "unavailable", "message": "No authorized Google connection; performance unknown"}
    if svc is not None:
        def sitemaps():
            records = list_sitemaps(None, ctx.config.gsc_property, svc=svc)
            (ctx.data_dir / "gsc_sitemaps.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        stage("sitemaps", sitemaps)
    crawled = stage("crawl", lambda: crawl_fn(ctx.config.url, ctx.data_dir / "crawl.csv", max_pages=ctx.max_pages, config=ctx.config, progress=progress))
    if crawled is not None and not crawled.empty and "status" in crawled:
        if crawled.status.astype(str).isin(["request_error"]).any():
            stages["crawl"]["status"] = "partial"
    if ctx.inspect and svc is not None:
        priorities = list(dict.fromkeys(p.landing_page for p in ctx.config.phrases if p.active and p.landing_page))
        other = [] if crawled is None or "final_url" not in crawled else crawled.loc[crawled["status"].astype(str).eq("200"), "final_url"].dropna().tolist()
        urls = [u for u in dict.fromkeys(priorities + other) if within_site(ctx.config.url, u)]
        scoped = []
        for url in urls:
            try:
                validate_property(ctx.config.gsc_property, url)
                scoped.append(url)
            except ValueError:
                pass
        urls = scoped
        stage("inspection", lambda: inspect_urls(None, ctx.config.gsc_property, urls, ctx.data_dir / "url_inspection.csv", limit=ctx.inspect_limit, svc=svc))
        inspected = read_csv(ctx.data_dir / "url_inspection.csv")
        if not inspected.empty and "error" in inspected and inspected.error.astype(str).ne("").any():
            stages["inspection"]["status"] = "partial"
    else:
        stages["inspection"] = {"status": "unavailable", "message": "Inspection disabled or no authorized connection"}
    # Never use a partially collected performance stage for conclusions.
    frames = {"crawl": read_csv(ctx.data_dir / "crawl.csv"), "url_inspection": read_csv(ctx.data_dir / "url_inspection.csv")}
    if stages.get("gsc_current", {}).get("status") == "complete":
        frames["gsc_query_page"] = read_csv(ctx.data_dir / "gsc_query_page.csv")
        opp = build_opportunities(ctx.data_dir, ctx.config)
        opp.to_csv(ctx.data_dir / "opportunities.csv", index=False)
    findings = generate(ctx.config, ctx.site_id, ctx.audit_id, frames, resolved)
    statuses = [s["status"] for s in stages.values()]
    manifest["status"] = "complete" if all(s == "complete" for s in statuses if s != "unavailable") and stages["gsc_current"]["status"] == "complete" else "partial" if "complete" in statuses else "failed"
    manifest["finished_utc"] = utc_now()
    write_reports(ctx.config, ctx.site_id, ctx.audit_id, ctx.data_dir, ctx.reports_dir, findings, manifest)
    (ctx.data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest, findings


def run_site(store: Store, site_id, *, request_id=None, expected_config_hash=None, demo=False, progress=None, **settings):
    windows(settings.get("days", 28), settings.get("lag_days", 3))
    if not 1 <= settings.get("max_pages", 50) <= 200 or not 1 <= settings.get("inspect_limit", 20) <= 100:
        raise ValueError("Invalid bounded audit settings")
    aid = request_id or new_id()
    with run_lock(GLOBAL_LOCK):
        prior = [r for r in store.audits(site_id) if r["id"] == aid]
        if prior:
            return aid  # Persistent request ID is idempotent across UI reruns.
        config = store.site(site_id)
        if expected_config_hash and config_hash(config) != expected_config_hash:
            raise ValueError("Site configuration changed before launch; review settings and run again")
        if demo:
            from .demo import SyntheticService, synthetic_crawl
            svc, crawl_fn = SyntheticService(config), synthetic_crawl
        else:
            require_protected(store.root)
            if not config.connection_id:
                raise ValueError("Choose an authorized Google connection for this site")
            store.connection(config.connection_id)
            svc = service_for_credentials(load_connection(config.connection_id))
            validate_access(svc, config.gsc_property, config.url)
            crawl_fn = crawl
        store.create_audit(site_id, audit_id=aid)
        data = store.audit_file(site_id, aid, "data", "manifest.json").parent
        reports = store.audit_file(site_id, aid, "reports", "snapshot.md").parent
        context = AuditContext(site_id, aid, config, data, reports, **settings)
        try:
            manifest, findings = run_snapshot(context, svc, progress=progress, crawl_fn=crawl_fn)
            manifest["synthetic"] = demo
            if demo:
                (data / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            store.save_findings(site_id, aid, findings)
            store.finish_audit(site_id, aid, manifest["status"], manifest)
        except Exception:
            manifest = {"status": "failed", "synthetic": demo, "message": "Audit could not complete. Preserved stages are diagnostic only."}
            store.finish_audit(site_id, aid, "failed", manifest)
            raise ValueError("Audit failed; preserved partial evidence is available in history") from None
        return aid


class Jobs:
    """One process-local worker; file lock also excludes CLI/other app processes."""
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="seo-audit")
        self.guard = Lock()
        self.current = None
        self.records = {}

    def submit(self, store, sid, request_id, **kwargs):
        key = (str(store.root), sid, request_id)
        with self.guard:
            if key in self.records:
                return key
            if self.current and not self.records[self.current]["future"].done():
                raise ValueError("An audit is already running")
            snapshot_hash = config_hash(store.site(sid))
            record = {"site_id": sid, "request_id": request_id, "progress": "Queued"}
            self.records[key] = record
            self.current = key
            def update(message):
                with self.guard:
                    record["progress"] = str(message)[:200]
            record["future"] = self.executor.submit(run_site, store, sid, request_id=request_id, expected_config_hash=snapshot_hash, progress=update, **kwargs)
        return key

    def snapshot(self, key):
        with self.guard:
            record = self.records.get(key)
            if not record:
                return None
            result = {"site_id": record["site_id"], "progress": record["progress"], "done": record["future"].done()}
            if result["done"]:
                try:
                    result["audit_id"] = record["future"].result()
                except Exception:
                    result["error"] = "Audit unavailable or failed. Check secure storage, connection, property and preserved history."
            return result

    def busy(self):
        with self.guard:
            return bool(self.current and not self.records[self.current]["future"].done())
