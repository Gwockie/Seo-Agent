import copy
import json
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from seo_agent import discovery as d, publishing
from seo_agent.backup import _backup, _restore
from seo_agent.config import SiteConfig, SCOPE
from seo_agent.coordination import run_lock, workspace_lock, BusyError
from seo_agent.discovery_client import DiscoveryReader, DiscoveryVault, SERVICE
from seo_agent.discovery_models import ISOLATION, parse, safe_data
from seo_agent.wordpress import CMSFailure
from seo_agent.storage import Store, config_hash


RAW = json.dumps([{"id": "container1", "elType": "container", "settings": {}, "elements": [
    {"id": "heading1", "elType": "widget", "widgetType": "heading", "settings": {
        "title": "Synthetic service", "header_size": "h1"}, "elements": []}]}])
HTML = ('<html><head><meta name="generator" content="WordPress synthetic"></head><body>'
        '<div data-elementor-type="wp-page" data-elementor-id="9001"><div data-id="container1">'
        '<div data-id="heading1" data-widget_type="heading.default"><h1>Synthetic service</h1>'
        '</div></div></div></body></html>')


class Vault:
    def __init__(self):
        self.values = {}
    def write(self, key, user, password):
        self.values[key] = (user, password)
    def read(self, key):
        return self.values[key]


class FakeReader:
    def __init__(self, c):
        self.c = c
    def public(self, ids):
        return {"pages": [{"id": 9001, "url": self.c["url"] + "service/", "type": "page", "status": "publish", "template": "default"}],
                "captures": [{"page_id": 9001, "url": self.c["url"] + "service/", "html": HTML, "response_sha256": "0" * 64}],
                "clues": [{"kind": "plugin", "value": "elementor"}], "missing": []}
    def authenticated(self, ids):
        return {"pages": [], "software": [], "missing": ["Private metadata requires export"]}
    def close(self):
        pass


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "workspace")
        self.sid = self.store.save_site(SiteConfig(name="Synthetic A", url="https://example.com/", gsc_property="sc-domain:example.com"))
        self.other = self.store.save_site(SiteConfig(name="Synthetic B", url="https://other.example/", gsc_property="sc-domain:other.example"))
        self.values = dict(label="Production", provider="Unknown", method="public", url="https://example.com/", environment="production", installation_id="synthetic-A")
        self.cid = d.configure(self.store, self.sid, self.values)
        self.protection = patch("seo_agent.discovery.require_protected")
        self.protection.start()
    def tearDown(self):
        self.protection.stop()
        self.tmp.cleanup()
    def bundle(self):
        value = d.export_template(self.store, self.sid, self.cid)
        c = d.connection(self.store, self.sid, self.cid)
        value.update(source_reference="Synthetic administrator export", software=[dict(kind="plugin", name="elementor", version="synthetic", active=True)],
                     complete_inventory=["plugin", "mu_plugin", "dropin"],
                     pages=[dict(id=9001, url=c["url"] + "service/", template="default", raw_excerpt="Synthetic explicit excerpt", raw_content="Synthetic mirror",
                                 metadata=[dict(row_id=42, key="_elementor_data", value=RAW)], shared_ids=[])])
        return value
    def import_bundle(self, value=None):
        path = self.root / "administrator.json"
        path.write_text(json.dumps(value or self.bundle()), encoding="utf-8")
        return d.import_evidence(self.store, self.sid, self.cid, path)
    def seed(self):
        d.refresh(self.store, self.sid, self.cid, [9001], client_factory=FakeReader)
        return self.import_bundle()

    def test_setup_site_scope_and_permission_separation(self):
        self.assertIsNone(publishing.destination(self.store, self.sid))
        for table in ("cms_authorizations", "cms_reviews", "cms_attempts"):
            self.assertEqual(publishing.rows(self.store, self.sid, table), [])
        with self.assertRaises(ValueError):
            d.connection(self.store, self.other, self.cid)
        self.assertEqual(d.connections(self.store, self.other), [])
        self.assertEqual(SCOPE, "https://www.googleapis.com/auth/webmasters.readonly")

    def test_unknown_installation_allowed_but_cannot_import_or_claim_identity(self):
        d.configure(self.store, self.sid, {**self.values, "installation_id": ""}, cid=self.cid)
        d.refresh(self.store, self.sid, self.cid, client_factory=FakeReader)
        self.assertIn("Independent installation identity", d.compatibility(self.store, self.sid, self.cid)["missing"])
        with self.assertRaises(ValueError):
            self.import_bundle()

    def test_bound_versions_clues_and_assertions_never_publication(self):
        self.seed()
        report = d.compatibility(self.store, self.sid, self.cid)
        self.assertFalse(report["publishing_compatible"])
        self.assertTrue(report["confirmed"])
        self.assertTrue(report["inferred"])
        self.assertTrue(report["administrator_asserted"])
        rows = d.records(self.store, self.sid, self.cid)
        self.assertEqual([r["version"] for r in rows], [2, 1])
        self.assertEqual(rows[0]["payload"]["body"]["scope"]["profile_hash"], config_hash(self.store.site(self.sid)))
        self.assertFalse(rows[0]["payload"]["compatibility_at_collection"]["publishing_compatible"])

    def test_failure_preserves_success_and_age_without_exception_content(self):
        self.seed()
        before = d.records(self.store, self.sid, self.cid)
        with patch.object(FakeReader, "public", side_effect=RuntimeError("PASSWORD-SENTINEL")):
            with self.assertRaises(ValueError) as error:
                d.refresh(self.store, self.sid, self.cid, client_factory=FakeReader)
        self.assertNotIn("PASSWORD-SENTINEL", str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)
        self.assertEqual(d.records(self.store, self.sid, self.cid), before)
        self.assertEqual(d.attempts(self.store, self.sid, self.cid)[0]["status"], "failed")

    def test_stale_import_is_visible_but_not_current(self):
        value = self.bundle()
        value["collected_utc"] = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        self.import_bundle(value)
        row = d.records(self.store, self.sid, self.cid)[0]
        self.assertEqual(d.status(self.store, self.sid, self.cid, row), "stale")
        self.assertIsNone(d.latest(self.store, self.sid, self.cid, "administrator_export"))

    def test_wrong_site_url_environment_profile_installation_dates_rejected(self):
        original = self.bundle()
        for key, val in (("site_id", self.other), ("site_url", "https://other.example/"), ("cms_url", "https://other.example/"),
                         ("environment", "staging"), ("profile_hash", "f" * 64), ("installation_id", "other-installation"),
                         ("collected_utc", "2099-01-01T00:00:00+00:00"), ("collected_utc", "2026-01-01")):
            with self.subTest(key=key, value=val), self.assertRaises(ValueError):
                self.import_bundle({**original, key: val})
        self.assertEqual(d.records(self.store, self.sid, self.cid), [])

    def test_sensitive_extra_keys_duplicate_ids_and_oversize_rejected(self):
        for change in ({"options": {"api_key": "SENTINEL"}}, {"password": "SENTINEL"}, {"customer_submissions": []}):
            with self.assertRaises(ValueError):
                self.import_bundle({**self.bundle(), **change})
        value = self.bundle()
        value["pages"][0]["metadata"][0]["value"] = '[{"settings":{"api_key":"SENTINEL"}}]'
        with self.assertRaises(ValueError):
            self.import_bundle(value)
        value = self.bundle()
        value["pages"].append(copy.deepcopy(value["pages"][0]))
        with self.assertRaises(ValueError):
            self.import_bundle(value)
        with self.assertRaises(ValueError):
            parse('{"schema_version":1,"schema_version":1}')
        path = self.root / "oversized.json"
        path.write_bytes(b"x" * (d.MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            d.import_evidence(self.store, self.sid, self.cid, path)

    def test_empty_builtin_dynamic_tags_import_as_evidence_but_cannot_map(self):
        d.refresh(self.store, self.sid, self.cid, [9001], client_factory=FakeReader)
        value = self.bundle()
        data = json.loads(RAW)
        settings = data[0]["elements"][0]["settings"]
        settings.update(title="", __dynamic__={
            "title": '[elementor-tag id="a0123bc" name="post-title" settings="%7B%7D"]',
            "link": '[elementor-tag id="b0123cd" name="post-url" settings="%7b%7d"]',
        })
        raw = json.dumps(data, indent=2)
        value["pages"][0]["metadata"][0]["value"] = raw
        self.import_bundle(value)
        saved = d.latest(self.store, self.sid, self.cid, "administrator_export")
        self.assertEqual(saved["payload"]["body"]["data"]["pages"][0]["metadata"][0]["value"], raw)
        self.assertFalse(d.compatibility(self.store, self.sid, self.cid)["publishing_compatible"])
        with self.assertRaises(CMSFailure):
            d.prepare_mapping(self.store, self.sid, self.cid, 9001, "heading1", "After")
        self.assertIsNone(d.latest(self.store, self.sid, self.cid, "mapping"))
        self.assertIsNone(publishing.destination(self.store, self.sid))
        for table in ("cms_authorizations", "cms_reviews", "cms_attempts"):
            self.assertEqual(publishing.rows(self.store, self.sid, table), [])

    def test_dynamic_tag_exception_is_exact_and_does_not_hide_secrets(self):
        tag = '[elementor-tag id="a0123bc" name="post-title" settings="%7B%7D"]'
        rejected = [tag.replace('post-title', 'post-custom-field'),
                    tag.replace('%7B%7D', '%7B%22api_key%22%3A%22SENTINEL%22%7D'),
                    tag.replace('%7B%7D', '%257B%257D'), tag + ' trailing',
                    tag.replace('a0123bc', 'a' * 32),
                    tag.replace(' settings=', ' token="SENTINEL" settings='),
                    tag.replace(' settings=', ' name="post-url" settings='),
                    tag.replace('%7B%7D', '{}'), '[elementor-tag',
                    '{"api_key":"SENTINEL"}', '[{"password":"SENTINEL"}]']
        for text in rejected:
            with self.subTest(text=text), self.assertRaises(ValueError) as error:
                safe_data({"__dynamic__": {"title": text}})
            self.assertNotIn("SENTINEL", str(error.exception))
        for value in (tag, {"title": tag}, {"__dynamic__": {"nested": {"title": tag}}},
                      {"__dynamic__": {"api_key": tag}}, {"__dynamic__": {"title": tag, "secret": "SENTINEL"}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_data(value)
        nested = {"__dynamic__": {"title": tag}}
        for _ in range(35):
            nested = {"child": nested}
        with self.assertRaises(ValueError):
            safe_data(nested)

    def test_protected_path_gate_and_history_not_importable(self):
        self.seed()
        path = self.root / "history.json"
        d.export_file(self.store, self.sid, self.cid, path)
        with self.assertRaises(ValueError):
            d.import_evidence(self.store, self.sid, self.cid, path)
        with patch("seo_agent.discovery.require_protected", side_effect=ValueError("not protected")):
            with self.assertRaises(ValueError):
                d.import_evidence(self.store, self.sid, self.cid, path)
            with self.assertRaises(ValueError):
                d.export_file(self.store, self.sid, self.cid, self.root / "blocked.json")
        self.assertFalse((self.root / "blocked.json").exists())

    def test_config_and_destination_changes_invalidate_evidence(self):
        self.seed()
        config = self.store.site(self.sid)
        config.location = "New synthetic location"
        self.store.save_site(config, self.sid)
        self.assertTrue(all(d.status(self.store, self.sid, self.cid, r) == "invalidated" for r in d.records(self.store, self.sid, self.cid)))
        self.seed()
        d.configure(self.store, self.sid, {**self.values, "installation_id": "different-install"}, cid=self.cid)
        self.assertTrue(all(d.status(self.store, self.sid, self.cid, r) == "invalidated" for r in d.records(self.store, self.sid, self.cid)))

    def test_profile_change_during_network_collection_cannot_stamp_new_scope(self):
        original = FakeReader.public
        def change(reader, ids):
            config = self.store.site(self.sid)
            config.location = "Changed while network request was pending"
            self.store.save_site(config, self.sid)
            return original(reader, ids)
        with patch.object(FakeReader, "public", change), self.assertRaises(ValueError):
            d.refresh(self.store, self.sid, self.cid, client_factory=FakeReader)
        self.assertEqual(d.records(self.store, self.sid, self.cid), [])
        self.assertEqual(d.attempts(self.store, self.sid, self.cid)[0]["status"], "failed")

    def test_credential_rotation_keeps_installation_but_never_uses_publisher_vault(self):
        vault = Vault()
        args = {**self.values, "method": "wordpress_rest"}
        d.configure(self.store, self.sid, args, cid=self.cid, username="synthetic-user", password="SYNTHETIC-SECRET", vault=vault)
        before = d.connection(self.store, self.sid, self.cid)
        d.configure(self.store, self.sid, args, cid=self.cid, username="synthetic-user", password="ROTATED-SECRET", vault=vault)
        after = d.connection(self.store, self.sid, self.cid)
        self.assertEqual(before["generation"], after["generation"])
        self.assertEqual(before["installation_id"], after["installation_id"])
        self.assertNotEqual(before["credential_id"], after["credential_id"])
        self.assertNotIn(b"SYNTHETIC-SECRET", self.store.db_path.read_bytes())
        self.assertNotIn(b"ROTATED-SECRET", self.store.db_path.read_bytes())
        self.assertNotEqual(SERVICE, "LocalSEOAudit.WordPress.v1")
        self.assertNotEqual(SERVICE, "LocalSEOAudit.Google.v1")

    def test_vault_exact_backend_roundtrip_and_failure_redaction(self):
        class Backend:
            def set_password(self, service, key, value):
                self.record = service, key, value
            def get_password(self, service, key):
                return self.record[2]
        class Validated:
            backend = Backend()
        with patch("seo_agent.discovery_client.WindowsVault", return_value=Validated()):
            vault = DiscoveryVault()
            vault.write("a" * 32, "synthetic", "test-only")
            self.assertEqual(vault.read("a" * 32), ("synthetic", "test-only"))
            self.assertEqual(vault.backend.record[0], SERVICE)
            with patch.object(vault.backend, "set_password", side_effect=RuntimeError("SECRET")):
                with self.assertRaises(ValueError) as error:
                    vault.write("a" * 32, "synthetic", "test-only")
                self.assertNotIn("SECRET", str(error.exception))
                self.assertTrue(error.exception.__suppress_context__)
        with patch("seo_agent.discovery_client.WindowsVault", side_effect=ValueError("backend unavailable")):
            with self.assertRaises(ValueError):
                DiscoveryVault()

    def test_workspace_lock_prevents_credentials_reads_and_mutations(self):
        with run_lock(workspace_lock(self.store.root)):
            for call in (lambda: d.configure(self.store, self.sid, self.values),
                         lambda: d.refresh(self.store, self.sid, self.cid, client_factory=FakeReader),
                         lambda: self.import_bundle(), lambda: d.disconnect(self.store, self.sid, self.cid)):
                with self.assertRaises(BusyError):
                    call()

    def test_operational_urls_and_nonfixed_routes_are_not_read(self):
        from seo_agent.discovery_client import page_url
        for path in ("wp-admin/", "wp-cron.php", "wp-login.php/", "wp-json/", "../outside", "%2e%2e/"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                page_url("https://example.com/", "https://example.com/" + path)
        reader = DiscoveryReader(dict(url="https://example.com/", environment="production", method="public"))
        with patch.object(reader.session, "get") as get:
            with self.assertRaises(ValueError):
                reader._get("?rest_route=/wp/v2/settings")
            get.assert_not_called()
        reader.close()

    def test_mapping_cross_checks_independent_identity_and_invalidates_on_refresh(self):
        self.seed()
        d.prepare_mapping(self.store, self.sid, self.cid, 9001, "heading1", "Revised synthetic service")
        row = d.latest(self.store, self.sid, self.cid, "mapping")
        self.assertFalse(row["payload"]["body"]["data"]["publishing_compatible"])
        self.assertEqual(row["payload"]["body"]["data"]["metadata_row_id"], 42)
        self.assertEqual(row["payload"]["body"]["data"]["mapping"]["path"], [0, "elements", 0, "settings", "title"])
        d.refresh(self.store, self.sid, self.cid, [9001], client_factory=FakeReader)
        self.assertEqual(d.status(self.store, self.sid, self.cid, row), "invalidated")

    def test_mapping_import_alone_wrong_template_shared_nested_document_rejected(self):
        self.import_bundle()
        with self.assertRaises(ValueError):
            d.prepare_mapping(self.store, self.sid, self.cid, 9001, "heading1", "After")
        self.seed()
        for field, value in (("template", "different"), ("shared_ids", [9002]), ("raw_excerpt", None)):
            bundle = self.bundle()
            bundle["pages"][0][field] = value
            self.import_bundle(bundle)
            with self.assertRaises(ValueError):
                d.prepare_mapping(self.store, self.sid, self.cid, 9001, "heading1", "After")
        self.seed()
        original = FakeReader.public
        def nested(reader, ids):
            data = original(reader, ids)
            data["captures"][0]["html"] = HTML.replace('<div data-id="container1">', '<div data-elementor-id="9002"><div data-id="container1">').replace('</body>', '</div></body>')
            return data
        with patch.object(FakeReader, "public", nested):
            d.refresh(self.store, self.sid, self.cid, [9001], client_factory=FakeReader)
        with self.assertRaises(ValueError):
            d.prepare_mapping(self.store, self.sid, self.cid, 9001, "heading1", "After")

    def test_staging_requires_concrete_all_condition_evidence_plus_human_review(self):
        production_id = self.cid
        with self.assertRaises(ValueError):
            d.configure(self.store, self.sid, {**self.values, "environment": "staging", "url": "https://stage.example.com/"})
        self.cid = d.configure(self.store, self.sid, {**self.values, "environment": "staging", "url": "https://stage.example.com/", "installation_id": "stage-install"})
        with self.assertRaises(ValueError):
            d.review_isolation(self.store, self.sid, self.cid, human_clicked=True, source="Synthetic human review")
        value = self.bundle()
        value["host"] = [dict(area=area, result="isolated", production_resource="production-" + area,
                              environment_resource="staging-" + area, observation="Synthetic independent resource verified in host evidence",
                              source_reference="Synthetic host record " + area) for area in ISOLATION]
        self.import_bundle(value)
        with self.assertRaises(ValueError):
            d.review_isolation(self.store, self.sid, self.cid, human_clicked=True, source="Synthetic human review")
        identity = next(h for h in value["host"] if h["area"] == "installation_identity")
        identity.update(production_resource="synthetic-A", environment_resource="stage-install")
        self.import_bundle(value)
        self.assertEqual(d.isolation_status(self.store, self.sid, self.cid)["status"], "unknown_keep_work_local")
        d.review_isolation(self.store, self.sid, self.cid, human_clicked=True, source="Synthetic human reviewed host records")
        self.assertEqual(d.isolation_status(self.store, self.sid, self.cid)["status"], "human_reviewed_isolation")
        review = d.latest(self.store, self.sid, self.cid, "isolation_review")
        self.assertIsNone(publishing.destination(self.store, self.sid))
        d.disconnect(self.store, self.sid, production_id)
        self.assertEqual(d.isolation_status(self.store, self.sid, self.cid)["status"], "unknown_keep_work_local")
        self.assertEqual(d.status(self.store, self.sid, self.cid, review), "invalidated")
        d.configure(self.store, self.sid, self.values, cid=production_id)
        self.assertEqual(d.isolation_status(self.store, self.sid, self.cid)["status"], "unknown_keep_work_local")
        self.import_bundle(value)
        self.assertEqual(d.isolation_status(self.store, self.sid, self.cid)["status"], "unknown_keep_work_local")

    def test_backup_detaches_access_and_history_never_becomes_current(self):
        vault = Vault()
        args = {**self.values, "method": "wordpress_rest"}
        d.configure(self.store, self.sid, args, cid=self.cid, username="synthetic", password="SENTINEL", vault=vault)
        self.seed()
        credential_id = d.connection(self.store, self.sid, self.cid)["credential_id"]
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        with zipfile.ZipFile(archive) as z:
            self.assertNotIn(credential_id.encode(), z.read("metadata.sqlite"))
            self.assertNotIn(b"SENTINEL", z.read("metadata.sqlite"))
        restored = _restore(archive, self.root / "restored")
        c = d.connection(restored, self.sid, self.cid)
        self.assertFalse(c["enabled"])
        self.assertIsNone(c["credential_id"])
        with self.assertRaises(ValueError):
            d.refresh(restored, self.sid, self.cid, client_factory=FakeReader)
        with self.assertRaises(ValueError):
            d.configure(restored, self.sid, args, cid=self.cid)
        d.configure(restored, self.sid, args, cid=self.cid, username="synthetic", password="new", vault=vault)
        self.assertTrue(all(d.status(restored, self.sid, self.cid, r) == "invalidated" for r in d.records(restored, self.sid, self.cid)))

    def test_database_only_backup_obeys_size_limit_before_creating_archive(self):
        self.seed()
        archive = self.root / "oversized-backup.zip"
        with patch("seo_agent.backup.MAX_BACKUP_BYTES", 1), self.assertRaises(ValueError):
            _backup(self.store, archive)
        self.assertFalse(archive.exists())

    def test_v6_additive_migration_preserves_publication_tables(self):
        with self.store.db() as db:
            for table in ("discovery_attempts", "discovery_evidence", "discovery_connections"):
                db.execute("DROP TABLE " + table)
            db.execute("PRAGMA user_version=6")
        migrated = Store(self.store.root)
        with migrated.db() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 7)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(migrated.site(self.sid).url, "https://example.com/")
        self.assertIsNone(publishing.destination(migrated, self.sid))


class ReaderLoopbackTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.response_mode = "ok"
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                outer.calls.append((self.command, self.path, self.headers.get("Authorization")))
                if outer.response_mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1:1/leak")
                    self.end_headers()
                    return
                if self.path in ("/", "/service/"):
                    body, mime = HTML, "text/html"
                elif "themes" in self.path or "plugins" in self.path:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"PRIVATE-FAILURE-SENTINEL")
                    return
                else:
                    data = dict(id=9001, link=outer.url + "service/", type="page", status="publish", template="default")
                    if "context=edit" in self.path:
                        data.update(content={"raw": "Synthetic content"}, excerpt={"raw": "Synthetic excerpt"})
                    body, mime = json.dumps(data), "application/json"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.end_headers()
                self.wfile.write(body.encode())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.vault = Vault()
        self.vault.write("a" * 32, "synthetic", "test-only")
        self.reader = DiscoveryReader(dict(url=self.url, environment="local", method="wordpress_rest", credential_id="a" * 32), vault=self.vault)
    def tearDown(self):
        self.reader.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
    def test_fixed_gets_credentials_only_on_authenticated_routes_and_partial_inventory(self):
        public = self.reader.public([9001])
        self.assertEqual(public["pages"][0]["id"], 9001)
        self.assertTrue(all(auth is None for _, _, auth in self.calls))
        auth = self.reader.authenticated([9001])
        self.assertEqual(auth["pages"][0]["raw_excerpt"], "Synthetic excerpt")
        self.assertTrue(auth["missing"])
        self.assertTrue(all(method == "GET" for method, _, _ in self.calls))
        self.assertEqual(len(self.calls), 6)
        self.assertFalse(self.reader.session.trust_env)
        with self.assertRaises(ValueError):
            self.reader._get("?rest_route=/wp/v2/settings", authenticated=True)
    def test_redirect_not_followed_or_retried_and_budget_enforced(self):
        self.response_mode = "redirect"
        with self.assertRaises(ValueError) as error:
            self.reader.public([9001])
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("127.0.0.1", str(error.exception))
        self.reader.requests = 48
        with self.assertRaises(ValueError):
            self.reader._get("", html=True)
        self.assertEqual(len(self.calls), 1)
    def test_hosted_tls_and_public_address_pinning(self):
        from seo_agent.public_fetch import PublicAdapter
        for url, environment in (("http://example.com/", "production"), ("https://example.com/", "local")):
            with self.assertRaises(ValueError):
                DiscoveryReader(dict(url=url, environment=environment, method="public"))
        reader = DiscoveryReader(dict(url="https://example.com/", environment="production", method="public"))
        try:
            self.assertIsInstance(reader.session.get_adapter("https://example.com/"), PublicAdapter)
            self.assertEqual(reader.session.get_adapter("https://example.com/").max_retries.total, 0)
        finally:
            reader.close()

    def test_escaped_echoed_passwords_are_rejected_before_persistence(self):
        for password in ('synthetic-"quote', 'synthetic-\\slash', 'synthetic-\u00e9'):
            self.vault.write("a" * 32, "synthetic", password)
            for echoed in (password, json.dumps(password)[1:-1]):
                data = dict(id=9001, link=self.url + "service/", type="page", status="publish", template="default",
                            content={"raw": echoed}, excerpt={"raw": "Synthetic excerpt"})
                with patch.object(self.reader, "_get", side_effect=[data, [], []]), self.assertRaises(ValueError) as error:
                    self.reader.authenticated([9001])
                self.assertNotIn(password, str(error.exception))
