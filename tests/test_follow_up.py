import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from seo_agent.__main__ import main
from seo_agent.backup import _backup, _restore
from seo_agent.config import SiteConfig, SCOPE
from seo_agent.demo import SyntheticService, synthetic_crawl
from seo_agent.import_export import register_legacy, seed_original
from seo_agent.preflight import setup_status
from seo_agent.protection import ProtectionError, storage_status
from seo_agent.runner import AuditContext, run_snapshot
from seo_agent.storage import Store, new_id, credential_location


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_store_denied_before_directory_or_database_creation(self):
        target = self.root / "absent" / "workspace"
        with patch("seo_agent.protection.require_protected", side_effect=ProtectionError("Blocked")):
            with self.assertRaises(ProtectionError):
                Store(target, enforce_protection=True)
        self.assertFalse(target.parent.exists())
        existing = self.root / "existing"
        existing.mkdir()
        with patch("seo_agent.protection.require_protected", side_effect=ProtectionError("Blocked")):
            with self.assertRaises(ProtectionError):
                Store(existing, enforce_protection=True)
        self.assertEqual(list(existing.iterdir()), [])

    def test_storage_diagnostic_creates_no_store_or_workspace(self):
        target = self.root / "absent"
        with patch("sys.argv", ["seo_agent", "--workspace", str(target), "storage-check"]), patch("seo_agent.__main__.Store") as factory, patch("seo_agent.protection.storage_status", return_value={"verified": False, "reason": "Blocked"}), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        factory.assert_not_called()
        self.assertFalse(target.exists())
        self.assertFalse(json.loads(output.getvalue())["verified"])

    def test_credentials_cannot_write_to_unignored_repository_directory(self):
        repo = Path(__file__).resolve().parent.parent
        for target in (repo / "docs" / "credential-copy", repo / "custom-secrets"):
            with self.assertRaises(ValueError):
                credential_location(target)
            self.assertFalse(target.exists())
        self.assertEqual(credential_location(repo / "secrets"), repo / "secrets")

    def test_storage_checks_fail_for_descendant_acl_and_reparse(self):
        good = {"acl": True, "encrypted": True, "checked_entries": 2, "broad_acl_entries": 0, "unencrypted_entries": 0, "reparse_entries": 0, "bitlocker": "verified"}
        for updates in ({}, {"acl": False, "broad_acl_entries": 1}, {"reparse_entries": 1}, {"acl": "true"}, {"checked_entries": 10001}):
            result = Mock(stdout=json.dumps({**good, **updates}))
            with patch("seo_agent.protection.os.name", "nt"), patch("seo_agent.protection.subprocess.run", return_value=result) as run:
                status = storage_status(self.root)
            self.assertEqual(status["verified"], not bool(updates))
            self.assertEqual(run.call_args.kwargs["env"]["SEO_CHECK_PATH"], str(self.root))
            self.assertNotIn(str(self.root), run.call_args.args[0][-1])

    def test_local_access_passes_without_encryption_but_opt_in_check_fails(self):
        plain = {"acl": True, "encrypted": False, "checked_entries": 2, "broad_acl_entries": 0, "unencrypted_entries": 2, "reparse_entries": 0, "bitlocker": "unknown"}
        with patch("seo_agent.protection.os.name", "nt"), patch("seo_agent.protection.subprocess.run", return_value=Mock(stdout=json.dumps(plain))):
            local = storage_status(self.root)
            strict = storage_status(self.root, require_encryption=True)
            missing = storage_status(self.root / "missing", require_encryption=True)
            # Exercise the actual Store gate: only synthetic metadata is written.
            store = Store(self.root / "workspace", enforce_protection=True)
        self.assertTrue(local["verified"])
        self.assertFalse(local["encrypted"])
        self.assertFalse(local["encryption_required"])
        self.assertIn("optional", local["reason"])
        self.assertFalse(strict["verified"])
        self.assertTrue(strict["encryption_required"])
        self.assertFalse(missing["verified"])
        self.assertTrue(missing["encryption_required"])
        self.assertTrue((store.root / "app.sqlite").is_file())

    def test_cli_encryption_check_is_explicit_and_read_only(self):
        with patch("sys.argv", ["seo_agent", "storage-check", "--path", str(self.root), "--require-encryption"]), patch("seo_agent.__main__.Store") as factory, patch("seo_agent.protection.storage_status", return_value={"verified": False}) as check, redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 1)
        check.assert_called_once_with(self.root, require_encryption=True)
        factory.assert_not_called()

    def test_missing_directory_and_unavailable_probe_do_not_pass(self):
        with patch("seo_agent.protection.subprocess.run", side_effect=subprocess.TimeoutExpired("powershell", 30)):
            self.assertFalse(storage_status(self.root)["verified"])
            status = storage_status(self.root / "missing")
        self.assertFalse(status["verified"])
        self.assertFalse(status["exists"])
        self.assertFalse((self.root / "missing").exists())

    def test_setup_diagnostic_redacts_credentials_and_never_accesses_google(self):
        secrets = self.root / "secrets"
        secrets.mkdir()
        token = json.dumps({"token": "ACCESS_SENTINEL", "refresh_token": "REFRESH_SENTINEL", "client_id": "CLIENT_SENTINEL", "client_secret": "SECRET_SENTINEL", "token_uri": "https://oauth2.googleapis.com/token", "scopes": [SCOPE]})
        path = secrets / "token.json"
        path.write_text(token)
        (secrets / "client_secret.json").write_text(json.dumps({"installed": {"auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "client_secret": "CLIENT_SECRET_SENTINEL"}}))
        with patch("seo_agent.preflight.storage_status", return_value={"verified": False}), patch("seo_agent.preflight.WindowsVault") as vault:
            status = setup_status(self.root / "absent", secrets, self.root)
        self.assertTrue(status["legacy_token"]["format_and_size_valid"])
        self.assertFalse(status["live_ready"])
        for sentinel in ("ACCESS_SENTINEL", "REFRESH_SENTINEL", "SECRET_SENTINEL", "CLIENT_SENTINEL", "CLIENT_SECRET_SENTINEL"):
            self.assertNotIn(sentinel, json.dumps(status))
        self.assertEqual(path.read_text(), token)
        vault.return_value.read.assert_not_called()
        vault.return_value.probe.assert_not_called()
        self.assertFalse((self.root / "absent").exists())

    def test_historical_pair_date_provenance_and_captures_survive_backup(self):
        store = Store(self.root / "workspace", legacy_root=self.root)
        sid = seed_original(store, name="Synthetic original", url="https://original.example/", property_url="https://original.example/")
        data = self.root / "data" / "20261005T192314Z"
        reports = self.root / "reports" / data.name
        data.mkdir(parents=True)
        reports.mkdir(parents=True)
        (data / "manifest.json").write_text(json.dumps({"url": "https://original.example/", "site": "https://original.example/", "created_utc": data.name}))
        (data / "pages").mkdir()
        captures = {"pages/service.html": b"<script>UNTRUSTED_CAPTURE</script>", "pages/service.txt": b"Original public text", "robots.txt": b"User-agent: *", "page-sitemap.xml": b"<urlset/>", "validation.json": b'{"historical":true}', "reviewed-page-observations.json": b'{"reviewed":true,"text":"UNTRUSTED_CAPTURE"}'}
        for name, raw in captures.items():
            (data / name).write_bytes(raw)
        (reports / "executive-summary.md").write_text("Original narrative")
        (data / "token.json").write_text("EXCLUDED_SENTINEL")
        wrong = self.root / "reports" / "another-snapshot"
        wrong.mkdir()
        with self.assertRaises(ValueError):
            register_legacy(store, sid, data, wrong)
        aid = register_legacy(store, sid, data, reports)
        row = store.audit(sid, aid)
        self.assertEqual(row["created"], "2026-10-05T19:23:14+00:00")
        self.assertEqual(json.loads(row["resolved"])["registry_version"], "unknown")
        self.assertEqual(register_legacy(store, sid, data, reports), aid)
        newer = store.create_audit(sid, created="2026-10-07T19:23:14+00:00")
        store.finish_audit(sid, newer, "complete", {})
        self.assertEqual(store.audits(sid)[0]["id"], newer)
        before = {p: p.read_bytes() for folder in (data, reports) for p in folder.rglob("*") if p.is_file()}
        archive = self.root / "backup.zip"
        _backup(store, archive)
        with zipfile.ZipFile(archive) as z:
            self.assertNotIn(b"EXCLUDED_SENTINEL", b"".join(z.read(n) for n in z.namelist()))
            for name, raw in captures.items():
                self.assertEqual(z.read(f"sites/{sid}/audits/{aid}/data/{name}"), raw)
        restored = _restore(archive, self.root / "restored")
        base = restored.audit_file(sid, aid, "data", "manifest.json").parent
        for name, raw in captures.items():
            self.assertEqual((base / name).read_bytes(), raw)
        for old in (aid, newer):
            with self.assertRaises(ValueError):
                restored.finish_audit(sid, old, "complete", {})
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_public_legacy_uses_folder_time_and_preserves_timestamp_source(self):
        store = Store(self.root / "workspace", legacy_root=self.root)
        sid = seed_original(store, name="Synthetic original", url="https://original.example/", property_url="https://original.example/")
        data = self.root / "data" / "public-20261005T190725Z"
        reports = self.root / "reports" / data.name
        data.mkdir(parents=True); reports.mkdir(parents=True)
        source = {"kind": "public_crawl_only", "site_url": "https://original.example/", "collected_date": "2026-10-05"}
        manifest = data / "manifest.json"
        manifest.write_text(json.dumps(source))
        raw = manifest.read_bytes()
        with self.assertRaises(ValueError):
            register_legacy(store, sid, data, reports)
        aid = register_legacy(store, sid, data, reports, associate=True)
        row = store.audit(sid, aid)
        saved = json.loads(row["manifest"])
        self.assertEqual(row["created"], "2026-10-05T19:07:25+00:00")
        self.assertEqual(row["status"], "legacy-public-only")
        self.assertFalse(saved["gsc_available"])
        self.assertEqual(saved["source"], source)
        self.assertIn("snapshot folder UTC", saved["collection_time_source"])
        self.assertEqual(manifest.read_bytes(), raw)

    def test_public_legacy_rejects_other_site_and_conflicting_date(self):
        store = Store(self.root / "workspace", legacy_root=self.root)
        sid = seed_original(store, name="Synthetic original", url="https://original.example/", property_url="https://original.example/")
        data = self.root / "data" / "public-20261005T190725Z"
        reports = self.root / "reports" / data.name
        data.mkdir(parents=True); reports.mkdir(parents=True)
        for source in ({"site_url": "https://other.example/", "collected_date": "2026-10-05"}, {"url": "https://original.example/", "site_url": "https://other.example/"}, {"site_url": "https://original.example/", "collected_date": "2026-10-06"}):
            (data / "manifest.json").write_text(json.dumps(source))
            with self.assertRaises(ValueError):
                register_legacy(store, sid, data, reports, associate=True)
            self.assertFalse(store.audits(sid))

    def test_legacy_without_timestamp_does_not_invent_import_date(self):
        store = Store(self.root / "workspace", legacy_root=self.root)
        sid = seed_original(store, name="Synthetic original", url="https://original.example/", property_url="https://original.example/")
        data = self.root / "data" / "unknown-time"
        reports = self.root / "reports" / data.name
        data.mkdir(parents=True); reports.mkdir(parents=True)
        (data / "manifest.json").write_text(json.dumps({"url": "https://original.example/", "site": "https://original.example/"}))
        with self.assertRaises(ValueError):
            register_legacy(store, sid, data, reports)
        self.assertFalse(store.audits(sid))

    def test_snapshot_rejects_prior_outputs_before_network_or_writes(self):
        config = SiteConfig(name="Synthetic", url="https://original.example/", gsc_property="https://original.example/")
        data, reports = self.root / "data", self.root / "reports"
        data.mkdir(); reports.mkdir()
        existing = data / "manifest.json"
        existing.write_text("Historical evidence")
        ctx = AuditContext(new_id(), new_id(), config, data, reports)
        service, crawler = Mock(), Mock()
        with self.assertRaises(ValueError):
            run_snapshot(ctx, service, crawl_fn=crawler)
        crawler.assert_not_called()
        service.searchanalytics.assert_not_called()
        self.assertEqual(existing.read_text(), "Historical evidence")

    def test_unavailable_public_pages_keep_live_snapshot_partial(self):
        import pandas as pd
        config = SiteConfig(name="Synthetic", url="https://original.example/", gsc_property="https://original.example/")
        for i, status in enumerate((202, "202", "blocked_by_robots", "request_error")):
            ctx = AuditContext(new_id(), new_id(), config, self.root / f"data-{i}", self.root / f"reports-{i}")
            def unavailable_crawl(url, path, **kwargs):
                frame = pd.DataFrame([{"url": url, "final_url": url, "status": status}])
                frame.to_csv(path, index=False)
                return frame
            manifest, _ = run_snapshot(ctx, SyntheticService(config), crawl_fn=unavailable_crawl)
            self.assertEqual(manifest["stages"]["gsc_current"]["status"], "complete")
            self.assertEqual(manifest["stages"]["crawl"]["status"], "partial")
            self.assertEqual(manifest["stages"]["crawl"]["unavailable_page_count"], 1)
            self.assertEqual(manifest["status"], "partial")
            self.assertIn("unavailable", (ctx.reports_dir / "executive-summary.md").read_text())

    def test_select_connection_changes_only_named_site_after_access_validation(self):
        store = Store(self.root / "workspace")
        old, new = store.add_connection("Old"), store.add_connection("New")
        a = store.save_site(SiteConfig(name="A", url="https://a.example/", gsc_property="https://a.example/", connection_id=old))
        b = store.save_site(SiteConfig(name="B", url="https://b.example/", gsc_property="https://b.example/", connection_id=old))
        argv = ["seo_agent", "--workspace", str(store.root), "select-connection", "--site-id", a, "--connection", new]
        with patch("sys.argv", argv), patch("seo_agent.__main__.Store", return_value=store), patch("seo_agent.credentials.load_connection"), patch("seo_agent.gsc.service_for_credentials"), patch("seo_agent.gsc.validate_access", side_effect=ValueError("No exact property access")), redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                main()
        self.assertEqual(store.site(a).connection_id, old)
        with patch("sys.argv", argv), patch("seo_agent.__main__.Store", return_value=store), patch("seo_agent.credentials.load_connection"), patch("seo_agent.gsc.service_for_credentials"), patch("seo_agent.gsc.validate_access") as validate, redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 0)
        self.assertEqual(validate.call_args.args[1:], ("https://a.example/", "https://a.example/"))
        self.assertEqual(store.site(a).connection_id, new)
        self.assertEqual(store.site(b).connection_id, old)


if __name__ == "__main__":
    unittest.main()
