"""Headless supervisor and bounded collector, launched by this app's Windows task."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

from .coordination import BusyError, run_lock, workspace_lock
from .storage import Store, config_hash, new_id
from . import scheduling as schedules

ROOT = Path(__file__).resolve().parent.parent
JOB_SECONDS = 900
DISPATCH_SECONDS = 1800


def current_principal():
    if os.name != "nt":
        raise ValueError("Windows is required")
    result = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10, check=True)
    import csv
    return list(csv.reader([result.stdout.strip()]))[0][1]


def validate_installation(path, *, check_executable=True):
    from .protection import require_protected
    from .storage import private_location
    path = private_location(Path(path))
    require_protected(path.parent)
    if path.name != "weekly-installation.json" or path.stat().st_size > 8000:
        raise ValueError("Invalid protected installation file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if set(value) != {"schema", "root", "workspace", "python", "pythonw", "principal"} or value["schema"] != 1:
        raise ValueError("Invalid installation contract")
    root, workspace = Path(value["root"]), Path(value["workspace"])
    if not root.is_absolute() or root.resolve() != ROOT or not (root / ".git").is_dir():
        raise ValueError("Launch only from the canonical primary installation")
    if not workspace.is_absolute() or private_location(workspace) != workspace or path.parent != workspace:
        raise ValueError("Wrong workspace")
    if workspace == root / "workspace" / "demo" or os.environ.get("SEO_DEMO") == "1":
        raise ValueError("Demo cannot use a live schedule")
    for key, name in (("python", "python.exe"), ("pythonw", "pythonw.exe")):
        expected = root / ".venv-mvp" / "Scripts" / name
        if Path(value[key]) != expected or not expected.is_file():
            raise ValueError("Use the stable primary .venv-mvp runtime")
    if check_executable and Path(sys.executable).resolve() not in {Path(value["python"]).resolve(), Path(value["pythonw"]).resolve()}:
        raise ValueError("Wrong interpreter")
    if value["principal"] != current_principal():
        raise ValueError("Wrong Windows principal; Vault access must be reviewed")
    require_protected(workspace)
    return value


def initialize(workspace):
    """Explicit setup only, never called by a UI rerun or development test."""
    from .protection import require_protected
    from .storage import private_location
    workspace = private_location(Path(workspace))
    require_protected(workspace)
    if not (ROOT / ".git").is_dir() or workspace == ROOT / "workspace" / "demo":
        raise ValueError("Configure only in the canonical primary installation")
    value = {"schema": 1, "root": str(ROOT), "workspace": str(workspace),
             "python": str(ROOT / ".venv-mvp" / "Scripts" / "python.exe"),
             "pythonw": str(ROOT / ".venv-mvp" / "Scripts" / "pythonw.exe"), "principal": current_principal()}
    path = workspace / "weekly-installation.json"
    with run_lock(workspace_lock(workspace)):
        if path.exists():
            raise ValueError("Installation already configured; review the existing packet")
        for key in ("python", "pythonw"):
            if not Path(value[key]).is_file():
                raise ValueError("Stable runtime missing")
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def collect(path, sid, trigger_id, *, manual=False):
    install = validate_installation(path)
    try:
        with run_lock(workspace_lock(install["workspace"])):
            store = Store(Path(install["workspace"]), enforce_protection=True, already_locked=True)
            schedules.reconcile(store)
            attempt = schedules.claim(store, sid, manual=manual, trigger_id=trigger_id)
            if not attempt:
                return 0
            value = schedules.schedule(store, sid)
            failure, retryable, aid, retry_after_seconds = None, False, None, 0
            try:
                if value.get("config_hash") != config_hash(store.site(sid)):
                    raise ValueError("Configuration changed")
                from .runner import run_site
                s = value["settings"]
                aid = run_site(store, sid, request_id=attempt["request_id"], already_locked=True,
                               expected_config_hash=value["config_hash"], inspect=True,
                               **{k: s[k] for k in ("days", "lag_days", "max_pages", "inspect_limit")})
                complete, sources = schedules.completeness(store, sid, aid)
                if not complete:
                    manifest = json.loads(store.audit(sid, aid)["manifest"])
                    # Challenges/robots/content gaps need local attention, not repeated hosting requests.
                    crawl_ok = sources.get("crawl") == "complete"
                    failure = "temporary_source" if crawl_ok else "public_content_unavailable"
                    retryable = crawl_ok
                    if not crawl_ok:
                        from .rules import read_csv
                        pages = read_csv(store.audit_file(sid, aid, "data", "crawl.csv"))
                        states = set(pages.get("status", []).astype(str)) if not pages.empty else set()
                        if states & {"request_error", "429", "500", "502", "503", "504"} and not states & {"content_unavailable", "202", "403", "blocked_by_robots"}:
                            failure, retryable = "temporary_source", True
                        if "category" in pages and pages.category.eq("public_destination_or_tls_invalid").any():
                            failure, retryable = "public_destination_or_tls_invalid", False
                    if any(s.get("category") == "access" for s in manifest.get("stages", {}).values()):
                        failure, retryable = "access_reconnect", False
                    for stage in manifest.get("stages", {}).values():
                        if stage.get("category") in {"access_reconnect", "connection_scope_size_or_vault_invalid", "vault_persistence_failed"}:
                            failure, retryable = stage["category"], False
                    retry_after_seconds = max((s.get("retry_after_seconds", 0) for s in manifest.get("stages", {}).values()), default=0)
            except Exception as exc:
                from .credentials import ConnectionError
                from .gsc import AccessError, RetryDeferredError
                from .protection import ProtectionError
                if isinstance(exc, ConnectionError):
                    failure, retryable = exc.category, exc.retryable
                elif isinstance(exc, AccessError):
                    failure = "access_reconnect"
                elif isinstance(exc, RetryDeferredError):
                    failure, retryable = "temporary_source", True
                    retry_after_seconds = exc.retry_after_seconds
                elif isinstance(exc, ProtectionError):
                    failure = "storage_invalid"
                else:
                    failure = "configuration_or_collection_failed"
                # Preserve audit identity even if run_site raised after creating it.
                if any(a["id"] == attempt["request_id"] for a in store.audits(sid)):
                    aid = attempt["request_id"]
            result = schedules.finish(store, attempt, audit_id=aid, failure=failure, retryable=retryable, retry_after_seconds=retry_after_seconds)
            return 0 if result["status"] == "complete" else 1
    except BusyError:
        return 75  # Deferred; no failed collection and due time stays overdue.


def dispatch(path, *, sid=None, trigger_id=None):
    """Hard wall-clock bound is outside the process making network calls."""
    install = validate_installation(path)
    try:
        with run_lock(workspace_lock(install["workspace"])):
            store = Store(Path(install["workspace"]), enforce_protection=True, already_locked=True)
            schedules.reconcile(store)
            selected = [sid] if sid else [s["id"] for s in store.sites() if schedules.status(store, s["id"])["overdue"]]
    except BusyError:
        return 75
    started = time.monotonic()
    outcome = 0
    for selected_sid in selected:
        remaining = DISPATCH_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            return 75
        command = [install["python"], "-m", "seo_agent", "weekly-collect", "--installation", str(path),
                   "--site-id", selected_sid, "--trigger-id", trigger_id or new_id()]
        if sid:
            command.append("--manual")
        try:
            result = subprocess.run(command, cwd=install["root"], timeout=min(JOB_SECONDS, remaining),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            outcome = result.returncode or outcome
        except subprocess.TimeoutExpired:
            # subprocess.run kills and waits for this child only; the OS releases its gate.
            try:
                with run_lock(workspace_lock(install["workspace"])):
                    schedules.reconcile(Store(Path(install["workspace"]), enforce_protection=True, already_locked=True))
            except BusyError:
                pass  # Next acquired gate reconciles without assuming success.
            outcome = 1
    return outcome
