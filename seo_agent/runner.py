"""One read-only runner, used by CLI and UI; explicit context and bounded jobs."""
from __future__ import annotations
import json
import time
from contextlib import nullcontext
from .coordination import run_lock, workspace_lock
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


def save_manifest(path, manifest):
    """Atomic checkpoint with bounded recovery from Windows sharing violations."""
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for attempt in range(6):
        try:
            pending.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.05 * 2 ** attempt)  # Total backoff is 1.55 seconds.

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

    def checkpoint():
        save_manifest(ctx.data_dir / "manifest.json", manifest)

    def stage(name, fn):
        stages[name] = {"status": "running"}
        checkpoint()
        if progress:
            progress(name)
        try:
            value = fn()
            stages[name] = {"status": "complete", "finished_utc": utc_now()}
            return value
        except Exception as exc:
            from .gsc import AccessError
            from .credentials import ConnectionError
            category = "access" if isinstance(exc, AccessError) else exc.category if isinstance(exc, ConnectionError) else "source_unavailable"
            message = "Public website crawl unavailable; check robots.txt, bot protection, network and destination boundaries." if name == "crawl" else "Source unavailable; check selected account, property, network, quota and destination boundaries."
            stages[name] = {"status": "failed", "category": category, "message": message, "finished_utc": utc_now()}
            if getattr(exc, "retry_after_seconds", None):
                stages[name]["retry_after_seconds"] = exc.retry_after_seconds
            return None
        finally:
            checkpoint()

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
    if crawled is not None:
        priorities = {p.landing_page for p in ctx.config.phrases if p.active and p.landing_page}
        seen = set(crawled.get("url", []))
        stage_crawl = stages["crawl"]
        stage_crawl["page_count"] = len(crawled)
        stage_crawl["missing_priority_count"] = len(priorities - seen)
        if not crawled.empty and "status" in crawled:
            statuses = crawled.status.astype(str)
            unavailable = statuses.ne("200")
            if "title" in crawled:
                unavailable |= crawled.title.fillna("").eq("")
            else:
                unavailable |= True
            stage_crawl["content_page_count"] = int((~unavailable).sum())
            stage_crawl["unavailable_page_count"] = int(unavailable.sum())
            if "retry_after_seconds" in crawled:
                stage_crawl["retry_after_seconds"] = int(pd.to_numeric(crawled.retry_after_seconds, errors="coerce").fillna(0).max())
        else:
            stage_crawl.update(content_page_count=0, unavailable_page_count=0)
        if stage_crawl["unavailable_page_count"] or stage_crawl["missing_priority_count"] or not stage_crawl["content_page_count"]:
            stage_crawl["status"] = "partial" if stage_crawl["page_count"] else "failed"
            stage_crawl["message"] = "Bounded crawl coverage incomplete; unavailable content cannot establish indexing health."
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
        urls = scoped[:ctx.inspect_limit]
        stage("inspection", lambda: inspect_urls(None, ctx.config.gsc_property, urls, ctx.data_dir / "url_inspection.csv", limit=ctx.inspect_limit, svc=svc))
        inspected = read_csv(ctx.data_dir / "url_inspection.csv")
        stages["inspection"]["requested_count"] = len(urls)
        stages["inspection"]["result_count"] = len(inspected)
        if stages["inspection"]["status"] == "complete" and (not urls or len(inspected) != len(urls) or ("error" in inspected and inspected.error.fillna("").astype(str).ne("").any())):
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
    manifest["status"] = "complete" if all(s == "complete" for s in statuses) and stages["gsc_current"]["status"] == "complete" else "partial" if "complete" in statuses else "failed"
    manifest["finished_utc"] = utc_now()
    write_reports(ctx.config, ctx.site_id, ctx.audit_id, ctx.data_dir, ctx.reports_dir, findings, manifest)
    checkpoint()
    return manifest, findings


def run_site(store: Store, site_id, *, request_id=None, expected_config_hash=None, demo=False, progress=None, already_locked=False, **settings):
    windows(settings.get("days", 28), settings.get("lag_days", 3))
    if not 1 <= settings.get("max_pages", 50) <= 200 or not 1 <= settings.get("inspect_limit", 20) <= 100:
        raise ValueError("Invalid bounded audit settings")
    aid = request_id or new_id()
    with nullcontext() if already_locked else run_lock(workspace_lock(store.root)):
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
                save_manifest(data / "manifest.json", manifest)
            store.save_findings(site_id, aid, findings)
            store.finish_audit(site_id, aid, manifest["status"], manifest)
        except Exception:
            manifest = {}
            try:
                saved = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
                if saved.get("site_id") == site_id and saved.get("audit_id") == aid:
                    manifest = saved
            except (OSError, ValueError):
                pass
            manifest.update(status="failed", synthetic=demo, message="Audit could not complete. Preserved stages are diagnostic only.")
            store.finish_audit(site_id, aid, "failed", manifest)
            raise ValueError("Audit failed; preserved partial evidence is available in history") from None
        from .page_tracking import refresh
        from .trends import ingest_audits
        ingest_audits(store, site_id)
        refresh(store, site_id, demo=demo, audit_id=aid, progress=progress, already_locked=True)
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
                    value = record["future"].result()
                    if record.get("kind") == "tracking":
                        result["tracking"] = value
                    else:
                        result["audit_id"] = value
                except Exception:
                    result["error"] = "Audit unavailable or failed. Check secure storage, connection, property and preserved history."
            return result

    def submit_check(self, store, sid, request_id, *, manual=False, demo=False):
        from .page_tracking import refresh
        key = (str(store.root), sid, "tracking:" + request_id)
        with self.guard:
            if key in self.records:
                return key
            if self.current and not self.records[self.current]["future"].done():
                raise ValueError("An audit or tracking check is already running")
            record = {"site_id": sid, "request_id": request_id, "progress": "Queued read-only tracking check", "kind": "tracking"}
            self.records[key] = record
            self.current = key
            def update(message):
                with self.guard:
                    record["progress"] = str(message)[:200]
            record["future"] = self.executor.submit(refresh, store, sid, manual=manual, demo=demo, progress=update)
        return key

    def busy(self):
        with self.guard:
            return bool(self.current and not self.records[self.current]["future"].done())

    def submit_weekly(self, store, sid, request_id, *, demo=False):
        from . import scheduling as weekly
        key = (str(store.root), sid, "weekly:" + request_id)
        with self.guard:
            if key in self.records:
                return key
            if self.current and not self.records[self.current]["future"].done():
                raise ValueError("Another operation is running")
            def run():
                if not demo:
                    from .weekly_worker import dispatch
                    return dispatch(store.root / "weekly-installation.json", sid=sid, trigger_id=request_id)
                with run_lock(workspace_lock(store.root)):
                    weekly.reconcile(store)
                    attempt = weekly.claim(store, sid, manual=True, trigger_id=request_id)
                    if attempt:
                        aid = run_site(store, sid, request_id=attempt["request_id"], already_locked=True, demo=True,
                                       days=28, lag_days=3, max_pages=50, inspect=True, inspect_limit=20)
                        return weekly.finish(store, attempt, audit_id=aid)
            self.records[key] = {"site_id": sid, "progress": "Bounded headless worker", "kind": "tracking", "future": self.executor.submit(run)}
            self.current = key
        return key
