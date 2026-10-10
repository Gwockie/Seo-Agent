"""Site-scoped metadata and checked file paths. SQLite contains no credentials."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager, nullcontext, closing
from .coordination import run_lock, workspace_lock
from datetime import datetime, timezone
from pathlib import Path

from .config import SiteConfig, resolve_rules


def new_id() -> str:
    return uuid.uuid4().hex


def checked_id(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Invalid generated record ID")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def historical_date(value: str) -> str:
    """Normalize imported collection time in metadata; source manifests stay intact."""
    try:
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Historical collection date is invalid") from None
        if parsed.tzinfo is None:
            raise ValueError("Historical collection date must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def config_hash(config: SiteConfig) -> str:
    return hashlib.sha256(json.dumps(config.model_dump(), sort_keys=True).encode()).hexdigest()


def child_path(root: Path, *parts: str) -> Path:
    root = root.resolve()
    path = root.joinpath(*parts).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Path is outside the selected workspace")
    return path


def private_location(path: Path) -> Path:
    path = path.resolve()
    repo = Path(__file__).resolve().parent.parent
    if path.is_relative_to(repo) and not any(path.is_relative_to(repo / name) for name in ("workspace", ".tmp", "backups")):
        raise ValueError("Private app artifacts inside this repo must use an ignored workspace, backups or scratch directory")
    return path


def credential_location(path: Path) -> Path:
    path = path.resolve()
    repo = Path(__file__).resolve().parent.parent
    if path.is_relative_to(repo / "secrets"):
        return path
    return private_location(path)


SCHEMA = """
CREATE TABLE IF NOT EXISTS connections(id TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, config TEXT NOT NULL, config_hash TEXT NOT NULL,
 connection_id TEXT REFERENCES connections(id));
CREATE TABLE IF NOT EXISTS target_phrases(site_id TEXT NOT NULL REFERENCES sites(id), phrase TEXT NOT NULL, config TEXT NOT NULL,
 PRIMARY KEY(site_id,phrase));
CREATE TABLE IF NOT EXISTS audits(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id), created TEXT NOT NULL,
 status TEXT NOT NULL, config TEXT NOT NULL, resolved TEXT NOT NULL, data_path TEXT NOT NULL, reports_path TEXT NOT NULL,
 legacy INTEGER NOT NULL DEFAULT 0, manifest TEXT NOT NULL DEFAULT '{}', UNIQUE(id,site_id));
CREATE TABLE IF NOT EXISTS recommendations(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, audit_id TEXT NOT NULL,
 payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'proposed',
 FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id));
CREATE TABLE IF NOT EXISTS change_events(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id), date TEXT NOT NULL,
 action TEXT NOT NULL, url TEXT NOT NULL, prior_value TEXT NOT NULL, proposed_value TEXT NOT NULL,
 approval_reference TEXT NOT NULL, evidence TEXT NOT NULL, verification TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS change_plans(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, audit_id TEXT NOT NULL,
 created TEXT NOT NULL, payload TEXT NOT NULL, change_id TEXT REFERENCES change_events(id),
 FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id), UNIQUE(id,site_id));
CREATE TABLE IF NOT EXISTS result_reviews(id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES change_plans(id),
 site_id TEXT NOT NULL, audit_id TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id), FOREIGN KEY(plan_id,site_id) REFERENCES change_plans(id,site_id));
"""

# Additive migration: old journals and evidence are never rewritten.
TRACKING_TABLES = {"tracking_actions", "handoff_imports", "publication_batches", "human_approvals",
                   "implementation_receipts", "public_snapshots", "outside_changes", "tracking_checks",
                   "tracking_settings", "trend_sources", "tracking_reviews", "approval_invalidations"}
TRACKING_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracking_actions(action_id TEXT NOT NULL, site_id TEXT NOT NULL,
 revision INTEGER NOT NULL, audit_id TEXT NOT NULL, plan_id TEXT, created TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(action_id,site_id,revision),
 FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id),
 FOREIGN KEY(plan_id,site_id) REFERENCES change_plans(id,site_id));
CREATE TABLE IF NOT EXISTS handoff_imports(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, audit_id TEXT NOT NULL,
 digest TEXT NOT NULL UNIQUE, created TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id));
CREATE TABLE IF NOT EXISTS publication_batches(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 created TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(id,site_id));
CREATE TABLE IF NOT EXISTS human_approvals(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, batch_id TEXT NOT NULL,
 created TEXT NOT NULL, payload TEXT NOT NULL, FOREIGN KEY(batch_id,site_id) REFERENCES publication_batches(id,site_id));
CREATE TABLE IF NOT EXISTS implementation_receipts(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, action_id TEXT NOT NULL,
 revision INTEGER NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(action_id,site_id,revision) REFERENCES tracking_actions(action_id,site_id,revision));
CREATE TABLE IF NOT EXISTS approval_invalidations(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, approval_id TEXT NOT NULL
 REFERENCES human_approvals(id), action_id TEXT NOT NULL, revision INTEGER NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(action_id,site_id,revision) REFERENCES tracking_actions(action_id,site_id,revision));
CREATE TABLE IF NOT EXISTS public_snapshots(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 url TEXT NOT NULL, checked TEXT NOT NULL, status TEXT NOT NULL, audit_id TEXT, payload TEXT NOT NULL,
 FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id));
CREATE TABLE IF NOT EXISTS outside_changes(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 url TEXT NOT NULL, first_seen TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tracking_checks(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 started TEXT NOT NULL, finished TEXT, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tracking_settings(site_id TEXT PRIMARY KEY REFERENCES sites(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trend_sources(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, audit_id TEXT NOT NULL,
 period TEXT NOT NULL, dataset TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(site_id,audit_id,period,dataset), FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id));
CREATE TABLE IF NOT EXISTS tracking_reviews(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, action_id TEXT NOT NULL,
 revision INTEGER NOT NULL, audit_id TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(action_id,site_id,revision) REFERENCES tracking_actions(action_id,site_id,revision),
 FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id));
PRAGMA user_version=2;
"""


SCHEDULING_TABLES = {"weekly_schedules", "weekly_attempts"}
SCHEDULING_SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_schedules(site_id TEXT PRIMARY KEY REFERENCES sites(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS weekly_attempts(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id),
 scheduled TEXT NOT NULL, started TEXT NOT NULL, finished TEXT, request_id TEXT NOT NULL UNIQUE,
 audit_id TEXT, payload TEXT NOT NULL, FOREIGN KEY(audit_id,site_id) REFERENCES audits(id,site_id));
PRAGMA user_version=3;
"""

EVALUATION_TABLES = {"proposal_evaluations"}
EVALUATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposal_evaluations(id TEXT PRIMARY KEY, site_id TEXT NOT NULL,
 action_id TEXT NOT NULL, revision INTEGER NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL,
 FOREIGN KEY(action_id,site_id,revision) REFERENCES tracking_actions(action_id,site_id,revision));
PRAGMA user_version=4;
"""


class Store:
    def __init__(self, root: Path, *, legacy_root: Path | None = None, enforce_protection=False, already_locked=False):
        self.enforce_protection = enforce_protection
        self.root = private_location(root)
        self.initial_protection = None
        existed = self.root.exists()
        if self.enforce_protection:
            from .protection import require_protected, existing_ancestor
            # Gate even empty directory/database creation, not only saved profiles.
            self.initial_protection = require_protected(existing_ancestor(self.root))
        self.root.mkdir(parents=True, exist_ok=True)
        if self.enforce_protection and not existed:
            # A newly created root needs its own check before database creation.
            self.initial_protection = require_protected(self.root)
        self.legacy_root = (legacy_root or Path(__file__).resolve().parent.parent).resolve()
        self.db_path = child_path(self.root, "app.sqlite")
        # Read-only fast path for current workspaces; never migrate ahead of the gate.
        current = False
        if self.db_path.exists():
            with closing(sqlite3.connect(f"{self.db_path.as_uri()}?mode=ro", uri=True)) as check:
                current = check.execute("PRAGMA user_version").fetchone()[0] == 4
        if not current:
            with nullcontext() if already_locked else run_lock(workspace_lock(self.root)):
                with self.db() as db:
                    version = db.execute("PRAGMA user_version").fetchone()[0]
                    if version not in (0, 1, 2, 3, 4):
                        raise ValueError("Unsupported workspace schema version")
                    db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + TRACKING_SCHEMA + SCHEDULING_SCHEMA + EVALUATION_SCHEMA + "\nCOMMIT;")

    def require_private_write(self):
        if self.enforce_protection:
            from .protection import require_protected
            require_protected(self.root)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_connection(self, label: str, connection_id: str | None = None) -> str:
        self.require_private_write()
        cid = checked_id(connection_id) if connection_id else new_id()
        if not label.strip() or len(label) > 150:
            raise ValueError("Connection label must be 1–150 characters")
        with self.db() as db:
            db.execute("INSERT INTO connections VALUES (?,?) ON CONFLICT(id) DO UPDATE SET label=excluded.label", (cid, label))
        return cid

    def connections(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM connections ORDER BY label")]

    def connection(self, cid: str):
        with self.db() as db:
            row = db.execute("SELECT * FROM connections WHERE id=?", (checked_id(cid),)).fetchone()
        if row is None:
            raise ValueError("Unknown connection; no fallback account is available")
        return dict(row)

    def save_site(self, config: SiteConfig, site_id: str | None = None) -> str:
        self.require_private_write()
        # Revalidate instances as well as user imports.
        config = SiteConfig.model_validate(config.model_dump())
        sid = checked_id(site_id) if site_id else new_id()
        if config.connection_id:
            self.connection(config.connection_id)
        with self.db() as db:
            old = db.execute("SELECT config FROM sites WHERE id=?", (sid,)).fetchone()
            if old:
                identity = SiteConfig.model_validate_json(old[0])
                if identity.url != config.url or identity.gsc_property != config.gsc_property:
                    raise ValueError("Site URL/property identity is immutable; add a separate site for a different property/URL")
            db.execute("INSERT INTO sites VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, config=excluded.config, config_hash=excluded.config_hash, connection_id=excluded.connection_id", (sid, config.name, config.model_dump_json(), config_hash(config), config.connection_id))
            db.execute("DELETE FROM target_phrases WHERE site_id=?", (sid,))
            db.executemany("INSERT INTO target_phrases VALUES (?,?,?)", [(sid, p.phrase, p.model_dump_json()) for p in config.phrases])
        return sid

    def sites(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT id,name,config_hash FROM sites ORDER BY name,id")]

    def site(self, sid: str) -> SiteConfig:
        with self.db() as db:
            row = db.execute("SELECT config FROM sites WHERE id=?", (checked_id(sid),)).fetchone()
        if row is None:
            raise ValueError("Unknown site")
        return SiteConfig.model_validate_json(row[0])

    def create_audit(self, sid: str, *, audit_id: str | None = None, legacy_paths=None, created=None) -> str:
        self.require_private_write()
        config = self.site(sid)
        aid = checked_id(audit_id) if audit_id else new_id()
        with self.db() as db:
            if db.execute("SELECT id FROM audits WHERE id=?", (aid,)).fetchone():
                raise ValueError("Audit ID is already registered; explicit site/audit relationship required")
        if legacy_paths:
            data, reports = (Path(p).resolve() for p in legacy_paths)
            if not data.is_relative_to(self.legacy_root / "data") or not reports.is_relative_to(self.legacy_root / "reports"):
                raise ValueError("Legacy paths must be under the original data/reports directories")
            if not data.is_dir() or not reports.is_dir():
                raise ValueError("Legacy evidence and reports directories must exist")
            if data.parent != self.legacy_root / "data" or reports.parent != self.legacy_root / "reports" or data.name != reports.name:
                raise ValueError("Historical data/reports must be the matching snapshot pair")
            if self.enforce_protection:
                from .protection import require_protected
                require_protected(data)
                require_protected(reports)
        recorded_date = historical_date(created) if created else utc_now()
        if not legacy_paths:
            data = child_path(self.root, "sites", sid, "audits", aid, "data")
            reports = child_path(self.root, "sites", sid, "audits", aid, "reports")
            data.mkdir(parents=True, exist_ok=False)
            reports.mkdir(parents=True, exist_ok=False)
        with self.db() as db:
            db.execute("INSERT INTO audits(id,site_id,created,status,config,resolved,data_path,reports_path,legacy) VALUES (?,?,?,?,?,?,?,?,?)", (aid, sid, recorded_date, "registered" if legacy_paths else "running", config.model_dump_json(), json.dumps(resolve_rules(config)), str(data), str(reports), int(bool(legacy_paths))))
        return aid

    def audit(self, sid: str, aid: str):
        with self.db() as db:
            row = db.execute("SELECT * FROM audits WHERE site_id=? AND id=?", (checked_id(sid), checked_id(aid))).fetchone()
        if row is None:
            raise ValueError("Audit does not belong to the selected site")
        return dict(row)

    def audits(self, sid: str):
        self.site(sid)
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM audits WHERE site_id=? ORDER BY created DESC", (sid,))]

    def audit_file(self, sid: str, aid: str, kind: str, filename: str, *, period="current") -> Path:
        if period not in ("current", "previous") or (period == "previous" and kind != "data"):
            raise ValueError("Invalid evidence period")
        if kind not in ("data", "reports") or not re.fullmatch(r"[a-zA-Z0-9_-]+\.(csv|json|md)", filename):
            raise ValueError("Invalid evidence filename")
        row = self.audit(sid, aid)
        base = Path(row[kind + "_path"]).resolve()
        expected = self.legacy_root / kind if row["legacy"] else child_path(self.root, "sites", sid, "audits", aid, kind)
        if (row["legacy"] and not base.is_relative_to(expected.resolve())) or (not row["legacy"] and base != expected):
            raise ValueError("Cross-site evidence path rejected")
        return child_path(base, "comparison", filename) if period == "previous" else child_path(base, filename)

    def finish_audit(self, sid, aid, status, manifest):
        self.require_private_write()
        row = self.audit(sid, aid)
        if row["legacy"] or row["status"] != "running":
            raise ValueError("Completed/historical evidence is immutable")
        if status not in ("complete", "partial", "failed", "interrupted"):
            raise ValueError("Invalid completion status")
        with self.db() as db:
            db.execute("UPDATE audits SET status=?,manifest=? WHERE site_id=? AND id=?", (status, json.dumps(manifest), sid, aid))

    def save_findings(self, sid, aid, findings):
        self.require_private_write()
        row = self.audit(sid, aid)
        if row["legacy"] or row["status"] != "running":
            raise ValueError("Completed/historical audit findings are immutable")
        for finding in findings:
            if finding.get("site_id") != sid or finding.get("audit_id") != aid:
                raise ValueError("Finding site/audit mismatch")
            resolved = json.loads(row["resolved"])
            producing = resolved["rules"].get(finding.get("rule"))
            if not producing or finding.get("rule_version") != producing["version"] or finding.get("industry") != resolved["industry"] or finding.get("profile_version") != resolved["profile_version"]:
                raise ValueError("Finding provenance differs from the saved audit profile")
            for ref in finding["evidence"]:
                path = self.audit_file(sid, aid, "data", ref["file"])
                if not path.is_file() or type(ref.get("row")) is not int or ref["row"] < 2:
                    raise ValueError("Finding requires its own existing evidence and a CSV row")
        with self.db() as db:
            db.executemany("INSERT INTO recommendations(id,site_id,audit_id,payload) VALUES (?,?,?,?)", [(new_id(), sid, aid, json.dumps(f)) for f in findings])

    def findings(self, sid, aid):
        self.audit(sid, aid)
        with self.db() as db:
            return [{**dict(r), "payload": json.loads(r["payload"])} for r in db.execute("SELECT * FROM recommendations WHERE site_id=? AND audit_id=?", (sid, aid))]

    def set_finding_state(self, sid, aid, rid, state):
        self.require_private_write()
        if state not in ("proposed", "reviewed", "implemented", "verified", "dismissed"):
            raise ValueError("Invalid recommendation state")
        self.audit(sid, aid)
        with self.db() as db:
            if db.execute("UPDATE recommendations SET state=? WHERE id=? AND site_id=? AND audit_id=?", (state, checked_id(rid), sid, aid)).rowcount != 1:
                raise ValueError("Recommendation is outside the selected audit")

    def add_change(self, sid, *, date, action, url="", prior_value="", proposed_value="", approval_reference="", evidence="", verification="user-reported"):
        self.require_private_write()
        from datetime import date as Date
        from .config import within_site
        config = self.site(sid)
        Date.fromisoformat(date)
        if url and not within_site(config.url, url):
            raise ValueError("Change URL is outside the selected site")
        values = (date, action, url, prior_value, proposed_value, approval_reference, evidence, verification)
        limits = (4000, 4000, 4000, 8000, 8000, 4000, 4000, 4000)
        if not action.strip() or any(len(v) > limit for v, limit in zip(values, limits)):
            raise ValueError("Invalid change record")
        with self.db() as db:
            cid = new_id()
            db.execute("INSERT INTO change_events VALUES (?,?,?,?,?,?,?,?,?,?)", (cid, sid, *values))
        return cid

    def changes(self, sid):
        self.site(sid)
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM change_events WHERE site_id=? ORDER BY date DESC", (sid,))]
