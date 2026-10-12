import copy
import unittest
from unittest.mock import patch

from seo_agent import publishing as p, tracking as t
from seo_agent.backup import _backup, _restore
from seo_agent.wordpress import CMSFailure, PROTOCOL, bind_public_target, rendered
from tests.test_tracking import TrackingFixture
from tests import test_tracking


class Vault:
    def write(self, key, username, password):
        self.key = key


class FakeWordPress:
    def __init__(self, destination):
        self.destination = destination
        self.states, self.operations, self.writes = {}, {}, []
        self.timeout = False
        self.reject = False
        self.bad_render = False

    def seed(self, page, url, text="Our service"):
        self.states[page] = dict(protocol=PROTOCOL, instance=self.destination["instance"], home=self.destination["url"],
            environment=self.destination["environment"], id=page, url=url, type="page", status="publish", supported=True,
            token=t.digest([page, text]), preserved="unchanged", content='<h1 id="service">' + text + '</h1><p>Unrelated</p>',
            headings=[dict(anchor="service", block_index=0, text=text)])

    def state(self, page):
        return copy.deepcopy(self.states[page])

    def public(self, url):
        state = next(s for s in self.states.values() if s["url"] == url)
        text = state["headings"][0]["text"]
        return {"html": '<html><head><title>Service</title></head><body><main><h1 id="service">' + text + '</h1><p>' +
                ('Unexpected edit' if self.bad_render else 'Context') + '</p></main><footer>Footer</footer></body></html>', "robots": ""}

    def write(self, page, body):
        self.writes.append(copy.deepcopy(body))
        if self.reject:
            raise CMSFailure("Unavailable")
        if body["request_id"] in self.operations:
            return self.operations[body["request_id"]]
        if body["token"] != self.states[page]["token"]:
            raise CMSFailure("Conflict")
        self.states[page]["headings"][0]["text"] = body["proposed"]
        self.states[page]["content"] = '<h1 id="service">' + body["proposed"] + '</h1><p>Unrelated</p>'
        self.states[page]["token"] = t.digest(body)
        result = dict(request_id=body["request_id"], request=body, status="applied", after_token=self.states[page]["token"])
        self.operations[body["request_id"]] = result
        if self.timeout:
            raise CMSFailure("Timeout after commit")
        return result

    def operation(self, page, request_id):
        return self.operations.get(request_id, {"status": "unknown"})

    def close(self):
        pass


class PublishingTests(TrackingFixture, unittest.TestCase):
    preview_target = test_tracking.TrackingTests.preview_target
    html_snapshot = test_tracking.TrackingTests.html_snapshot

    def setUp(self):
        super().setUp()
        self.record, _ = self.preview_target()
        p.configure_from_human_ui(self.store, self.sid, url="https://example.com/", instance="synthetic",
            environment="production", username="test", password="synthetic-test-only", isolation="", human_clicked=True, vault=Vault())
        self.client = FakeWordPress(p.destination(self.store, self.sid))
        self.client.seed(3, self.record["payload"]["url"])
        self.factory = lambda _: self.client
        self.bid = t.freeze_batch(self.store, self.sid, [(self.record["action_id"], 2)])
        t.approve_from_human_ui(self.store, self.sid, self.bid, human_clicked=True,
            statement="I approve this exact publication batch", confirmation_source="Synthetic owner")
        self.mapping = {self.record["action_id"]: {"object_id": 3, "anchor": "service"}}

    def ready(self, rollback=False):
        rid = p.prepare(self.store, self.sid, self.bid, self.mapping, client_factory=self.factory)
        p.authorize_from_human_ui(self.store, self.sid, rid, human_clicked=True, statement=p.STATEMENT,
                                  confirmation_source="Synthetic owner confirmed", rollback=rollback)
        return rid

    def apply(self, rid, **kwargs):
        return p.execute(self.store, self.sid, rid, human_clicked=True, client_factory=self.factory, **kwargs)

    def test_success_duplicate_click_and_receipt(self):
        rid = self.ready()
        attempts = self.apply(rid)
        self.apply(rid)
        self.assertEqual(len(self.client.writes), 1)
        result = p.latest_event(self.store, self.sid, attempts[0]["id"])
        self.assertEqual((result["write"], result["verification"]), ("succeeded", "passed"))
        self.assertEqual([r["payload"]["outcome"] for r in t.rows(self.store, "implementation_receipts", self.sid)], ["attempted", "reported_applied"])

    def configure_fixture(self, environment, url, instance):
        p.configure_from_human_ui(self.store, self.sid, url=url, instance=instance,
            environment=environment, username="test", password="synthetic-test-only",
            isolation="Synthetic independent database and deployment with no production synchronization",
            isolation_verified=True, human_clicked=True, vault=Vault())
        self.client = FakeWordPress(p.destination(self.store, self.sid))
        self.client.seed(3, p.mapped_url(self.client.destination, self.store.site(self.sid).url, self.record["payload"]["url"]))

    def test_staging_then_production_requires_separate_review_and_can_apply(self):
        self.configure_fixture("staging", "https://staging.example.com/", "separate-staging")
        staging = self.ready()
        first = self.apply(staging)[0]
        self.configure_fixture("production", "https://example.com/", "synthetic")
        with self.assertRaisesRegex(ValueError, "Destination changed"):
            self.apply(staging)
        production = self.ready()
        second = self.apply(production)[0]
        self.assertNotEqual(first["destination_key"], second["destination_key"])
        self.assertEqual(p.latest_event(self.store, self.sid, second["id"])["verification"], "passed")
        self.apply(production)
        self.assertEqual(len(self.client.writes), 1)

    def test_credential_rotation_cannot_reset_consumed_revision(self):
        self.apply(self.ready())
        self.configure_fixture("production", "https://example.com/", "synthetic")
        with self.assertRaisesRegex(ValueError, "already been attempted"):
            self.ready()
        self.assertEqual(self.client.writes, [])

    def test_uncertain_page_in_another_installation_does_not_block(self):
        self.configure_fixture("staging", "https://staging.example.com/", "separate-staging")
        self.client.reject = True
        self.apply(self.ready())
        self.configure_fixture("production", "https://example.com/", "synthetic")
        attempt = self.apply(self.ready())[0]
        self.assertEqual(p.latest_event(self.store, self.sid, attempt["id"])["verification"], "passed")

    def test_uncertain_staging_receipt_does_not_block_another_staging_installation(self):
        self.configure_fixture("staging", "https://staging-a.example.com/", "staging-a")
        self.client.reject = True
        first = self.apply(self.ready())[0]
        self.assertEqual(p.latest_event(self.store, self.sid, first["id"])["write"], "uncertain")
        self.configure_fixture("staging", "https://staging-b.example.com/", "staging-b")
        second = self.apply(self.ready())[0]
        self.assertEqual(p.latest_event(self.store, self.sid, second["id"])["verification"], "passed")
        self.assertEqual(len(self.client.writes), 1)
        self.assertEqual(p.latest_event(self.store, self.sid, first["id"])["write"], "uncertain")

    def test_credential_rotation_allows_read_only_recovery_but_revokes_writes(self):
        rid = self.ready()
        self.client.timeout = True
        attempt = self.apply(rid)[0]
        old_client = self.client
        self.configure_fixture("production", "https://example.com/", "synthetic")
        active = p.active_destination(self.store, self.sid)
        used = []
        def factory(destination):
            used.append(destination)
            return old_client
        self.assertEqual(p.reconcile(self.store, self.sid, attempt["id"], client_factory=factory), "passed")
        self.assertEqual(used, [active])
        self.assertEqual(len(old_client.writes), 1)
        with self.assertRaisesRegex(ValueError, "Destination changed"):
            p.resume(self.store, self.sid, attempt["id"], human_clicked=True, client_factory=factory)
        self.configure_fixture("staging", "https://staging.example.com/", "separate-staging")
        with self.assertRaisesRegex(ValueError, "Destination changed"):
            p.reconcile(self.store, self.sid, attempt["id"], client_factory=factory)

    def test_v5_attempt_migration_preserves_receipts_and_replay_protection(self):
        from seo_agent.storage import Store, PUBLISHING_SCHEMA_V5
        attempt = self.apply(self.ready())[0]
        before_events = p.rows(self.store, self.sid, "cms_events")
        with self.store.db() as db:
            db.execute("PRAGMA foreign_keys=OFF")
            create = next(q for q in PUBLISHING_SCHEMA_V5.split(";") if "CREATE TABLE IF NOT EXISTS cms_attempts(" in q)
            db.execute(create.replace("cms_attempts(", "cms_attempts_old("))
            db.execute("INSERT INTO cms_attempts_old SELECT id,site_id,review_id,action_id,revision,direction,created,payload FROM cms_attempts")
            db.execute("DROP TABLE cms_attempts")
            db.execute("ALTER TABLE cms_attempts_old RENAME TO cms_attempts")
            db.execute("PRAGMA user_version=5")
        self.store = Store(self.store.root)
        self.assertEqual(p.record(self.store, self.sid, "cms_attempts", attempt["id"]), attempt)
        self.assertEqual(p.rows(self.store, self.sid, "cms_events"), before_events)
        with self.store.db() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 6)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        with self.assertRaisesRegex(ValueError, "already been attempted"):
            self.ready()

    def test_wrong_site_and_destination(self):
        with self.assertRaises(ValueError):
            p.prepare(self.store, self.other, self.bid, self.mapping, client_factory=self.factory)
        self.client.states[3]["instance"] = "another-installation"
        with self.assertRaises(ValueError):
            self.ready()
        self.assertEqual(self.client.writes, [])

    def test_unsupported_title_and_block_identifier(self):
        self.mapping[self.record["action_id"]]["field"] = "seo_title"
        with self.assertRaises(ValueError):
            self.ready()
        self.mapping[self.record["action_id"]].pop("field")
        self.client.states[3]["supported"] = False
        with self.assertRaises(ValueError):
            self.ready()

    def test_frozen_target_cannot_map_to_same_text_elsewhere(self):
        with self.assertRaises(ValueError):
            bind_public_target('<html><body><main><h1>Our service</h1><p>Context</p></main><footer><h1 id="service">Our service</h1></footer></body></html>',
                               t.batch(self.store, self.sid, self.bid)["payload"]["actions"][0]["target"], "service")

    def test_stale_proposal_stops_before_write(self):
        rid = self.ready()
        t.save_action(self.store, self.sid, self.aid, {**self.record["payload"], "proposed": "Different wording"}, revision=3)
        with self.assertRaises(ValueError):
            self.apply(rid)
        self.assertEqual(self.client.writes, [])

    def test_cms_conflict_stops_before_attempt(self):
        rid = self.ready()
        self.client.states[3]["token"] = "f" * 64
        with self.assertRaises(ValueError):
            self.apply(rid)
        self.assertEqual(p.rows(self.store, self.sid, "cms_attempts"), [])

    def test_timeout_after_commit_reconciles_without_resend(self):
        rid = self.ready()
        self.client.timeout = True
        attempt = self.apply(rid)[0]
        self.assertEqual(p.latest_event(self.store, self.sid, attempt["id"])["write"], "uncertain")
        with self.assertRaises(ValueError):
            self.apply(rid)
        self.assertEqual(p.reconcile(self.store, self.sid, attempt["id"], client_factory=self.factory), "passed")
        self.apply(rid)
        self.assertEqual(len(self.client.writes), 1)

    def test_missing_server_receipt_never_means_safe_retry(self):
        rid = self.ready()
        self.client.reject = True
        attempt = self.apply(rid)[0]
        self.assertEqual(p.reconcile(self.store, self.sid, attempt["id"], client_factory=self.factory), "uncertain")
        with self.assertRaises(ValueError):
            self.apply(rid)
        self.assertEqual(len(self.client.writes), 1)

    def test_verification_failure_is_separate_from_successful_write(self):
        rid = self.ready()
        write = self.client.write
        def changed(page, body):
            result = write(page, body)
            self.client.bad_render = True
            return result
        self.client.write = changed
        attempt = self.apply(rid)[0]
        result = p.latest_event(self.store, self.sid, attempt["id"])
        self.assertEqual((result["write"], result["verification"]), ("succeeded", "failed"))

    def test_rollback_requires_exact_authorization_and_checks_conflicts(self):
        rid = self.ready()
        self.apply(rid)
        with self.assertRaises(ValueError):
            self.apply(rid, direction="rollback")

    def test_authorized_rollback_and_duplicate(self):
        rid = self.ready(rollback=True)
        self.apply(rid)
        self.apply(rid, direction="rollback")
        self.apply(rid, direction="rollback")
        self.assertEqual(len(self.client.writes), 2)
        self.assertEqual(self.client.states[3]["headings"][0]["text"], "Our service")

    def test_rollback_never_overwrites_subsequent_edit(self):
        rid = self.ready(rollback=True)
        self.apply(rid)
        self.client.states[3]["token"] = "a" * 64
        with self.assertRaises(ValueError):
            self.apply(rid, direction="rollback")
        self.assertEqual(len(self.client.writes), 1)

    def test_restored_backup_disables_destination_and_authority(self):
        rid = self.ready(rollback=True)
        self.apply(rid)
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "restored")
        self.assertFalse(p.destination(restored, self.sid)["enabled"])
        self.assertIsNone(p.destination(restored, self.sid)["credential_id"])
        self.assertTrue(p.rows(restored, self.sid, "cms_authorizations")[0]["payload"]["history_only"])
        with self.assertRaises(ValueError):
            p.execute(restored, self.sid, rid, human_clicked=True, client_factory=self.factory)

    def test_nonhuman_cannot_configure_approve_or_apply(self):
        rid = p.prepare(self.store, self.sid, self.bid, self.mapping, client_factory=self.factory)
        with self.assertRaises(ValueError):
            p.authorize_from_human_ui(self.store, self.sid, rid, human_clicked=False, statement=p.STATEMENT, confirmation_source="model", rollback=True)
        with self.assertRaises(ValueError):
            p.execute(self.store, self.sid, rid, human_clicked=False, client_factory=self.factory)

    def test_directives_and_adjacent_content_are_verified(self):
        before = self.client.public(self.record["payload"]["url"])
        after = {**before, "robots": "noindex"}
        self.assertNotEqual(rendered(before, "service", "Our service"), rendered(after, "service", "Our service"))

    def second_page(self):
        self.value["url"] = "https://example.com/second/"
        self.aid = self.store.create_audit(self.sid)
        from tests.test_review_previews import fixture
        def site_fixture(sid, aid, url):
            bundle = fixture(sid, aid, url)
            bundle["appearance"]["url"] = self.store.site(sid).url
            return bundle
        with patch("tests.test_review_previews.fixture", side_effect=site_fixture):
            # The legacy helper selects the first site action; scope its lookup to
            # this second audit while constructing the independent fixture.
            original_actions = t.actions
            def scoped_actions(store, sid, **kwargs):
                return [r for r in original_actions(store, sid, **kwargs) if r["audit_id"] == self.aid]
            with patch.object(t, "actions", side_effect=scoped_actions):
                second, _ = self.preview_target()
        self.client.seed(4, self.value["url"])
        self.mapping[second["action_id"]] = {"object_id": 4, "anchor": "service"}
        self.bid = t.freeze_batch(self.store, self.sid, [(self.record["action_id"], 2), (second["action_id"], 2)])
        t.approve_from_human_ui(self.store, self.sid, self.bid, human_clicked=True,
            statement="I approve this exact publication batch", confirmation_source="Synthetic owner")

    def test_partial_batch_retains_first_success_and_stops(self):
        self.second_page()
        rid = self.ready()
        write = self.client.write
        def fail_second(page, body):
            self.client.reject = page == 4
            return write(page, body)
        self.client.write = fail_second
        attempts = self.apply(rid)
        results = [p.latest_event(self.store, self.sid, a["id"])["write"] for a in attempts]
        self.assertEqual(results, ["succeeded", "uncertain"])
        self.assertEqual(self.client.states[3]["headings"][0]["text"], self.record["payload"]["proposed"])
        self.assertEqual(self.client.states[4]["headings"][0]["text"], "Our service")

    def test_full_batch_preflight_prevents_first_write_when_second_conflicts(self):
        self.second_page()
        rid = self.ready()
        self.client.states[4]["token"] = "b" * 64
        with self.assertRaises(ValueError):
            self.apply(rid)
        self.assertEqual(self.client.writes, [])

    def test_destination_reconfiguration_revokes_cms_authority(self):
        rid = self.ready()
        p.configure_from_human_ui(self.store, self.sid, url="https://example.com/", instance="synthetic",
            environment="production", username="test", password="synthetic-test-only", isolation="", human_clicked=True, vault=Vault())
        with self.assertRaises(ValueError):
            self.apply(rid)

    def test_workspace_lock_blocks_competing_execution(self):
        from seo_agent.coordination import run_lock, workspace_lock, BusyError
        rid = self.ready()
        with run_lock(workspace_lock(self.store.root)), self.assertRaises(BusyError):
            self.apply(rid)
        self.assertEqual(self.client.writes, [])

    def test_explicit_resume_reads_first_and_reuses_request_identity(self):
        rid = self.ready()
        self.client.reject = True
        attempt = self.apply(rid)[0]
        self.client.reject = False
        with patch.object(self.client, "operation", wraps=self.client.operation) as read:
            self.assertEqual(p.resume(self.store, self.sid, attempt["id"], human_clicked=True, client_factory=self.factory), "passed")
            read.assert_called_once()
        self.assertEqual(self.client.writes[0], self.client.writes[1])
        self.assertEqual(len(self.client.operations), 1)

    def test_resume_cannot_bypass_revised_wording(self):
        rid = self.ready()
        self.client.reject = True
        attempt = self.apply(rid)[0]
        t.save_action(self.store, self.sid, self.aid, {**self.record["payload"], "proposed": "Changed"}, revision=3)
        with self.assertRaises(ValueError):
            p.resume(self.store, self.sid, attempt["id"], human_clicked=True, client_factory=self.factory)
        self.assertEqual(len(self.client.writes), 1)

    def test_preparation_and_approval_never_write(self):
        self.ready()
        self.assertEqual(self.client.writes, [])
        self.assertEqual(p.rows(self.store, self.sid, "cms_attempts"), [])

    def test_stale_public_validation_blocks_then_unchanged_refresh_preserves_permission(self):
        from datetime import datetime, timedelta, timezone
        from seo_agent import page_tracking
        rid = self.ready()
        snapshots = t.rows(self.store, "public_snapshots", self.sid)
        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with self.store.db() as db:
            db.execute("UPDATE public_snapshots SET checked=? WHERE site_id=?", (old, self.sid))
        with self.assertRaises(ValueError):
            self.apply(rid)
        s = snapshots[-1]
        page_tracking.save_snapshot(self.store, self.sid, s["url"], status="complete", payload=s["payload"])
        self.apply(rid)
        self.assertEqual(len(self.client.writes), 1)

    def test_export_has_no_credential_reference_or_executable_authority(self):
        rid = self.ready()
        exported = p.export_review(self.store, self.sid, rid)
        self.assertTrue(exported["history_only"])
        self.assertNotIn("credential_id", t.canonical(exported))
        self.assertTrue(p.destination(self.store, self.sid)["credential_id"])

    def test_server_restore_cannot_reauthorize_a_known_success(self):
        rid = self.ready()
        before = copy.deepcopy(self.client.states)
        attempt = self.apply(rid)[0]
        # A WordPress-only restore can remove the operation journal and restore
        # the exact original page token. Local proof of success must survive it.
        self.client.states = before
        self.client.operations.clear()
        p.reconcile(self.store, self.sid, attempt["id"], client_factory=self.factory)
        self.assertEqual(p.latest_event(self.store, self.sid, attempt["id"])["write"], "succeeded")
        with self.assertRaises(ValueError):
            p.resume(self.store, self.sid, attempt["id"], human_clicked=True, client_factory=self.factory)
        self.assertEqual(len(self.client.writes), 1)

    def test_shortcode_brackets_are_rejected_before_cms_authorization(self):
        value = {**self.record["payload"], "proposed": "Our service [updated]"}
        t.save_action(self.store, self.sid, self.aid, value, revision=3)
        self.bid = t.freeze_batch(self.store, self.sid, [(value["action_id"], 3)])
        t.approve_from_human_ui(self.store, self.sid, self.bid, human_clicked=True,
            statement="I approve this exact publication batch", confirmation_source="Synthetic owner")
        with self.assertRaises(ValueError):
            self.ready(rollback=True)
        self.assertFalse(p.rows(self.store, self.sid, "cms_reviews"))
        self.assertFalse(self.client.writes)


if __name__ == "__main__":
    unittest.main()
