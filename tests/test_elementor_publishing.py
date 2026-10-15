import copy
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent import publishing as p, tracking as t, discovery as d, publisher_setup as setup
from seo_agent import elementor_publishing as ep
from seo_agent.backup import _backup, _restore
from seo_agent.elementor import map_heading, preview_heading
from seo_agent.previews import save_preview
from seo_agent.storage import utc_now
from seo_agent.wordpress import CMSFailure, WordPress
from tests.test_tracking import TrackingFixture
from tests import test_tracking
from tests.test_review_previews import fixture
from tests.test_publishing import Vault
from tests.test_publication_ui import publication_app
from tests.publication_fixtures import staging_connection


RAW = '[ {"id":"root", "elType":"container", "settings":{}, "elements":[' \
      '{"id":"heading1","elType":"widget","widgetType":"heading","settings":{"title":"Our service","header_size":"h1"},"elements":[]},' \
      '{"id":"heading2","elType":"widget","widgetType":"heading","settings":{"title":"Adjacent","header_size":"h2"},"elements":[]}' \
      ']} ]'


class FakeElementor:
    def __init__(self, destination):
        self.destination = destination
        self.raw = RAW
        self.content = '<h1>Our service</h1>\n<h2>Adjacent</h2>'
        self.operations, self.writes = {}, []
        self.timeout = self.reject = self.bad_render = False
        self.token_extra = ""

    def close(self):
        pass

    def state(self, page):
        ms = [map_heading(self.raw, page_id=page, element_id=eid) for eid in ("heading1", "heading2")]
        return dict(protocol=ep.PROTOCOL, contract=ep.CONTRACT, contract_hash=t.digest(ep.contract_manifest()),
            instance=self.destination["instance"], home=self.destination["url"], environment=self.destination["environment"],
            id=page, url=self.destination["url"], type="page", status="publish", supported=True,
            template="elementor_canvas", metadata_row_id=42, elementor_data=self.raw, content=self.content,
            excerpt="Fixed explicit synthetic excerpt", headings=[dict(element_id=m.element_id, path=list(m.path),
                ancestor_ids=list(m.ancestor_ids), tag=m.tag, text=m.current) for m in ms],
            preserved="a" * 64, token=t.digest([self.raw, self.content, self.token_extra]), inventory={"adapter_hash": ep.adapter_hash()})

    def public(self, url):
        text = map_heading(self.raw, page_id=3, element_id="heading1").current
        return dict(html='<html><head><title>Service</title></head><body>'
            '<div data-elementor-type="wp-page" data-elementor-id="3"><div data-id="root">'
            '<div data-id="heading1" data-widget_type="heading.default"><h1>' + text + '</h1></div>'
            '<div data-id="heading2" data-widget_type="heading.default"><h2>' + ('Changed' if self.bad_render else 'Adjacent') + '</h2></div>'
            '</div></div></body></html>', robots="")

    def write(self, page, body):
        self.writes.append(copy.deepcopy(body))
        if self.reject:
            raise CMSFailure("Unavailable")
        if body["request_id"] in self.operations:
            return self.operations[body["request_id"]]
        before = self.state(page)
        if body["token"] != before["token"]:
            raise CMSFailure("Conflict")
        m = map_heading(self.raw, page_id=page, element_id=body["element_id"])
        from seo_agent.elementor import _parse
        _, spans = _parse(self.raw)
        start, end = spans[m.path]
        self.raw = self.raw[:start] + body["replacement_token"] + self.raw[end:]
        self.content = ep.mirror_candidate(self.content, before["headings"], body["element_id"], body["proposed"])
        result = dict(status="applied", request_id=body["request_id"], request=body, before_token=body["token"],
                      after_token=self.state(page)["token"], written_utc=utc_now())
        self.operations[body["request_id"]] = result
        if self.timeout:
            raise CMSFailure("Timeout after commit")
        return result

    def operation(self, page, rid):
        return copy.deepcopy(self.operations.get(rid, {"status": "unknown"}))


class ElementorPublishingTests(TrackingFixture, unittest.TestCase):
    html_snapshot = test_tracking.TrackingTests.html_snapshot

    def setUp(self):
        super().setUp()
        # In-memory protocol tests inject their synthetic fixture, not an app flag.
        # HostingBindingTests exercise the real required evidence boundary separately.
        self.evidence = patch("seo_agent.publisher_setup.evidence_binding", return_value=None)
        self.installation = patch("seo_agent.publisher_setup.validate_installation")
        self.evidence.start()
        self.installation.start()
        self.addCleanup(self.evidence.stop)
        self.addCleanup(self.installation.stop)
        p.configure_from_human_ui(self.store, self.sid, url="http://127.0.0.1:8879/", instance="synthetic-local-elementor",
            environment="local", username="test", password="synthetic-only", isolation="Synthetic separate local database/files with no live services",
            isolation_verified=True, human_clicked=True, vault=Vault(), adapter=ep.ADAPTER)
        self.client = FakeElementor(p.destination(self.store, self.sid))
        self.factory = lambda _: self.client
        bundle = fixture(self.sid, self.aid, self.value["url"])
        page = bundle["pages"][0]
        page["captured_utc"] = utc_now()
        heading = page["tree"]["children"][0]
        page["tree"]["children"] = [dict(id="r3", tag="div", children=[dict(id="r4", tag="div", children=[
            dict(id="r5", tag="div", children=[heading]), dict(id="r6", tag="div", children=[dict(id="r7", tag="h2", children=[dict(text="Adjacent")])])])])]
        save_preview(self.store, self.sid, self.aid, bundle)
        t.from_preview(self.store, self.sid, self.aid, 1)
        saved = t.actions(self.store, self.sid)[0]
        t.save_action(self.store, self.sid, self.aid, {**saved["payload"], "confirmations": [dict(item="Service/location", status="confirmed", source="Synthetic owner")]}, revision=2)
        self.record = t.action(self.store, self.sid, saved["action_id"], 2)
        self.html_snapshot(self.client.public(self.value["url"])["html"])
        self.bid = t.freeze_batch(self.store, self.sid, [(saved["action_id"], 2)])
        t.approve_from_human_ui(self.store, self.sid, self.bid, human_clicked=True,
            statement="I approve this exact publication batch", confirmation_source="Synthetic owner")
        self.mapping = {saved["action_id"]: dict(object_id=3, metadata_row_id=42, element_id="heading1")}

    def ready(self, rollback=True):
        rid = p.prepare(self.store, self.sid, self.bid, self.mapping, client_factory=self.factory)
        p.authorize_from_human_ui(self.store, self.sid, rid, human_clicked=True, statement=p.STATEMENT,
                                 confirmation_source="Synthetic owner", rollback=rollback)
        return rid

    def apply(self, rid, **kwargs):
        return p.execute(self.store, self.sid, rid, human_clicked=True, client_factory=self.factory, **kwargs)

    def test_candidate_apply_duplicate_and_byte_exact_inverse(self):
        rid = self.ready()
        review = p.record(self.store, self.sid, "cms_reviews", rid)["payload"]
        self.assertEqual(review["actions"][0]["candidate_data"], RAW.replace('"Our service"', '"Our service in City"'))
        first = self.apply(rid)[0]
        self.assertEqual(p.latest_event(self.store, self.sid, first["id"])["verification"], "passed")
        self.apply(rid)
        self.assertEqual(len(self.client.writes), 1)
        self.apply(rid, direction="rollback")
        self.assertEqual(self.client.raw, RAW)
        self.assertEqual(self.client.content, '<h1>Our service</h1>\n<h2>Adjacent</h2>')
        self.apply(rid)
        self.assertEqual(len(self.client.writes), 2)

    def test_timeout_after_commit_reconcile_and_lost_journal(self):
        rid = self.ready()
        self.client.timeout = True
        attempt = self.apply(rid)[0]
        self.assertEqual(p.latest_event(self.store, self.sid, attempt["id"])["write"], "uncertain")
        self.assertEqual(p.reconcile(self.store, self.sid, attempt["id"], client_factory=self.factory), "passed")
        self.client.operations.clear()
        self.client.raw, self.client.content = RAW, '<h1>Our service</h1>\n<h2>Adjacent</h2>'
        self.assertEqual(p.reconcile(self.store, self.sid, attempt["id"], client_factory=self.factory), "failed")
        with self.assertRaisesRegex(ValueError, "already succeeded"):
            p.resume(self.store, self.sid, attempt["id"], human_clicked=True, client_factory=self.factory)
        self.assertEqual(len(self.client.writes), 1)

    def test_unknown_request_resume_reuses_body_and_identity(self):
        rid = self.ready()
        self.client.reject = True
        attempt = self.apply(rid)[0]
        self.assertEqual(p.reconcile(self.store, self.sid, attempt["id"], client_factory=self.factory), "uncertain")
        self.client.reject = False
        self.assertEqual(p.resume(self.store, self.sid, attempt["id"], human_clicked=True, client_factory=self.factory), "passed")
        self.assertEqual(self.client.writes[0], self.client.writes[1])

    def test_wrong_metadata_identity_and_moved_public_target_rejected(self):
        self.mapping[self.record["action_id"]]["metadata_row_id"] = 43
        with self.assertRaisesRegex(ValueError, "Metadata row"):
            self.ready()
        self.mapping[self.record["action_id"]]["metadata_row_id"] = 42
        public = self.client.public(self.value["url"])
        public["html"] = public["html"].replace('<div data-id="heading1"', '<div data-elementor-id="99"><div data-id="heading1"').replace('</h1></div>', '</h1></div></div>')
        with patch.object(self.client, "public", return_value=public), self.assertRaises(ValueError):
            self.ready()
        self.assertFalse(self.client.writes)

    def test_revision_and_configuration_conflicts_block_writes(self):
        rid = self.ready()
        self.client.token_extra = "concurrent configuration"
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.apply(rid)
        self.client.token_extra = ""
        t.save_action(self.store, self.sid, self.aid, {**self.record["payload"], "proposed": "Different wording"}, revision=3)
        with self.assertRaises(ValueError):
            self.apply(rid)
        self.assertFalse(self.client.writes)
        self.assertFalse(setup.readiness(self.store, self.sid)["locally_validated"])

    def test_partial_staging_batch_cannot_certify_another_action(self):
        frozen = {"action_id": self.record["action_id"], "revision": 2, "action": self.record["payload"]}
        action = dict(action_id=frozen["action_id"], revision=2, adapter=ep.ADAPTER,
            current=frozen["action"]["current"], proposed=frozen["action"]["proposed"], before=self.client.state(3))
        attempt = dict(id="a" * 32, review_id="b" * 32, action_id="c" * 32, revision=2, direction="apply", payload={})
        review = dict(payload=dict(destination={**self.client.destination, "environment": "staging"}, actions=[action]))
        with patch.object(p, "rows", return_value=[attempt]), patch.object(p, "record", return_value=review), \
                patch.object(p, "latest_event", return_value=dict(write="succeeded", verification="passed")), \
                self.assertRaisesRegex(ValueError, "successful verified staging"):
            setup.staging_proof(self.store, self.sid, {"environment": "production"}, frozen, self.client.state(3))

    def test_two_page_batch_is_rejected_before_review_or_attempt(self):
        self.value["url"] = "https://example.com/second/"
        self.aid = self.store.create_audit(self.sid)
        original_actions = t.actions
        def scoped_actions(store, sid, **kwargs):
            return [r for r in original_actions(store, sid, **kwargs) if r["audit_id"] == self.aid]
        def second_fixture(sid, aid, url):
            bundle = fixture(sid, aid, url)
            bundle["appearance"]["url"] = self.store.site(sid).url
            return bundle
        with patch("tests.test_review_previews.fixture", side_effect=second_fixture), patch.object(t, "actions", side_effect=scoped_actions):
            second, _ = test_tracking.TrackingTests.preview_target(self)
        bid = t.freeze_batch(self.store, self.sid, [(self.record["action_id"],2), (second["action_id"],2)])
        t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=True,
            statement="I approve this exact publication batch", confirmation_source="Synthetic owner")
        mapping = {**self.mapping, second["action_id"]:dict(object_id=4, metadata_row_id=43, element_id="heading1")}
        with patch.object(self.client, "state", wraps=self.client.state) as state, self.assertRaisesRegex(ValueError, "exactly one action"):
            p.prepare(self.store, self.sid, bid, mapping, client_factory=self.factory)
        state.assert_not_called()
        self.assertFalse(p.rows(self.store, self.sid, "cms_reviews"))
        self.assertFalse(p.rows(self.store, self.sid, "cms_attempts"))
        app = AppTest.from_function(publication_app, args=(str(self.store.root), self.sid, bid), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("exactly one action" in item.value for item in app.warning))
        self.assertFalse(app.number_input)

    def test_verification_failure_is_separate_from_write_success(self):
        rid = self.ready()
        original = self.client.write
        def changed(page, body):
            result = original(page, body)
            self.client.bad_render = True
            return result
        with patch.object(self.client, "write", side_effect=changed):
            attempt = self.apply(rid)[0]
        event = p.latest_event(self.store, self.sid, attempt["id"])
        self.assertEqual((event["write"], event["verification"]), ("succeeded", "failed"))
        with self.assertRaises(ValueError):
            self.apply(rid)

    def test_rotation_keeps_read_only_recovery_on_frozen_adapter(self):
        rid = self.ready()
        self.client.timeout = True
        attempt = self.apply(rid)[0]
        p.configure_from_human_ui(self.store, self.sid, url=self.client.destination["url"], instance=self.client.destination["instance"],
            environment="local", username="test", password="rotated", isolation="Synthetic separate local database/files with no live services",
            isolation_verified=True, human_clicked=True, vault=Vault(), adapter="core-heading/1")
        used = []
        def factory(destination):
            used.append(destination["adapter"])
            return self.client
        self.assertEqual(p.reconcile(self.store, self.sid, attempt["id"], client_factory=factory), "passed")
        self.assertEqual(used, [ep.ADAPTER])
        with self.assertRaises(ValueError):
            self.apply(rid)

    def test_backup_remains_inert_and_site_switch_cannot_use_review(self):
        rid = self.ready()
        self.apply(rid)
        with self.assertRaises(ValueError):
            p.execute(self.store, self.other, rid, human_clicked=True, client_factory=self.factory)
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "restored")
        self.assertFalse(p.destination(restored, self.sid)["enabled"])
        self.assertTrue(p.record(restored, self.sid, "cms_reviews", rid)["payload"]["history_only"])
        with self.assertRaises(ValueError):
            p.execute(restored, self.sid, rid, human_clicked=True, client_factory=self.factory)

    def test_ui_mapping_candidate_authorization_apply_receipt(self):
        app = AppTest.from_function(publication_app, args=(str(self.store.root), self.sid, self.bid), default_timeout=30).run()
        self.assertFalse(app.exception)
        next(n for n in app.number_input if n.label == "WordPress page ID").set_value(3)
        next(n for n in app.number_input if n.label.startswith("Exact _elementor_data")).set_value(42)
        next(i for i in app.text_input if i.label.startswith("Elementor heading widget")).set_value("heading1")
        original = p.prepare
        with patch.object(p, "prepare", side_effect=lambda *a, **kw: original(*a, **kw, client_factory=self.factory)):
            next(b for b in app.button if b.label == "Read CMS and prepare exact publication review").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("in City" in c.value for c in app.code))
        self.assertFalse(p.rows(self.store, self.sid, "cms_authorizations"))
        next(c for c in app.checkbox if c.label.startswith("I reviewed these exact CMS fields")).check()
        next(i for i in app.text_input if i.label.startswith("Responsible human")).set_value("Synthetic owner")
        next(i for i in app.text_input if i.label.startswith('Type "I approve these')).set_value(p.STATEMENT)
        next(b for b in app.button if b.label == "Approve exact CMS publication review").click().run()
        self.assertFalse(self.client.writes)
        execute = p.execute
        with patch.object(p, "execute", side_effect=lambda *a, **kw: execute(*a, **kw, client_factory=self.factory)):
            next(b for b in app.button if b.label == "Apply these approved CMS actions").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Verification: passed" in text.value for text in app.text))


class HostingBindingTests(TrackingFixture, unittest.TestCase):
    def stage(self):
        self.cid = staging_connection(self.store, self.sid, "https://stage.example.com/", "stage-install")
        p.configure_from_human_ui(self.store, self.sid, url="https://stage.example.com/", instance="stage-install", environment="staging",
            username="synthetic", password="synthetic-only", isolation="Synthetic independently verified isolated staging", human_clicked=True,
            isolation_verified=True, vault=Vault(), discovery_id=self.cid)

    def test_checkbox_or_label_cannot_enable_staging(self):
        with self.assertRaisesRegex(ValueError, "Hosting & CMS"):
            p.configure_from_human_ui(self.store, self.sid, url="https://stage.example.com/", instance="stage-install", environment="staging",
                username="synthetic", password="synthetic-only", isolation="A sufficiently long but unverified description", human_clicked=True,
                isolation_verified=True, vault=Vault())
        with self.assertRaisesRegex(ValueError, "Hosting & CMS"):
            p.configure_from_human_ui(self.store, self.sid, url="http://127.0.0.1:8879/", instance="tunnel", environment="local",
                username="synthetic", password="synthetic-only", isolation="Loopback might be forwarding to production", human_clicked=True,
                isolation_verified=True, vault=Vault(), adapter=ep.ADAPTER)

    def test_disconnect_replacement_expiry_and_profile_revoke_binding(self):
        for change in ("disconnect", "replace", "expire", "profile"):
            with self.subTest(change=change):
                self.stage()
                p.active_destination(self.store, self.sid)
                if change == "disconnect":
                    prod = next(c for c in d.connections(self.store, self.sid) if c["environment"] == "production" and c["enabled"])
                    d.disconnect(self.store, self.sid, prod["id"])
                elif change == "replace":
                    row = d.latest(self.store, self.sid, self.cid, "administrator_export")
                    d._save(self.store, self.sid, d.connection(self.store, self.sid, self.cid), "administrator_export", row["payload"]["body"]["data"])
                elif change == "expire":
                    with self.store.db() as db:
                        row = d.latest(self.store, self.sid, self.cid, "isolation_review")
                        body = row["payload"]["body"]
                        body["observed_utc"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
                        db.execute("UPDATE discovery_evidence SET payload=? WHERE id=?", (d.canonical(dict(body=body, sha256=d.digest(body))), row["id"]))
                else:
                    config = self.store.site(self.sid)
                    config.name = "Changed profile"
                    self.store.save_site(config, self.sid)
                with self.assertRaises(ValueError):
                    p.active_destination(self.store, self.sid)
                self.assertTrue(p.active_destination(self.store, self.sid, recovery=True))
                d.disconnect(self.store, self.sid, self.cid)

    def test_real_elementor_cannot_use_unbound_or_unknown_host(self):
        with self.assertRaises(ValueError):
            p.configure_from_human_ui(self.store, self.sid, url=self.store.site(self.sid).url, instance="prod", environment="production",
                username="synthetic", password="synthetic-only", isolation="", human_clicked=True, vault=Vault(), adapter=ep.ADAPTER)
        self.assertFalse(setup.readiness(self.store, self.sid)["production_ready"])

    def test_setup_packet_has_exact_hashes_and_grants_no_authority(self):
        packet = setup.setup_packet(self.store, self.sid)
        self.assertTrue(packet["history_only"])
        self.assertEqual(packet["provider"], "Unknown")
        self.assertEqual(len(packet["files"]["elementor-publisher.php"]), 64)
        self.assertFalse(p.rows(self.store, self.sid, "cms_authorizations"))

    def test_elementor_host_binding_crosschecks_live_inventory_and_replacement_invalidates(self):
        self.stage()
        c = d.connection(self.store, self.sid, self.cid)
        data = copy.deepcopy(d.latest(self.store, self.sid, self.cid, "administrator_export")["payload"]["body"]["data"])
        data["host"].extend(dict(area=area, result="observed", observation="Synthetic independently observed supported host behavior",
            source_reference="Synthetic provider record", production_resource="production", environment_resource="staging") for area in d.HOST_EFFECTS)
        manifest = ep.contract_manifest()
        inv = dict(wordpress=manifest["wordpress"], php=manifest["php_runtime"], database=manifest["database_runtime"],
            theme=manifest["theme"], elementor=manifest["elementor"], adapter_hash=ep.adapter_hash(),
            plugins=["elementor/elementor.php", "local-seo-publisher/local-seo-publisher.php"],
            core_includes_php=manifest["core_includes_php"], theme_files=manifest["theme_files"], elementor_files=manifest["elementor_files"])
        state = FakeElementor(p.destination(self.store, self.sid)).state(3)
        state["inventory"] = inv
        data["pages"] = [dict(id=3, url=state["url"], template=state["template"], raw_content=state["content"],
            raw_excerpt=state["excerpt"], shared_ids=[], metadata=[dict(row_id=42, key="_elementor_data", value=state["elementor_data"])])]
        data["complete_inventory"] = ["core", "php", "database", "table_engine", "theme", "plugin", "mu_plugin", "dropin"]
        data["software"] = [dict(kind=k, name=n, version=v, sha256=h, active=True) for k,n,v,h in (
            ("core","WordPress",inv["wordpress"],inv["core_includes_php"]),
            ("theme",inv["theme"],manifest["theme_version"],inv["theme_files"]),
            ("plugin","elementor/elementor.php",inv["elementor"],inv["elementor_files"]),
            ("plugin","local-seo-publisher/local-seo-publisher.php","0.2.0",inv["adapter_hash"]),
            ("php","PHP",inv["php"],None), ("database","MariaDB",inv["database"],None))]
        d._save(self.store, self.sid, c, "administrator_export", data)
        d._save(self.store, self.sid, c, "public", {"pages":[dict(id=3,url=state["url"],template=state["template"])], "clues":[]})
        d.review_isolation(self.store, self.sid, self.cid, human_clicked=True, source="Synthetic independent review")
        with self.assertRaisesRegex(ValueError, "host effect"):
            setup.evidence_binding(self.store, self.sid, url=c["url"], instance=c["installation_id"],
                environment="staging", adapter=ep.ADAPTER, discovery_id=self.cid)
        setup.review_host(self.store, self.sid, self.cid, human_clicked=True, source="Synthetic independent review",
                          conditions=list(setup.HOST_CONDITIONS))
        binding = setup.evidence_binding(self.store, self.sid, url=c["url"], instance=c["installation_id"],
                environment="staging", adapter=ep.ADAPTER, discovery_id=self.cid)
        destination = {**p.destination(self.store, self.sid), "adapter":ep.ADAPTER, "discovery_binding":binding}
        setup.validate_binding(self.store, self.sid, destination)
        setup.validate_installation(self.store, self.sid, destination, state)
        for bad in ({"metadata_row_id":43}, {"template":"elementor_header_footer"},
                    {"inventory":{**inv, "elementor":"4.3.4"}}):
            with self.subTest(bad=list(bad)), self.assertRaises(ValueError):
                setup.validate_installation(self.store, self.sid, destination, {**state, **bad})
        row = d.latest(self.store, self.sid, self.cid, "public")
        d._save(self.store, self.sid, c, "public", row["payload"]["body"]["data"])
        with self.assertRaises(ValueError): setup.validate_binding(self.store, self.sid, destination)


class ProtocolTests(unittest.TestCase):
    def test_distinct_client_route_and_no_ambient_auth(self):
        class ReadVault:
            def read(self, _): return "synthetic", "synthetic-only"
        destination = dict(url="http://127.0.0.1:8879/", instance="local", environment="local", credential_id="a" * 32, adapter=ep.ADAPTER)
        client = WordPress(destination, ReadVault())
        with patch.object(client, "request", return_value={}) as request:
            client.state(3)
            self.assertIn("/local-seo-elementor/v1/", request.call_args.args[1])
        self.assertFalse(client.session.trust_env)
        client.close()

    def test_entity_text_and_mirror_drift_rejected(self):
        for value in ("A &amp; B", "Literal &#65;", "<b>text</b>", "Synthetic &copy heading", "A &notable word"):
            with self.assertRaises(ValueError): ep.plain(value)
        ep.plain("Meadow & Mind")
        with self.assertRaises(ValueError): ep.mirror_candidate('<h1>Changed</h1>', [dict(element_id="a", tag="h1", text="Before")], "a", "After")
