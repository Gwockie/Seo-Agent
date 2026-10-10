"""Synthetic scheduling, process, credential, source and Windows task regressions."""
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import httplib2
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError

from seo_agent import scheduling as w
from seo_agent import weekly_worker as worker
from seo_agent import windows_tasks as tasks
from seo_agent.backup import _backup, _restore
from seo_agent.config import SCOPE
from seo_agent.content_safety import usable_html
from seo_agent.coordination import BusyError, run_lock, workspace_lock
from seo_agent.credentials import ConnectionError, load_connection
from seo_agent.demo import seed_demo, SyntheticService, synthetic_crawl
from seo_agent.gsc import execute, AccessError, service_for_credentials
from seo_agent.public_fetch import PublicFetcher
from seo_agent.runner import run_site, run_snapshot, AuditContext
from seo_agent.storage import Store, new_id, config_hash
from tests.test_app_engine import FakeVault, token

UTC = timezone.utc
NOW = datetime(2026, 10, 5, 13, 0, tzinfo=UTC)


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "workspace")
        seed_demo(self.store)
        self.sid, self.other = [s["id"] for s in self.store.sites()][:2]
        w.save_schedule(self.store, self.sid, {"enabled": True}, now=NOW - timedelta(minutes=1))

    def tearDown(self):
        self.tmp.cleanup()

    def due(self, now=NOW):
        return w.claim(self.store, self.sid, now=now)

    def test_default_disabled_and_saved_independent_bounds(self):
        self.assertFalse(w.schedule(self.store, self.other)["settings"]["enabled"])
        self.assertTrue(w.status(self.store, self.sid, now=NOW)["overdue"])
        for key, value in (("max_pages", 51), ("inspect_limit", 21), ("days", 90), ("lag_days", 0), ("weekday", 7), ("local_time", "24:00"), ("timezone", "Unknown/Zone")):
            with self.subTest(key=key), self.assertRaises(Exception):
                w.save_schedule(self.store, self.other, {key: value}, now=NOW)
        self.assertIsNone(w.schedule(self.store, self.other)["next_due"])

    def test_timezone_dst_fold_and_gap(self):
        sunday = {**w.Schedule().model_dump(), "weekday": 6, "local_time": "02:30"}
        self.assertEqual(w.next_occurrence(sunday, datetime(2026, 3, 7, tzinfo=UTC)), datetime(2026, 3, 8, 7, tzinfo=UTC))
        sunday["local_time"] = "01:30"
        self.assertEqual(w.next_occurrence(sunday, datetime(2026, 10, 31, tzinfo=UTC)), datetime(2026, 11, 1, 5, 30, tzinfo=UTC))
        self.assertEqual(w.next_occurrence(w.Schedule().model_dump(), datetime(2026, 11, 1, tzinfo=UTC)).hour, 14)
        with self.assertRaises(ValueError):
            w.next_occurrence(sunday, datetime(2026, 1, 1))

    def test_restart_clock_backwards_missed_weeks_catchup_once(self):
        restarted = Store(self.store.root)
        later = NOW + timedelta(days=35)
        attempt = w.claim(restarted, self.sid, now=later)
        self.assertEqual(attempt["scheduled"], NOW.isoformat())
        self.assertIsNone(w.claim(restarted, self.sid, now=later))
        aid = run_site(restarted, self.sid, request_id=attempt["request_id"], demo=True)
        w.finish(restarted, attempt, audit_id=aid, now=later)
        self.assertEqual(len(w.attempts(restarted, self.sid)), 1)
        self.assertFalse(w.status(restarted, self.sid, now=later)["overdue"])
        self.assertIsNone(w.claim(restarted, self.sid, now=NOW - timedelta(days=1)))

    def test_fail_before_audit_fresh_retry_ids_capped_and_overdue(self):
        a = self.due()
        w.finish(self.store, a, failure="temporary_source", retryable=True, now=NOW)
        self.assertIsNone(w.claim(self.store, self.sid, now=NOW + timedelta(minutes=14)))
        b = self.due(NOW + timedelta(minutes=15))
        self.assertNotEqual(a["request_id"], b["request_id"])
        w.finish(self.store, b, failure="temporary_source", retryable=True, now=NOW + timedelta(minutes=15))
        c = self.due(NOW + timedelta(minutes=75))
        w.finish(self.store, c, failure="temporary_source", retryable=True, now=NOW + timedelta(minutes=75))
        self.assertIsNone(self.due(NOW + timedelta(days=10)))
        state = w.status(self.store, self.sid, now=NOW + timedelta(days=10))
        self.assertTrue(state["stopped"])
        self.assertTrue(state["overdue"])
        self.assertIsNone(state["last_complete"])
        self.assertTrue(all(a["audit_id"] is None for a in w.attempts(self.store, self.sid)))

    def test_backward_clock_during_attempt_keeps_valid_history_and_retry(self):
        a = self.due()
        w.finish(self.store, a, failure="temporary_source", retryable=True, now=NOW - timedelta(hours=1))
        self.assertEqual(w.attempts(self.store, self.sid)[0]["finished"], NOW.isoformat())
        self.assertEqual(w.schedule(self.store, self.sid)["retry_at"], (NOW + timedelta(minutes=15)).isoformat())
        self.assertIsNone(w.claim(self.store, self.sid, now=NOW - timedelta(minutes=30)))
        w.validate_restored(self.store)

    def test_duplicate_manual_trigger_and_disable(self):
        trigger = new_id()
        a = w.claim(self.store, self.sid, now=NOW, manual=True, trigger_id=trigger)
        w.finish(self.store, a, failure="access_reconnect", now=NOW)
        self.assertIsNone(w.claim(self.store, self.sid, now=NOW, manual=True, trigger_id=trigger))
        w.disable(self.store, self.sid)
        self.assertIsNone(self.due())
        self.assertIsNotNone(w.claim(self.store, self.sid, now=NOW, manual=True, trigger_id=new_id()))

    def test_manual_success_consumes_overdue_and_retry_after_survives_restart(self):
        a = self.due()
        w.finish(self.store, a, failure="temporary_source", retryable=True, retry_after_seconds=7200, now=NOW)
        restarted = Store(self.store.root)
        self.assertEqual(w.schedule(restarted, self.sid)["retry_at"], (NOW + timedelta(hours=2)).isoformat())
        self.assertIsNone(w.claim(restarted, self.sid, now=NOW + timedelta(hours=1)))
        b = w.claim(restarted, self.sid, manual=True, now=NOW + timedelta(hours=1), trigger_id=new_id())
        aid = run_site(restarted, self.sid, request_id=b["request_id"], demo=True)
        w.finish(restarted, b, audit_id=aid, now=NOW + timedelta(hours=1))
        self.assertIsNone(w.claim(restarted, self.sid, now=NOW + timedelta(hours=3)))
        self.assertFalse(w.status(restarted, self.sid, now=NOW + timedelta(hours=3))["overdue"])

    def test_partial_retry_retains_last_complete_and_independent_sites(self):
        a = self.due()
        aid = run_site(self.store, self.sid, request_id=a["request_id"], demo=True)
        self.assertTrue(w.finish(self.store, a, audit_id=aid, now=NOW)["status"] == "complete")
        later = NOW + timedelta(days=7)
        b = self.due(later)
        partial = run_site(self.store, self.sid, request_id=b["request_id"], demo=True)
        m = json.loads(self.store.audit(self.sid, partial)["manifest"])
        m["stages"]["inspection"]["status"] = "partial"
        with self.store.db() as db:
            db.execute("UPDATE audits SET status=?,manifest=? WHERE id=?", ("partial", json.dumps(m), partial))
        w.finish(self.store, b, audit_id=partial, retryable=True, now=later)
        self.assertEqual(w.schedule(self.store, self.sid)["last_complete"]["audit_id"], aid)
        self.assertIsNone(w.schedule(self.store, self.other)["last_attempt"])
        with self.assertRaises(ValueError):
            w.completeness(self.store, self.other, aid)

    def test_replayed_finish_does_not_replace_success_or_future_due(self):
        a = self.due()
        w.finish(self.store, a, failure="temporary_source", retryable=True, now=NOW)
        b = self.due(NOW + timedelta(minutes=15))
        aid = run_site(self.store, self.sid, request_id=b["request_id"], demo=True)
        w.finish(self.store, b, audit_id=aid, now=NOW + timedelta(minutes=15))
        before = w.schedule(self.store, self.sid)
        w.finish(self.store, a, failure="access_reconnect", now=NOW + timedelta(hours=1))
        self.assertEqual(w.schedule(self.store, self.sid), before)

    def test_restore_rejects_cross_site_last_complete_and_wrong_request_binding(self):
        for case in ("last_complete", "request_id"):
            with self.subTest(case=case):
                a = w.claim(self.store, self.sid, manual=True, trigger_id=new_id())
                aid = run_site(self.store, self.sid, request_id=a["request_id"], demo=True)
                w.finish(self.store, a, audit_id=aid)
                if case == "last_complete":
                    other_aid = run_site(self.store, self.other, demo=True)
                    state = w.schedule(self.store, self.sid)
                    state["last_complete"]["audit_id"] = other_aid
                    w.persist(self.store, self.sid, state)
                else:
                    with self.store.db() as db:
                        db.execute("UPDATE weekly_attempts SET request_id=? WHERE id=?", (new_id(), a["id"]))
                with self.assertRaises(ValueError):
                    w.validate_restored(self.store)

    def test_interrupted_reconciliation_preserves_stages_not_completion(self):
        a = self.due()
        aid = self.store.create_audit(self.sid, audit_id=a["request_id"])
        m = {"site_id": self.sid, "audit_id": aid, "stages": {"gsc_current": {"status": "complete"}, "crawl": {"status": "running"}}}
        self.store.audit_file(self.sid, aid, "data", "manifest.json").write_text(json.dumps(m))
        w.reconcile(self.store, now=NOW)
        state = w.schedule(self.store, self.sid)
        attempt = w.attempts(self.store, self.sid)[0]
        self.assertIsNone(state["last_complete"])
        self.assertEqual(attempt["audit_id"], aid)
        self.assertEqual(attempt["payload"]["sources"]["gsc_current"], "complete")
        self.assertEqual(self.store.audit(self.sid, aid)["status"], "interrupted")
        self.assertIsNotNone(self.due(NOW + timedelta(minutes=15)))

    def test_interrupted_before_audit_and_after_audit_never_invents_completion(self):
        a = self.due()
        w.reconcile(self.store, now=NOW)
        b = self.due(NOW + timedelta(minutes=15))
        run_site(self.store, self.sid, request_id=b["request_id"], demo=True)
        w.reconcile(self.store, now=NOW + timedelta(minutes=15))
        self.assertEqual(len(w.attempts(self.store, self.sid)), 2)
        self.assertTrue(all(a["payload"]["failure"] == "interrupted" for a in w.attempts(self.store, self.sid)))
        self.assertIsNone(w.schedule(self.store, self.sid)["last_complete"])

    def test_honest_coverage_required_sources_and_health_independent(self):
        aid = run_site(self.store, self.sid, demo=True)
        audit = self.store.audit(self.sid, aid)
        original = json.loads(audit["manifest"])
        self.assertTrue(w.completeness(self.store, self.sid, aid)[0])
        for source in w.REQUIRED:
            for status in ("partial", "failed", "unavailable", "running"):
                with self.subTest(source=source, status=status):
                    m = json.loads(json.dumps(original)); m["stages"][source]["status"] = status
                    with self.store.db() as db:
                        db.execute("UPDATE audits SET manifest=? WHERE id=?", (json.dumps(m), aid))
                    self.assertFalse(w.completeness(self.store, self.sid, aid)[0])
        for source, key, value in (("crawl", "page_count", 0), ("crawl", "content_page_count", 0), ("crawl", "missing_priority_count", 1), ("inspection", "result_count", 0)):
            m = json.loads(json.dumps(original)); m["stages"][source][key] = value
            with self.store.db() as db:
                db.execute("UPDATE audits SET manifest=? WHERE id=?", (json.dumps(m), aid))
            self.assertFalse(w.completeness(self.store, self.sid, aid)[0])

    def test_backup_restore_retains_history_disables_detaches_installation(self):
        a = self.due(); aid = run_site(self.store, self.sid, request_id=a["request_id"], demo=True)
        w.finish(self.store, a, audit_id=aid, now=NOW)
        (self.store.root / "weekly-installation.json").write_text('{"private":"not exported"}')
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "restored")
        self.assertEqual(w.attempts(restored, self.sid)[0]["audit_id"], aid)
        self.assertFalse(w.schedule(restored, self.sid)["settings"]["enabled"])
        self.assertIsNone(restored.site(self.sid).connection_id)
        self.assertFalse((restored.root / "weekly-installation.json").exists())

    def test_migration_waits_for_gate_current_reads_do_not_migrate(self):
        with self.store.db() as db:
            db.execute("PRAGMA user_version=2")
        with run_lock(workspace_lock(self.store.root)), self.assertRaises(BusyError):
            Store(self.store.root)
        with self.store.db() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
        migrated = Store(self.store.root)
        with run_lock(workspace_lock(self.store.root)):
            self.assertTrue(Store(self.store.root).sites())
            with self.assertRaises(BusyError):
                run_site(migrated, self.sid, demo=True)

    def test_cross_process_checkout_independent_gate(self):
        script = "from pathlib import Path; from seo_agent.coordination import run_lock; import sys; " + "\ntry:\n with run_lock(Path(sys.argv[1])): pass\nexcept ValueError: sys.exit(75)"
        with run_lock(workspace_lock(self.store.root)):
            result = subprocess.run([sys.executable, "-c", script, str(workspace_lock(self.store.root))], timeout=20)
            self.assertEqual(result.returncode, 75)
        self.assertEqual(subprocess.run([sys.executable, "-c", script, str(workspace_lock(self.store.root))], timeout=20).returncode, 0)

    def test_worker_mocked_collect_is_normal_run_site_and_deduplicates(self):
        install = {"workspace": str(self.store.root)}
        def synthetic(store, sid, **kwargs):
            return run_site(store, sid, demo=True, **kwargs)
        with patch.object(worker, "validate_installation", return_value=install), patch("seo_agent.storage.Store.require_private_write"), patch("seo_agent.protection.require_protected"), patch("seo_agent.runner.run_site", side_effect=synthetic), patch.object(w, "now_utc", return_value=NOW):
            trigger = new_id()
            self.assertEqual(worker.collect(self.store.root / "weekly-installation.json", self.sid, trigger), 0)
            self.assertEqual(worker.collect(self.store.root / "weekly-installation.json", self.sid, trigger), 0)
        self.assertEqual(len(w.attempts(self.store, self.sid)), 1)

    def test_worker_busy_before_store_and_pre_audit_access_stop(self):
        install = {"workspace": str(self.store.root)}
        with patch.object(worker, "validate_installation", return_value=install), run_lock(workspace_lock(self.store.root)), patch.object(worker, "Store") as constructor:
            self.assertEqual(worker.collect(Path("ignored"), self.sid, new_id()), 75)
            constructor.assert_not_called()
        with patch.object(worker, "validate_installation", return_value=install), patch("seo_agent.protection.require_protected"), patch("seo_agent.runner.run_site", side_effect=ConnectionError("access_reconnect")), patch.object(w, "now_utc", return_value=NOW):
            self.assertEqual(worker.collect(Path("ignored"), self.sid, new_id()), 1)
        self.assertEqual(w.attempts(self.store, self.sid)[0]["payload"]["failure"], "access_reconnect")
        self.assertTrue(w.schedule(self.store, self.sid)["stopped"])

    def test_worker_mid_audit_credentials_and_unsafe_public_stops(self):
        for category in ("access_reconnect", "connection_scope_size_or_vault_invalid", "vault_persistence_failed", "public_destination_or_tls_invalid"):
            with self.subTest(category=category):
                w.save_schedule(self.store, self.sid, {"enabled": True}, now=NOW - timedelta(minutes=1))
                def incomplete(store, sid, **kwargs):
                    aid = run_site(store, sid, demo=True, **kwargs)
                    m = json.loads(store.audit(sid, aid)["manifest"])
                    stage = "crawl" if category.startswith("public_") else "gsc_current"
                    m["stages"][stage].update(status="failed", category=category)
                    if stage == "crawl":
                        pd.DataFrame([{"status": "request_error", "category": category}]).to_csv(store.audit_file(sid, aid, "data", "crawl.csv"), index=False)
                    with store.db() as db:
                        db.execute("UPDATE audits SET status='partial',manifest=? WHERE id=?", (json.dumps(m), aid))
                    return aid
                with patch.object(worker, "validate_installation", return_value={"workspace": str(self.store.root)}), patch("seo_agent.protection.require_protected"), patch("seo_agent.runner.run_site", side_effect=incomplete), patch.object(w, "now_utc", return_value=NOW):
                    self.assertEqual(worker.collect(Path("ignored"), self.sid, new_id()), 1)
                state = w.schedule(self.store, self.sid)
                self.assertEqual(state["failure"], category)
                self.assertTrue(state["stopped"])
                self.assertIsNone(state["retry_at"])
                self.assertTrue(w.status(self.store, self.sid, now=NOW)["overdue"])

    def test_supervisor_kills_hung_child_and_reconciles(self):
        install = {"workspace": str(self.store.root), "root": str(Path.cwd()), "python": sys.executable}
        with patch.object(worker, "validate_installation", return_value=install), patch("seo_agent.protection.require_protected"), patch.object(worker.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 900)) as run:
            self.assertEqual(worker.dispatch(Path("ignored"), sid=self.sid, trigger_id=new_id()), 1)
            self.assertLessEqual(run.call_args.kwargs["timeout"], 900)
            self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_supervisor_real_child_timeout_releases_and_reconciles_attempt(self):
        install = {"workspace": str(self.store.root), "root": str(Path.cwd()), "python": sys.executable}
        original = subprocess.run
        def hung_child(*args, **kwargs):
            w.claim(self.store, self.sid, manual=True, trigger_id=new_id())
            kwargs["timeout"] = .2
            return original([sys.executable, "-c", "import time; time.sleep(20)"], **kwargs)
        with patch.object(worker, "validate_installation", return_value=install), patch("seo_agent.protection.require_protected"), patch.object(worker.subprocess, "run", side_effect=hung_child):
            self.assertEqual(worker.dispatch(Path("ignored"), sid=self.sid, trigger_id=new_id()), 1)
        self.assertEqual(w.attempts(self.store, self.sid)[0]["payload"]["status"], "interrupted")
        with run_lock(workspace_lock(self.store.root)):
            pass


class CredentialReadinessTests(unittest.TestCase):
    def credential(self):
        creds = Mock(expired=True, refresh_token="synthetic", valid=True, scopes=[SCOPE], granted_scopes=[SCOPE])
        creds.to_json.return_value = token()
        vault = FakeVault(); cid = new_id(); vault.write(cid, token())
        return creds, vault, cid

    def test_expired_refresh_exact_scope_persistence_and_automatic_refresh(self):
        creds, vault, cid = self.credential()
        original = creds.refresh
        with patch("seo_agent.credentials.Credentials.from_authorized_user_info", return_value=creds):
            self.assertIs(load_connection(cid, vault), creds)
        original.assert_called_once()
        self.assertEqual(vault.read(cid), creds.to_json())
        creds.refresh(Mock())
        self.assertEqual(original.call_count, 2)

    def test_refresh_scope_overflow_revocation_write_read_failure_preserves_other(self):
        for case in ("scope", "overflow", "revoked", "write", "readback", "network"):
            with self.subTest(case=case):
                creds, vault, cid = self.credential()
                other = new_id(); vault.write(other, token(account="other")); prior = vault.read(cid)
                if case == "scope":
                    creds.refresh.side_effect = lambda _: setattr(creds, "granted_scopes", [SCOPE, "broad"])
                if case == "overflow":
                    creds.to_json.return_value = token(token="x" * 3000)
                if case == "revoked":
                    creds.refresh.side_effect = RefreshError("SYNTHETIC_SECRET_REVOCATION")
                if case == "network":
                    creds.refresh.side_effect = TransportError("SYNTHETIC_SECRET_NETWORK")
                if case == "write":
                    vault.write = Mock(side_effect=ValueError("secret write failure"))
                if case == "readback":
                    vault.write = Mock()
                    creds.to_json.return_value = token(token="different")
                with patch("seo_agent.credentials.Credentials.from_authorized_user_info", return_value=creds), self.assertRaises(ConnectionError) as error:
                    load_connection(cid, vault)
                self.assertNotIn("SYNTHETIC_SECRET", str(error.exception))
                self.assertEqual(vault.read(cid), prior)
                self.assertEqual(vault.read(other), token(account="other"))
                self.assertEqual(error.exception.retryable, case == "network")

    def test_google_transport_and_refresh_timeout(self):
        creds, _, _ = self.credential()
        with patch("seo_agent.gsc.google_auth_httplib2.AuthorizedHttp"), patch("seo_agent.gsc.build"), patch("seo_agent.gsc.httplib2.Http") as http:
            service_for_credentials(creds)
            http.assert_called_once_with(timeout=20)
        from seo_agent.credentials import bounded_refresh_request
        with patch("seo_agent.credentials.Request") as request:
            bounded_refresh_request()(url="https://oauth2.googleapis.com/token", timeout=999)
            self.assertEqual(request.return_value.call_args.kwargs["timeout"], 20)

    def test_automatic_refresh_rejection_sanitized_and_independent(self):
        for case in ("revoked", "network", "scope", "overflow", "write", "readback"):
            with self.subTest(case=case):
                creds, vault, cid = self.credential()
                original = creds.refresh
                creds.expired = False
                other = new_id(); vault.write(other, token(account="other"))
                with patch("seo_agent.credentials.Credentials.from_authorized_user_info", return_value=creds):
                    load_connection(cid, vault)
                prior = vault.read(cid)
                if case in {"revoked", "network"}:
                    original.side_effect = (TransportError if case == "network" else RefreshError)("SYNTHETIC_SECRET")
                elif case == "scope":
                    original.side_effect = lambda _: setattr(creds, "granted_scopes", [SCOPE, "broad"])
                elif case == "overflow":
                    creds.to_json.return_value = token(token="x" * 3000)
                elif case == "write":
                    vault.write = Mock(side_effect=ValueError("SYNTHETIC_SECRET"))
                else:
                    vault.write = Mock(); creds.to_json.return_value = token(token="different")
                with self.assertRaises(ConnectionError) as error:
                    creds.refresh(Mock())
                self.assertNotIn("SYNTHETIC_SECRET", str(error.exception))
                self.assertEqual(error.exception.retryable, case == "network")
                self.assertEqual(vault.read(cid), prior)
                self.assertEqual(vault.read(other), token(account="other"))


class SourceAndTaskTests(unittest.TestCase):
    def test_mid_audit_connection_category_preserves_independent_crawl(self):
        from seo_agent.config import SiteConfig
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = SiteConfig(name="Synthetic", url="https://example.com/", gsc_property="sc-domain:example.com")
            context = AuditContext(new_id(), new_id(), config, root / "data", root / "reports")
            with patch("seo_agent.runner.export_performance", side_effect=ConnectionError("access_reconnect")):
                manifest, _ = run_snapshot(context, SyntheticService(config), crawl_fn=synthetic_crawl)
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(manifest["stages"]["gsc_current"]["category"], "access_reconnect")
            self.assertEqual(manifest["stages"]["crawl"]["status"], "complete")
            self.assertTrue((context.data_dir / "crawl.csv").is_file())

    def test_atomic_checkpoint_sharing_retry_and_exhaustion_preserve_baseline(self):
        from seo_agent.runner import save_manifest
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            path.write_text('{"prior":true}')
            original = Path.replace
            failures = [True, True, False]
            def transient(pending, target):
                if failures.pop(0):
                    raise PermissionError("Synthetic Windows sharing violation")
                return original(pending, target)
            with patch.object(Path, "replace", transient), patch("seo_agent.runner.time.sleep") as sleep:
                save_manifest(path, {"new": True})
            self.assertEqual(json.loads(path.read_text()), {"new": True})
            self.assertEqual(sleep.call_count, 2)
            with patch.object(Path, "replace", side_effect=PermissionError()) as replace, patch("seo_agent.runner.time.sleep"), self.assertRaises(PermissionError):
                save_manifest(path, {"uncommitted": True})
            self.assertEqual(replace.call_count, 6)
            self.assertEqual(json.loads(path.read_text()), {"new": True})

    def test_crawl_challenge_200_does_not_extract_content_directives_or_links(self):
        from seo_agent.crawl import crawl
        from seo_agent.config import SiteConfig
        with tempfile.TemporaryDirectory() as folder:
            for code, html in ((200, '<html><title>Security check</title><body><h1>Challenge</h1><meta name="robots" content="noindex"><a href="/trap">Trap</a></body></html>'),
                               (202, '<html><title>Wait</title><body>Wait</body></html>')):
                fetcher = Mock()
                robots = Mock(status_code=200, text="User-agent: *\nAllow: /")
                response = Mock(status_code=code, url="https://example.com/", text=html, headers={"content-type": "text/html"}, retry_after_seconds=0)
                fetcher.get.return_value = robots
                config = SiteConfig(name="Synthetic", url="https://example.com/", gsc_property="sc-domain:example.com")
                with patch("seo_agent.crawl.PublicFetcher", return_value=fetcher), patch("seo_agent.crawl.discover_sitemaps", return_value=[]), patch("seo_agent.crawl.safe_get", return_value=response) as get:
                    frame = crawl(config.url, Path(folder) / "crawl.csv", config=config)
                self.assertEqual(frame.iloc[0]["http_status"], code)
                self.assertNotIn("meta_robots", frame.columns)
                self.assertNotIn("h1", frame.columns)
                self.assertEqual(fetcher.get.call_count, 1)
                self.assertEqual(get.call_count, 1)
                fetcher.close.assert_called_once()

    def test_google_retry_after_cap_and_access_stop(self):
        request = Mock()
        response = httplib2.Response({"status": "429", "retry-after": "4"})
        request.execute.side_effect = [HttpError(response, b'quota'), {"rows": []}]
        with patch("seo_agent.gsc.time.sleep") as sleep:
            self.assertEqual(execute(request), {"rows": []}); sleep.assert_called_once_with(4)
        request.execute.side_effect = HttpError(httplib2.Response({"status": "429", "retry-after": "120"}), b'quota')
        with patch("seo_agent.gsc.time.sleep") as sleep, self.assertRaises(ValueError):
            execute(request)
        sleep.assert_not_called()
        request.execute.side_effect = HttpError(httplib2.Response({"status": "403"}), b'access denied')
        with self.assertRaises(AccessError):
            execute(request)
        from seo_agent.gsc import RetryDeferredError
        request.execute.side_effect = [HttpError(httplib2.Response({"status": "429"}), b'quota'),
                                       HttpError(httplib2.Response({"status": "429"}), b'quota'),
                                       HttpError(httplib2.Response({"status": "429", "retry-after": "7200"}), b'quota')]
        with patch("seo_agent.gsc.time.sleep"), self.assertRaises(RetryDeferredError) as deferred:
            execute(request)
        self.assertEqual(deferred.exception.retry_after_seconds, 7200)

    def test_google_retries_capped(self):
        request = Mock(); request.execute.side_effect = OSError("secret")
        with patch("seo_agent.gsc.time.sleep") as sleep, self.assertRaises(ValueError):
            execute(request)
        self.assertEqual(request.execute.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_challenge_unfinished_and_good_page(self):
        for title, body in (("Just a moment...", "Challenge"), ("Example", '<div id="sg-captcha">Verify</div>'), ("Example", "verify that you are human"), ("Example", "Loading...")):
            self.assertFalse(usable_html(f"<html><title>{title}</title><body>{body}</body></html>"))
        self.assertFalse(usable_html("<title>Example</title><h1>Unfinished</h1>"))
        self.assertTrue(usable_html("<html><title>Example</title><body><h1>Service</h1></body></html>"))

    def test_public_retry_after_challenge_stop_and_request_budget(self):
        f = PublicFetcher("https://example.com/", max_requests=2)
        try:
            unavailable = Mock(status_code=503, headers={"Retry-After": "5"})
            good = Mock(status_code=200)
            with patch.object(f, "_get_once", side_effect=[unavailable, good]) as get, patch("seo_agent.public_fetch.time.sleep") as sleep:
                self.assertIs(f.get("https://example.com/"), good)
                self.assertEqual(get.call_count, 2); sleep.assert_called_once_with(5)
            for code in (200, 202, 403):
                with patch.object(f, "_get_once", return_value=Mock(status_code=code)) as get:
                    f.get("https://example.com/"); self.assertEqual(get.call_count, 1)
            with patch.object(f, "_get_once", return_value=Mock(status_code=503, headers={"Retry-After": "300"})), patch("seo_agent.public_fetch.time.sleep") as sleep:
                f.get("https://example.com/"); sleep.assert_not_called()
        finally:
            f.close()

    def install(self, root):
        return {"schema": 1, "root": str(root), "workspace": str(root / "workspace" / "private"),
                "python": str(root / ".venv-mvp" / "Scripts" / "python.exe"),
                "pythonw": str(root / ".venv-mvp" / "Scripts" / "pythonw.exe"), "principal": "S-1-5-21-123"}

    def test_task_xml_absolute_paths_spaces_no_password_and_power(self):
        install = self.install(Path("C:/Synthetic Root With Spaces"))
        xml = tasks.task_xml(install, Path(install["workspace"]) / "weekly-installation.json")
        root = ET.fromstring(xml); ns = {"t": tasks.NS}
        self.assertEqual(root.find("t:Actions/t:Exec/t:Command", ns).text, install["pythonw"])
        arguments = root.find("t:Actions/t:Exec/t:Arguments", ns).text
        self.assertIn('"C:', arguments)
        self.assertIn("InteractiveToken", xml); self.assertIn("LeastPrivilege", xml)
        self.assertNotIn("Password", xml); self.assertNotIn("SYSTEM", xml)
        self.assertEqual(root.find("t:Settings/t:WakeToRun", ns).text, "false")
        self.assertEqual(root.find("t:Settings/t:StartWhenAvailable", ns).text, "true")

    def test_task_preview_mutation_hash_ownership_and_rollback_mocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weekly-installation.json"
            install = self.install(Path(tmp))
            with patch.object(tasks, "validate_installation", return_value=install), patch.object(tasks, "invoke", return_value={"registered": False}) as invoke:
                preview = tasks.preview(path)
                self.assertEqual(invoke.call_args.args[0]["action"], "status")
                with self.assertRaises(ValueError):
                    tasks.apply(path, "register", "wrong")
                tasks.apply(path, "register", preview["reviewed_sha256"])
                self.assertEqual(invoke.call_args.args[0]["action"], "register")
                self.assertEqual(len(list(Path(tmp).glob("weekly-task-rollback-*.json"))), 1)
                self.assertIn("Task ownership mismatch", tasks.SCRIPT)
                self.assertIn("Task changed since review", tasks.SCRIPT)

    def test_wrong_installation_checkout_workspace_runtime_principal_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / ".git").mkdir()
            scripts = root / ".venv-mvp" / "Scripts"; scripts.mkdir(parents=True)
            for name in ("python.exe", "pythonw.exe"): (scripts / name).touch()
            value = self.install(root); folder = Path(value["workspace"]); folder.mkdir(parents=True)
            path = folder / "weekly-installation.json"
            path.write_text(json.dumps(value))
            with patch.object(worker, "ROOT", root), patch("seo_agent.protection.require_protected"), patch.object(worker, "current_principal", return_value=value["principal"]):
                worker.validate_installation(path, check_executable=False)
                for key, wrong in (("root", str(root / "other")), ("workspace", str(root / "workspace" / "demo")), ("python", "relative.exe"), ("principal", "S-1-5-99")):
                    path.write_text(json.dumps({**value, key: wrong}))
                    with self.assertRaises(ValueError): worker.validate_installation(path, check_executable=False)
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError): worker.validate_installation(path)
                with patch.dict("os.environ", {"SEO_DEMO": "1"}), self.assertRaises(ValueError): worker.validate_installation(path, check_executable=False)
                (root / ".git").rmdir(); (root / ".git").write_text("gitdir: elsewhere")
                with self.assertRaises(ValueError): worker.validate_installation(path, check_executable=False)


if __name__ == "__main__":
    unittest.main()
