import io
import json
import sqlite3
import tempfile
import threading
import time
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from seo_agent.backup import _backup, _restore
from seo_agent.config import SiteConfig, Phrase, RuleOverride, SCOPE, resolve_rules, validate_property, public_url
from seo_agent.credentials import WindowsVault, credential_payload, migrate_legacy, validate_scopes, load_connection, validate_credentials
from seo_agent.demo import seed_demo, SyntheticService, synthetic_crawl
from seo_agent.gsc import validate_access, _query_all
from seo_agent.import_export import export_phrases, import_phrases, report_packet, register_legacy, safe_csv, seed_original
from seo_agent.metrics import totals, windows, query_groups
from seo_agent.public_fetch import PublicFetcher, resolve_public, connect_public, public_address
from seo_agent.rules import generate, read_csv
from seo_agent.runner import AuditContext, Jobs, run_snapshot, run_site, run_lock
from seo_agent.storage import Store, new_id, config_hash


def token(**updates):
    return json.dumps({"token": "SYNTHETIC_ACCESS_SENTINEL", "refresh_token": "SYNTHETIC_REFRESH_SENTINEL", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "synthetic-id", "client_secret": "synthetic-client", "scopes": [SCOPE], "expiry": "2099-01-01T00:00:00Z", **updates})


class FakeVault:
    def __init__(self):
        self.values = {}
    def exists(self, cid):
        return cid in self.values
    def probe(self):
        pass
    def read(self, cid):
        if cid not in self.values:
            raise ValueError("Missing")
        return self.values[cid]
    def write(self, cid, raw):
        self.values[cid] = credential_payload(raw)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "workspace", legacy_root=self.root)
        seed_demo(self.store)
        self.ids = {r["name"]: r["id"] for r in self.store.sites()}
        self.a = self.ids["Demo psychology A"]
        self.b = self.ids["Demo psychology B"]
        self.c = self.ids["Demo electrician"]

    def tearDown(self):
        self.temp.cleanup()

    def test_three_sites_independent_findings_accounts_and_profiles(self):
        audits = {sid: run_site(self.store, sid, demo=True, max_pages=5) for sid in [self.a, self.b, self.c]}
        a, b, c = [self.store.site(s) for s in [self.a, self.b, self.c]]
        self.assertNotEqual(a.connection_id, b.connection_id)
        self.assertNotEqual(a.phrases, b.phrases)
        self.assertNotEqual(a.confirmed_facts, b.confirmed_facts)
        self.assertEqual(resolve_rules(a)["guidance"], resolve_rules(b)["guidance"])
        for sid, aid in audits.items():
            row = self.store.audit(sid, aid)
            self.assertEqual(row["status"], "complete")
            fs = self.store.findings(sid, aid)
            self.assertTrue(fs)
            exported = report_packet(self.store, sid, aid)
            with zipfile.ZipFile(io.BytesIO(exported)) as z:
                self.assertIn("data/comparison/gsc_totals.csv", z.namelist())
                text = b"".join(z.read(n) for n in z.namelist()).decode("utf-8-sig")
                if sid == self.c:
                    self.assertNotIn("clinical_review", text)
                    self.assertNotIn("ADHD", text)
                    self.assertNotIn("Paoli", text)
                    self.assertNotIn("Clinician", text)
                elif sid == self.b:
                    self.assertNotIn(a.url, text)
                    self.assertNotIn(a.phrases[0].phrase, text)
                    self.assertNotIn(a.confirmed_facts["fixture"], text)
            for f in fs:
                self.assertEqual(f["payload"]["site_id"], sid)
                self.assertEqual(f["payload"]["audit_id"], aid)
                self.assertTrue(f["payload"]["evidence"])
        self.assertIn("clinical_review", {f["payload"]["rule"] for f in self.store.findings(self.a, audits[self.a])})
        self.assertNotIn("clinical_review", {f["payload"]["rule"] for f in self.store.findings(self.c, audits[self.c])})

    def test_site_audit_paths_and_foreign_keys(self):
        aid = self.store.create_audit(self.a)
        with self.assertRaises(ValueError):
            self.store.audit(self.b, aid)
        for name in ("../manifest.json", "a/../../token.json", "C:\\secrets\\token.json"):
            with self.assertRaises(ValueError):
                self.store.audit_file(self.a, aid, "data", name)
        with self.store.db() as db:
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO recommendations(id,site_id,audit_id,payload) VALUES (?,?,?,?)", (new_id(), self.b, aid, "{}"))
            db.execute("UPDATE audits SET data_path=? WHERE id=?", (str(self.root / "workspace" / "sites" / self.b), aid))
        with self.assertRaises(ValueError):
            self.store.audit_file(self.a, aid, "data", "manifest.json")

    def test_shared_connection_does_not_un_scope_audits(self):
        a = self.store.site(self.a)
        b = self.store.site(self.b)
        b.connection_id = a.connection_id
        self.store.save_site(b, self.b)
        aid = self.store.create_audit(self.a)
        with self.assertRaises(ValueError):
            self.store.findings(self.b, aid)

    def test_unknown_conflicting_and_immutable_rule_overrides(self):
        for override in [{"bogus": {}}, {"indexing": {"min_impressions": 20}}, {"security": {"enabled": False}}, {"clinical_review": {"enabled": False}}, {"ctr": {"min_impressions": "100"}}]:
            with self.assertRaises(ValueError):
                SiteConfig.model_validate({**self.store.site(self.a).model_dump(), "overrides": override})
        with self.assertRaises(ValueError):
            SiteConfig.model_validate({**self.store.site(self.c).model_dump(), "overrides": {"clinical_review": {}}})
        with self.assertRaises(ValueError):
            SiteConfig.model_validate({**self.store.site(self.a).model_dump(), "profile_version": "2"})

    def test_historical_config_and_findings_are_immutable(self):
        aid = run_site(self.store, self.a, demo=True)
        before = self.store.audit(self.a, aid)
        findings = self.store.findings(self.a, aid)
        config = self.store.site(self.a)
        config.location = "Another town"
        config.overrides = {"ctr": RuleOverride(min_impressions=500)}
        self.store.save_site(config, self.a)
        self.assertEqual(before, self.store.audit(self.a, aid))
        self.assertEqual(findings, self.store.findings(self.a, aid))
        with self.assertRaises(ValueError):
            self.store.save_findings(self.a, aid, [])

    def test_finding_provenance_and_evidence_rejected(self):
        aid = self.store.create_audit(self.a)
        f = {"site_id": self.a, "audit_id": aid, "rule": "made-up", "rule_version": "1.0", "industry": "psychology", "profile_version": "1.0", "evidence": []}
        with self.assertRaises(ValueError):
            self.store.save_findings(self.a, aid, [f])
        f.update(rule="indexing", evidence=[{"file": "crawl.csv", "row": 2}])
        with self.assertRaises(ValueError):
            self.store.save_findings(self.a, aid, [f])

    def test_phrase_csv_scoping_limits_duplicates_and_safe_export(self):
        config = self.store.site(self.a)
        raw = export_phrases(self.a, config)
        self.assertEqual(import_phrases(raw, self.a, config).phrases, config.phrases)
        with self.assertRaises(ValueError):
            import_phrases(raw, self.b, self.store.site(self.b))
        unscoped = b'phrase,group\nsample,service\n'
        with self.assertRaises(ValueError):
            import_phrases(unscoped, self.a, config)
        self.assertEqual(import_phrases(unscoped, self.a, config, associate=True).phrases[0].phrase, "sample")
        for raw in (b'phrase,group\nx,g\nx,g\n', b'x' * (2 * 1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                import_phrases(raw, self.a, config, associate=True)
        exported = safe_csv(pd.DataFrame({"q": ['=HYPERLINK("bad")', "  +1", "@cmd", "normal"]})).decode("utf-8-sig")
        self.assertIn("'@cmd", exported)
        self.assertIn("'  +1", exported)
        self.assertIn("'=evil", safe_csv(pd.DataFrame({"=evil": ["x"]})).decode("utf-8-sig"))

    def test_site_identity_cannot_be_reassigned_to_another_client(self):
        changed = {**self.store.site(self.a).model_dump(), "url": "https://another.example/", "gsc_property": "https://another.example/", "phrases": []}
        with self.assertRaises(ValueError):
            self.store.save_site(SiteConfig.model_validate(changed), self.a)

    def test_private_metadata_writes_fail_without_protected_storage(self):
        with patch("seo_agent.protection.require_protected"):
            gated = Store(self.root / "gated", enforce_protection=True)
        with patch("seo_agent.protection.require_protected", side_effect=ValueError("Protection unavailable")):
            with self.assertRaises(ValueError):
                gated.save_site(self.store.site(self.a))
            with self.assertRaises(ValueError):
                gated.add_connection("Private account")
        self.assertEqual(gated.sites(), [])

    def test_unignored_repository_workspace_rejected_before_creation(self):
        repo = Path(__file__).resolve().parent.parent
        target = repo / ("private-unignored-" + new_id())
        with self.assertRaises(ValueError):
            Store(target)
        self.assertFalse(target.exists())

    def test_exclusions_and_no_receiving_evidence_produce_no_inherited_findings(self):
        config = self.store.site(self.a)
        landing = config.phrases[0].landing_page
        frame = synthetic_crawl(config.url, self.root / "crawl.csv", config=config)
        config.exclusions = [landing]
        self.assertEqual(generate(config, self.a, new_id(), {"crawl": frame}), [])
        self.assertEqual(generate(self.store.site(self.b), self.b, new_id(), {}), [])

    def test_packet_whitelists_evidence_not_credentials(self):
        aid = run_site(self.store, self.a, demo=True)
        base = self.store.audit_file(self.a, aid, "data", "manifest.json").parent
        (base / "client_secret.json").write_text("SYNTHETIC_SECRET_DO_NOT_EXPORT")
        with zipfile.ZipFile(io.BytesIO(report_packet(self.store, self.a, aid))) as z:
            self.assertNotIn("data/client_secret.json", z.namelist())
            self.assertNotIn(b"SYNTHETIC_SECRET_DO_NOT_EXPORT", b"".join(z.read(n) for n in z.namelist()))

    def test_property_exact_access_and_url_relationship(self):
        svc = Mock()
        svc.sites.return_value.list.return_value.execute.return_value = {"siteEntry": [{"siteUrl": "sc-domain:example.com", "permissionLevel": "siteFullUser"}]}
        validate_access(svc, "sc-domain:example.com", "https://www.example.com/")
        for prop, url in [("https://example.com/", "https://example.com/"), ("sc-domain:example.com", "https://example.com.evil.net/")]:
            with self.assertRaises(ValueError):
                validate_access(svc, prop, url)
        for prop, url in [("https://example.com/path/", "https://example.com/pathology/"), ("https://example.com/", "http://example.com/")]:
            with self.assertRaises(ValueError):
                validate_property(prop, url)

    def test_missing_sources_partial_and_empty_not_zero(self):
        config = self.store.site(self.a)
        for suffix, svc in [("none", None), ("failed", Mock())]:
            if svc:
                svc.searchanalytics.return_value.query.side_effect = RuntimeError("SECRET_SENTINEL")
            ctx = AuditContext(self.a, new_id(), config, self.root / suffix / "data", self.root / suffix / "reports", max_pages=5)
            manifest, fs = run_snapshot(ctx, svc, crawl_fn=synthetic_crawl)
            self.assertEqual(manifest["status"], "partial")
            self.assertNotIn("SECRET_SENTINEL", json.dumps(manifest))
            self.assertFalse(totals(read_csv(ctx.data_dir / "gsc_totals.csv"))["available"])
        svc = SyntheticService(config)
        svc.query = lambda **kwargs: type("R", (), {"execute": lambda self: {"rows": []}})()
        ctx = AuditContext(self.a, new_id(), config, self.root / "empty/data", self.root / "empty/reports")
        manifest, _ = run_snapshot(ctx, svc, crawl_fn=synthetic_crawl)
        self.assertEqual(manifest["stages"]["gsc_current"]["observation"], "empty export; demand unknown")

    def test_old_files_registered_without_rewriting(self):
        data = self.root / "data" / "20261005"
        reports = self.root / "reports" / "20261005"
        data.mkdir(parents=True); reports.mkdir(parents=True)
        config = self.store.site(self.a)
        raw = json.dumps({"site": config.gsc_property, "url": config.url, "created_utc": "20261005T000000Z"})
        (data / "manifest.json").write_text(raw)
        (reports / "snapshot.md").write_text("Original private narrative")
        aid = register_legacy(self.store, self.a, data, reports)
        self.assertEqual(self.store.audit_file(self.a, aid, "reports", "snapshot.md"), reports / "snapshot.md")
        self.assertEqual((data / "manifest.json").read_text(), raw)
        with self.assertRaises(ValueError):
            register_legacy(self.store, self.b, data, reports)
        (data / "manifest.json").write_text(json.dumps({"url": config.url}))
        with self.assertRaises(ValueError):
            register_legacy(self.store, self.a, data, reports)

    def test_seed_original_only_has_known_goals_and_user_reported_change(self):
        sid = seed_original(self.store, name="Original", url="https://original.example/", property_url="https://original.example/")
        config = self.store.site(sid)
        self.assertEqual(len(config.phrases), 10)
        self.assertEqual(config.confirmed_facts, {})
        self.assertIn("user-reported", self.store.changes(sid)[0]["verification"])

    def test_backup_restore_excludes_secrets_and_detaches_accounts(self):
        aid = run_site(self.store, self.a, demo=True)
        self.store.add_change(self.a, date="2026-10-06", action="Synthetic observed change")
        (self.root / "token.json").write_text("NEVER_BACK_UP_TOKEN")
        destination = self.root / "backup.zip"
        _backup(self.store, destination)
        with zipfile.ZipFile(destination) as z:
            self.assertNotIn("token.json", z.namelist())
            self.assertNotIn(b"NEVER_BACK_UP_TOKEN", b"".join(z.read(n) for n in z.namelist()))
        restored = _restore(destination, self.root / "restored")
        self.assertEqual(restored.site(self.a).phrases, self.store.site(self.a).phrases)
        self.assertIsNone(restored.site(self.a).connection_id)
        self.assertEqual(restored.changes(self.a), self.store.changes(self.a))
        self.assertEqual(restored.findings(self.a, aid), self.store.findings(self.a, aid))
        self.assertTrue(restored.audit_file(self.a, aid, "data", "crawl.csv").exists())

    def test_zip_traversal_rejected_before_extracting(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../token.json", "bad")
        with self.assertRaises(ValueError):
            _restore(archive, self.root / "bad-restore")
        self.assertFalse((self.root / "token.json").exists())

    def test_job_duplicate_and_inflight_site_isolation(self):
        started, release = threading.Event(), threading.Event()
        count = []
        def fake_run(store, sid, **kwargs):
            count.append(sid)
            started.set()
            release.wait(5)
            return kwargs["request_id"]
        jobs = Jobs()
        rid = new_id()
        with patch("seo_agent.runner.run_site", side_effect=fake_run):
            key = jobs.submit(self.store, self.a, rid)
            self.assertTrue(started.wait(3))
            self.assertEqual(jobs.submit(self.store, self.a, rid), key)
            with self.assertRaises(ValueError):
                jobs.submit(self.store, self.b, new_id())
            self.assertEqual(jobs.snapshot(key)["site_id"], self.a)
            release.set()
            jobs.executor.shutdown(wait=True)
        self.assertEqual(count, [self.a])

    def test_persistent_request_id_idempotent_and_config_change_rejected(self):
        rid = new_id()
        run_site(self.store, self.a, request_id=rid, demo=True)
        run_site(self.store, self.a, request_id=rid, demo=True)
        self.assertEqual(len(self.store.audits(self.a)), 1)
        with self.assertRaises(ValueError):
            run_site(self.store, self.a, request_id=new_id(), expected_config_hash="wrong", demo=True)


class MetricsTests(unittest.TestCase):
    def test_weighted_metrics_and_missing_rows(self):
        df = pd.DataFrame({"clicks": [1, 18], "impressions": [10, 90], "position": [1, 11], "ctr": [.1, .2]})
        result = totals(df)
        self.assertAlmostEqual(result["ctr"], .19)
        self.assertAlmostEqual(result["position"], 10)
        self.assertFalse(totals(pd.DataFrame())["available"])

    def test_complete_adjacent_windows_across_leap_year(self):
        result = windows(28, today=date(2024, 3, 4))
        current, previous = result["current"], result["previous"]
        self.assertEqual(current["end"], "2024-03-01")
        self.assertEqual((date.fromisoformat(current["end"]) - date.fromisoformat(current["start"])).days, 27)
        self.assertEqual((date.fromisoformat(current["start"]) - date.fromisoformat(previous["end"])).days, 1)
        self.assertEqual((date.fromisoformat(previous["end"]) - date.fromisoformat(previous["start"])).days, 27)
        with self.assertRaises(ValueError):
            windows(lag_days=0)

    def test_gsc_final_web_and_aggregation_explicit(self):
        svc = Mock()
        svc.searchanalytics.return_value.query.return_value.execute.return_value = {"rows": []}
        _query_all(svc, "https://example.com/", "2026-08-01", "2026-08-28", ["query", "page"])
        body = svc.searchanalytics.return_value.query.call_args.kwargs["body"]
        self.assertEqual(body["dataState"], "final")
        self.assertEqual(body["type"], "web")
        self.assertEqual(body["aggregationType"], "byPage")
        _query_all(svc, "https://example.com/", "2026-08-01", "2026-08-28", [])
        self.assertEqual(svc.searchanalytics.return_value.query.call_args.kwargs["body"]["aggregationType"], "byProperty")


class CredentialTests(unittest.TestCase):
    def test_unexpected_granted_scope_rejected_after_refresh(self):
        vault = FakeVault()
        cid = new_id()
        raw = token()
        vault.write(cid, raw)
        creds = Mock(scopes=[SCOPE], granted_scopes=None, expired=True, refresh_token="synthetic", valid=True)
        def refresh(_):
            creds.granted_scopes = [SCOPE, "unexpected"]
        creds.refresh.side_effect = refresh
        with patch("seo_agent.credentials.Credentials.from_authorized_user_info", return_value=creds):
            with self.assertRaises(ValueError):
                load_connection(cid, vault)
        self.assertEqual(vault.read(cid), raw)

    def test_legacy_token_read_validates_endpoint_universe_without_rewriting(self):
        from seo_agent.auth import get_credentials
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "token.json"
            raw = token()
            path.write_text(raw)
            self.assertEqual(get_credentials(Path(folder)).token, "SYNTHETIC_ACCESS_SENTINEL")
            self.assertEqual(path.read_text(), raw)
            path.write_text(token(universe_domain="evil.example"))
            with self.assertRaises(ValueError):
                get_credentials(Path(folder))

    def test_scopes_and_payload_limit(self):
        for scopes in ([], [SCOPE, "other"], "other"):
            with self.assertRaises(ValueError):
                validate_scopes(scopes)
        credential_payload(token())
        with self.assertRaises(ValueError):
            credential_payload(token(token="x" * 2000))
        with self.assertRaises(ValueError):
            credential_payload(token(token_uri="https://evil.example/token"))

    def test_insecure_backend_rejected(self):
        with patch("keyring.get_keyring", return_value=Mock()):
            with self.assertRaises(ValueError):
                WindowsVault()

    def test_explicit_connection_and_reconnect_preserve_other_accounts(self):
        vault = FakeVault()
        a, b = new_id(), new_id()
        vault.write(a, token(token="ACCOUNT_A"))
        vault.write(b, token(token="ACCOUNT_B"))
        vault.write(a, token(token="ACCOUNT_A_RECONNECTED"))
        self.assertEqual(load_connection(b, vault).token, "ACCOUNT_B")
        with self.assertRaises(ValueError):
            load_connection(new_id(), vault)
        with self.assertRaises(ValueError):
            vault.write(a, token(scopes=["other"]))
        self.assertEqual(load_connection(a, vault).token, "ACCOUNT_A_RECONNECTED")

    def test_migration_preserves_legacy_and_verifies_property_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "token.json"
            raw = token()
            path.write_text(raw)
            vault = FakeVault()
            config = SiteConfig(name="A", url="https://example.com/", gsc_property="https://example.com/")
            svc = Mock()
            svc.sites.return_value.list.return_value.execute.return_value = {"siteEntry": [{"siteUrl": config.gsc_property, "permissionLevel": "siteOwner"}]}
            cid = new_id()
            migrate_legacy(path, cid, config, vault=vault, service_factory=lambda creds: svc)
            self.assertEqual(path.read_text(), raw)
            self.assertEqual(vault.read(cid), raw)
            with self.assertRaises(ValueError):
                migrate_legacy(path, cid, config, vault=vault, service_factory=lambda creds: svc)
            svc.sites.return_value.list.return_value.execute.return_value = {"siteEntry": []}
            other = new_id()
            with self.assertRaises(ValueError):
                migrate_legacy(path, other, config, vault=vault, service_factory=lambda creds: svc)
            self.assertFalse(vault.exists(other))


class PublicFetchTests(unittest.TestCase):
    def test_direct_urls_ipv4_ipv6_credentials_and_ports(self):
        for url in ["file:///etc/passwd", "https://u:p@example.com/", "http://127.0.0.1/", "http://10.0.0.1/", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://[fe80::1%25eth0]/", "https://example.com:8443/"]:
            with self.assertRaises(ValueError):
                public_url(url)
        self.assertFalse(public_address("::ffff:10.0.0.1"))
        self.assertFalse(public_address("169.254.169.254"))

    def test_mixed_dns_rejected(self):
        public = (2, 1, 6, "", ("93.184.216.34", 443))
        private = (2, 1, 6, "", ("127.0.0.1", 443))
        with patch("socket.getaddrinfo", return_value=[public, private]):
            with self.assertRaises(ValueError):
                resolve_public("example.com", 443)

    def test_connection_pins_numeric_address_and_checks_peer(self):
        address = (2, 1, 6, "", ("93.184.216.34", 443))
        sock = Mock()
        sock.getpeername.return_value = ("93.184.216.34", 443)
        with patch("socket.getaddrinfo", return_value=[address]) as dns, patch("socket.socket", return_value=sock):
            self.assertIs(connect_public("example.com", 443, 5), sock)
            self.assertEqual(dns.call_count, 1)
            sock.connect.assert_called_once_with(("93.184.216.34", 443))
        sock.getpeername.return_value = ("127.0.0.1", 443)
        with patch("socket.getaddrinfo", return_value=[address]), patch("socket.socket", return_value=sock):
            with self.assertRaises(ValueError):
                connect_public("example.com", 443, 5)

    def test_connection_time_dns_change_fails_before_connect(self):
        address = (2, 1, 6, "", ("93.184.216.34", 443))
        private = (2, 1, 6, "", ("10.0.0.1", 443))
        with patch("socket.getaddrinfo", side_effect=[[address], [private]]), patch("socket.socket") as sockets:
            resolve_public("example.com", 443)
            with self.assertRaises(ValueError):
                connect_public("example.com", 443, 5)
            sockets.assert_not_called()

    def test_redirects_robots_tokens_and_size_bounds(self):
        from urllib.robotparser import RobotFileParser
        rp = RobotFileParser(); rp.parse(["User-agent: *", "Disallow: /private"])
        for target in ("http://127.0.0.1/", "https://other.example/", "/private"):
            fetcher = PublicFetcher("https://example.com/")
            response = Mock(status_code=302, headers={"Location": target})
            with patch("seo_agent.public_fetch.resolve_public"), patch.object(fetcher.session, "get", return_value=response) as get:
                with self.assertRaises(ValueError):
                    fetcher.get("https://example.com/", rp=rp)
                self.assertEqual(get.call_count, 1)
                kwargs = get.call_args.kwargs
                self.assertTrue(kwargs["verify"])
                self.assertFalse(kwargs["allow_redirects"])
                self.assertNotIn("Authorization", fetcher.session.headers)
                self.assertFalse(fetcher.session.trust_env)
            fetcher.close()
        fetcher = PublicFetcher("https://example.com/", max_bytes=10)
        response = Mock(status_code=200, headers={"Content-Length": "11"})
        with patch("seo_agent.public_fetch.resolve_public"), patch.object(fetcher.session, "get", return_value=response):
            with self.assertRaises(ValueError):
                fetcher.get("https://example.com/")
        fetcher.close()

    def test_untrusted_sitemap_entities_dtd_rejected(self):
        from seo_agent.crawl import sitemap_urls
        from urllib.robotparser import RobotFileParser
        rp = RobotFileParser(); rp.parse([])
        session = Mock()
        session.get.return_value = Mock(ok=True, status_code=200, headers={"content-type": "application/xml"}, content=b'<!DOCTYPE urlset [<!ENTITY e SYSTEM "file:///secret">]><urlset><url><loc>&e;</loc></url></urlset>')
        self.assertEqual(sitemap_urls("https://example.com/sitemap.xml", session, root_url="https://example.com/", rp=rp), set())


if __name__ == "__main__":
    unittest.main()
