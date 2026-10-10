"""Credential-free private backup on verified protected storage; safe restore."""
from __future__ import annotations
import json
from contextlib import closing
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .protection import require_protected
from .storage import Store, child_path, checked_id, config_hash, private_location, TRACKING_TABLES, SCHEDULING_TABLES, EVALUATION_TABLES
from .config import SiteConfig
from .import_export import backup_evidence_path
from .appearance import appearance_path, load_appearance

MAX_BACKUP_BYTES = 200 * 1024 * 1024


def backup(store: Store, destination: Path):
    private_location(destination)
    require_protected(store.root)
    require_protected(destination.parent)
    for site in store.sites():
        for audit in store.audits(site["id"]):
            if audit["legacy"]:
                require_protected(Path(audit["data_path"]))
                require_protected(Path(audit["reports_path"]))
    from .coordination import run_lock, workspace_lock
    with run_lock(workspace_lock(store.root)):
        _backup(store, destination)


def _backup(store, destination):
    # Internal writer exists for synthetic test fixtures; production entry gates storage.
    with tempfile.TemporaryDirectory(dir=store.root) as tmp:
        dbpath = Path(tmp) / "metadata.sqlite"
        with store.db() as source, closing(sqlite3.connect(dbpath)) as target:
            source.backup(target)
        total = dbpath.stat().st_size
        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("backup.json", json.dumps({"schema": 1, "credentials": "excluded; reconnect Google on restore"}))
            z.write(dbpath, "metadata.sqlite")
            for site in store.sites():
                sid = site["id"]
                appearance = appearance_path(store, sid)
                if appearance.is_file():
                    load_appearance(store, sid)  # Validate site identity and inert format.
                    total += appearance.stat().st_size
                    if total > MAX_BACKUP_BYTES:
                        raise ValueError("Backup size limit exceeded")
                    z.write(appearance, f"sites/{sid}/appearance.json")
                for audit in store.audits(sid):
                    aid = audit["id"]
                    for kind in ("data", "reports"):
                        base = store.audit_file(sid, aid, kind, "manifest.json" if kind == "data" else "snapshot.md").parent
                        for path in base.rglob("*"):
                            if not path.is_file():
                                continue
                            relative = path.relative_to(base)
                            if not backup_evidence_path(relative, kind):
                                continue
                            if not path.resolve().is_relative_to(base.resolve()) or any(p in path.name.casefold() for p in ("token", "secret", "credential")):
                                raise ValueError("Forbidden file in evidence directory")
                            total += path.stat().st_size
                            if total > MAX_BACKUP_BYTES:
                                raise ValueError("Backup size limit exceeded")
                            z.write(path, f"sites/{sid}/audits/{aid}/{kind}/{relative.as_posix()}")


def restore(archive: Path, root: Path):
    private_location(root)
    require_protected(archive.parent)
    require_protected(root.parent)
    from .coordination import run_lock, workspace_lock
    with run_lock(workspace_lock(root)):
        return _restore(archive, root, already_locked=True)


def _restore(archive, root, *, already_locked=False):
    root = root.resolve()
    if root.exists():
        raise ValueError("Restore requires a new workspace directory")
    if archive.stat().st_size > MAX_BACKUP_BYTES:
        raise ValueError("Backup exceeds size limit")
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > 5000 or sum(i.file_size for i in infos) > MAX_BACKUP_BYTES or len({i.filename for i in infos}) != len(infos):
            raise ValueError("Backup entry/expanded size limit exceeded")
        for info in infos:
            p = PurePosixPath(info.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in info.filename or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe archive path")
            if info.filename not in {"backup.json", "metadata.sqlite"}:
                parts = p.parts
                if len(parts) == 3 and parts[0] == "sites" and parts[2] == "appearance.json":
                    checked_id(parts[1])
                    continue
                if len(parts) not in (6, 7) or parts[0] != "sites" or parts[2] != "audits" or parts[4] not in ("data", "reports"):
                    raise ValueError("Unexpected archive contents")
                checked_id(parts[1]); checked_id(parts[3])
                if not backup_evidence_path(PurePosixPath(*parts[5:]), parts[4]):
                    raise ValueError("Forbidden archive file")
        if json.loads(z.read("backup.json")).get("schema") != 1:
            raise ValueError("Unsupported backup schema")
        root.mkdir(parents=True)
        for info in infos:
            if info.filename == "backup.json":
                continue
            dest = child_path(root, "app.sqlite" if info.filename == "metadata.sqlite" else info.filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(info))
    # Validate the SQLite structure before executing schema statements or queries.
    with closing(sqlite3.connect(root / "app.sqlite")) as db, db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Invalid backup database")
        if db.execute("SELECT name FROM sqlite_master WHERE type IN ('trigger','view')").fetchall():
            raise ValueError("Executable database objects are prohibited")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        original_tables = {"connections", "sites", "target_phrases", "audits", "recommendations", "change_events"}
        journal_tables = {"change_plans", "result_reviews"}
        if tables not in (original_tables, original_tables | journal_tables, original_tables | journal_tables | TRACKING_TABLES, original_tables | journal_tables | TRACKING_TABLES | SCHEDULING_TABLES, original_tables | journal_tables | TRACKING_TABLES | SCHEDULING_TABLES | EVALUATION_TABLES):
            raise ValueError("Unexpected backup database schema")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2, 3, 4):
            raise ValueError("Unsupported backup database version")
        from .storage import SCHEMA, TRACKING_SCHEMA, SCHEDULING_SCHEMA, EVALUATION_SCHEMA
        with closing(sqlite3.connect(":memory:")) as expected:
            expected.executescript(SCHEMA + TRACKING_SCHEMA + SCHEDULING_SCHEMA + EVALUATION_SCHEMA)
            for table in tables:
                # Table names have already been checked against a fixed allowlist.
                for pragma in ("table_info", "foreign_key_list"):
                    if db.execute(f"PRAGMA {pragma}({table})").fetchall() != expected.execute(f"PRAGMA {pragma}({table})").fetchall():
                        raise ValueError("Unexpected backup table structure")
        for sid, raw in db.execute("SELECT id,config FROM sites").fetchall():
            checked_id(sid)
            config = SiteConfig.model_validate_json(raw)
            # Explicitly detach restored account references; IDs/labels remain history.
            config.connection_id = None
            db.execute("UPDATE sites SET config=?,config_hash=?,connection_id=NULL WHERE id=?", (config.model_dump_json(), config_hash(config), sid))
        for aid, sid in db.execute("SELECT id,site_id FROM audits").fetchall():
            checked_id(aid); checked_id(sid)
            data = child_path(root, "sites", sid, "audits", aid, "data")
            reports = child_path(root, "sites", sid, "audits", aid, "reports")
            data.mkdir(parents=True, exist_ok=True); reports.mkdir(parents=True, exist_ok=True)
            db.execute("UPDATE audits SET data_path=?,reports_path=?,legacy=0 WHERE id=? AND site_id=?", (str(data), str(reports), aid, sid))
    store = Store(root, already_locked=already_locked)
    for site in store.sites():
        load_appearance(store, site["id"])
        from .learning import plans, validate_plan, reviews
        for record in plans(store, site["id"]):
            audit = store.audit(site["id"], record["audit_id"])
            validate_plan(record["payload"], SiteConfig.model_validate_json(audit["config"]))
            if record["change_id"] and not any(c["id"] == record["change_id"] for c in store.changes(site["id"])):
                raise ValueError("Backup contains a change attached to another site")
            for review in reviews(store, site["id"], record["id"]):
                store.audit(site["id"], review["audit_id"])
    from .tracking import validate_restored_tracking
    validate_restored_tracking(store)
    from .proposal_review import validate_restored as validate_assessments
    validate_assessments(store)
    from .scheduling import validate_restored
    validate_restored(store)
    return store
