import copy
import json
import unittest
from unittest.mock import patch

from seo_agent import proposal_review as r, tracking as t, page_tracking as p
from seo_agent.backup import _backup, _restore
from seo_agent.config import SiteConfig, Phrase
from seo_agent.storage import new_id
from tests.test_tracking import TrackingFixture


def model_output(request, *, questions=None):
    judgment = {"assessment": "Synthetic judgment: clearer phrasing may help users; effectiveness remains uncertain", "evidence_ids": ["profile", "proposal", "crawl.csv:2"]}
    return {"schema": "seo-proposal-model-review/1", "request_id": request["id"], "binding_hash": t.digest(request["payload"]["binding"]),
            "input_hash": request["payload"]["input_hash"], "reviewer": "Synthetic local reviewer", "model": "fixture-only",
            "axes": {axis: copy.deepcopy(judgment) for axis in r.AXES}, "improves": [judgment], "weakens": [],
            "advisory": [{"assessment": "Prefer a shorter title; the user can keep this style", "evidence_ids": ["original", "proposal"]}],
            "uncertainty": ["Competition and demand remain unknown"], "missing_confirmations": questions or [],
            "measurement": "Inspect the published title and compare complete finalized affected-query/page windows; do not infer causality"}


class ProposalReviewTests(TrackingFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.import_action()
        self.snapshot()

    def record(self):
        return t.actions(self.store, self.sid)[0]

    def evaluate(self):
        a = self.record()
        r.assess(self.store, self.sid, a["action_id"], a["revision"])
        return r.evaluations(self.store, self.sid, a["action_id"])[-1]

    def test_revision_restore_history_observations_and_state_are_independent(self):
        original = copy.deepcopy(self.record())
        before = p.latest_snapshot(self.store, self.sid, self.value["url"])
        r.revise(self.store, self.sid, original, {"proposed": "My alternative", "expected_effect": "Clarity hypothesis"}, note="I prefer less promotional wording")
        changed = self.record()
        self.assertEqual(changed["revision"], 2)
        self.assertEqual(changed["payload"]["revision_note"], "I prefer less promotional wording")
        self.assertEqual(changed["payload"]["current"], original["payload"]["current"])
        self.assertEqual(changed["payload"]["evidence"], original["payload"]["evidence"])
        self.assertEqual(changed["payload"]["confirmations"][0]["status"], "pending")
        r.restore(self.store, self.sid, changed, 1)
        restored = self.record()
        self.assertEqual(restored["revision"], 3)
        self.assertEqual(restored["payload"]["proposed"], "After")
        self.assertEqual(restored["payload"]["restored_from"], 1)
        self.assertEqual(t.action(self.store, self.sid, self.value["action_id"], 1), original)
        self.assertEqual(p.latest_snapshot(self.store, self.sid, self.value["url"]), before)
        self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
        self.assertEqual(t.rows(self.store, "implementation_receipts", self.sid), [])
        for changes in ({"current": "Forged"}, {"evidence": []}, {"url": "https://other.example/"}):
            with self.assertRaises(ValueError):
                r.revise(self.store, self.sid, restored, changes)

    def test_revision_and_config_evidence_changes_stale_assessments_and_approval(self):
        evaluation = self.evaluate()
        bid = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=True, statement="I approve this exact publication batch", confirmation_source="Synthetic owner")
        frozen = copy.deepcopy(t.batch(self.store, self.sid, bid))
        r.revise(self.store, self.sid, self.record(), {"proposed": "Alternative"}, owner_confirmed=True, confirmation_source="Synthetic exact revised wording confirmed")
        self.assertTrue(r.is_stale(self.store, self.sid, evaluation))
        self.assertIn(self.value["action_id"], t.batch_validity(self.store, self.sid, bid))
        self.assertEqual(t.batch(self.store, self.sid, bid), frozen)
        with self.assertRaises(ValueError):
            t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 2)])
        current = self.evaluate()
        self.assertFalse(r.is_stale(self.store, self.sid, current))
        newer_batch = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 2)])
        config = self.store.site(self.sid)
        self.store.save_site(SiteConfig.model_validate({**config.model_dump(), "confirmed_facts": {"service": "Changed owner fact"}}), self.sid)
        self.assertTrue(r.is_stale(self.store, self.sid, current))
        self.assertTrue(t.batch_validity(self.store, self.sid, newer_batch))
        latest = self.evaluate()
        self.store.audit_file(self.sid, self.aid, "data", "crawl.csv").write_text("url,title\nhttps://example.com/,Different source\n", encoding="utf-8")
        self.assertTrue(r.is_stale(self.store, self.sid, latest))

    def test_refreshed_capture_preserves_approved_exact_action_but_requires_fresh_pending_review(self):
        evaluation = self.evaluate()
        bid = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        pending = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=True, statement="I approve this exact publication batch", confirmation_source="Synthetic owner")
        frozen = copy.deepcopy(t.batch(self.store, self.sid, bid))
        self.snapshot()
        self.assertTrue(r.is_stale(self.store, self.sid, evaluation))
        self.assertFalse(t.batch_validity(self.store, self.sid, bid))
        self.assertTrue(t.batch_validity(self.store, self.sid, pending))
        with self.assertRaises(ValueError):
            t.approve_from_human_ui(self.store, self.sid, pending, human_clicked=True, statement="I approve this exact publication batch", confirmation_source="Synthetic owner")
        request = self.evaluate()
        r.import_model(self.store, self.sid, request["id"], t.canonical(model_output(request, questions=["Owner confirms availability"])).encode())
        self.assertTrue(t.batch_validity(self.store, self.sid, bid), "New mandatory owner questions still block approved actions")
        self.assertEqual(t.batch(self.store, self.sid, bid), frozen)

    def test_unavailable_infrastructure_is_explicit_no_outbound_call(self):
        with patch("requests.Session.request") as network:
            evaluation = self.evaluate()
            handoff = json.loads(r.handoff(self.store, self.sid, evaluation))
        network.assert_not_called()
        self.assertIsNone(evaluation["payload"]["model"])
        self.assertTrue(any("not a complete" in s for s in evaluation["payload"]["mechanical"]["uncertainty"]))
        self.assertEqual(handoff["request_id"], evaluation["id"])
        self.assertNotIn("connection_id", handoff["input"]["profile"])

    def test_delayed_model_import_rechecks_revision_before_commit(self):
        request = self.evaluate()
        original_validator = r.validate_model
        def edit_during_validation(raw, pinned):
            value = original_validator(raw, pinned)
            r.revise(self.store, self.sid, self.record(), {"proposed": "Changed during review"})
            return value
        with patch.object(r, "validate_model", side_effect=edit_during_validation), self.assertRaises(ValueError):
            r.import_model(self.store, self.sid, request["id"], t.canonical(model_output(request)).encode())
        self.assertEqual(len(r.evaluations(self.store, self.sid, self.value["action_id"])), 1)

    def test_supported_destinations_directives_exclusions_and_uplift_constraints(self):
        for kind, proposed, expected in (("href", "javascript:alert(1)", "Destination"), ("canonical", "https://other.example/", "Cross-site"), ("index_directive", "index, noindex", "Conflicting"), ("index_directive", "index, none", "Conflicting"), ("index_directive", "follow, none", "Conflicting"), ("index_directive", "madeup", "Unsupported")):
            with self.subTest(kind=kind, proposed=proposed):
                value = {**self.value, "action_id": new_id(), "action_kind": kind, "proposed": proposed}
                t.save_action(self.store, self.sid, self.aid, value)
                record = t.action(self.store, self.sid, value["action_id"], 1)
                self.assertTrue(any(expected in s for s in r.constraint_blockers(self.store, self.sid, record)))
        for directive in ("all, noindex", "all, nofollow", "none"):
            value = {**self.value, "action_id": new_id(), "action_kind": "index_directive", "proposed": directive}
            t.save_action(self.store, self.sid, self.aid, value)
            self.assertFalse(r.constraint_blockers(self.store, self.sid, t.action(self.store, self.sid, value["action_id"], 1)))
        config = self.store.site(self.sid)
        self.store.save_site(SiteConfig.model_validate({**config.model_dump(), "exclusions": [self.value["url"]]}), self.sid)
        for directive in ("index, follow", "all", "all, nofollow", "noarchive"):
            value = {**self.value, "action_id": new_id(), "action_kind": "index_directive", "proposed": directive}
            t.save_action(self.store, self.sid, self.aid, value)
            self.assertTrue(any("exclusion" in s for s in r.constraint_blockers(self.store, self.sid, t.action(self.store, self.sid, value["action_id"], 1))))
        for directive in ("none", "all, noindex"):
            value = {**self.value, "action_id": new_id(), "action_kind": "index_directive", "proposed": directive}
            t.save_action(self.store, self.sid, self.aid, value)
            self.assertFalse(r.constraint_blockers(self.store, self.sid, t.action(self.store, self.sid, value["action_id"], 1)))
        r.revise(self.store, self.sid, t.action(self.store, self.sid, self.value["action_id"], 1), {"expected_effect": "Will increase organic clicks by 30%"})
        record = t.action(self.store, self.sid, self.value["action_id"], 2)
        self.assertTrue(any("numerical uplift" in s for s in r.constraint_blockers(self.store, self.sid, record)))

    def test_advisory_disagreement_does_not_block_approval_or_change_proposal(self):
        request = self.evaluate()
        raw = model_output(request)
        r.import_model(self.store, self.sid, request["id"], t.canonical(raw).encode())
        self.assertTrue(t.readiness(self.store, self.sid, self.record())["ready"])
        self.assertEqual(self.record()["payload"]["proposed"], "After")
        self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
        self.assertIsNotNone(t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)]))
        r.revise(self.store, self.sid, self.record(), {}, note="I retain the title despite the advisory style preference")
        self.assertTrue(r.is_stale(self.store, self.sid, request))
        self.assertEqual(self.record()["payload"]["revision_note"], "I retain the title despite the advisory style preference")

    def test_model_questions_survive_removal_restore_and_second_opinion(self):
        request = self.evaluate()
        question = "Owner must confirm emergency availability"
        r.import_model(self.store, self.sid, request["id"], t.canonical(model_output(request, questions=[question])).encode())
        self.assertTrue(any(question in s for s in t.readiness(self.store, self.sid, self.record())["reasons"]))
        with self.assertRaises(ValueError):
            t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        r.import_model(self.store, self.sid, request["id"], t.canonical(model_output(request)).encode())
        self.assertIn(question, r.required_questions(self.store, self.sid, self.record()))
        r.revise(self.store, self.sid, self.record(), {"proposed": "Alternative", "confirmations": []})
        self.assertIn(question, [c["item"] for c in self.record()["payload"]["confirmations"]])
        r.restore(self.store, self.sid, self.record(), 1)
        self.assertIn(question, [c["item"] for c in self.record()["payload"]["confirmations"]])
        r.revise(self.store, self.sid, self.record(), {}, owner_confirmed=True, confirmation_source="Synthetic owner confirms all retained questions")
        self.evaluate()
        self.assertTrue(t.readiness(self.store, self.sid, self.record())["ready"])

    def test_forged_model_confirmation_approval_and_wrong_evidence_are_rejected(self):
        request = self.evaluate()
        for changes in ({"approval": "granted"}, {"confirmations": [{"status": "confirmed"}]}, {"binding_hash": "wrong"}, {"request_id": new_id()}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                r.import_model(self.store, self.sid, request["id"], t.canonical({**model_output(request), **changes}).encode())
        raw = model_output(request)
        raw["axes"]["query_intent"]["evidence_ids"] = ["other-site.csv:2"]
        with self.assertRaises(ValueError):
            r.import_model(self.store, self.sid, request["id"], t.canonical(raw).encode())
        raw = model_output(request)
        raw["measurement"] = "Guaranteed first ranking"
        with self.assertRaises(ValueError):
            r.import_model(self.store, self.sid, request["id"], t.canonical(raw).encode())
        self.assertEqual(len(r.evaluations(self.store, self.sid, self.value["action_id"])), 1)

    def test_cross_site_requests_configuration_and_target_isolation(self):
        config = self.store.site(self.sid)
        self.store.save_site(SiteConfig.model_validate({**config.model_dump(), "location": "Reading", "service_groups": {"wiring": ["Wiring"]}, "phrases": [Phrase(phrase="Wiring Reading", landing_page=self.value["url"]).model_dump()]}), self.sid)
        r.revise(self.store, self.sid, self.record(), {"proposed": "Wiring Reading"})
        request = self.evaluate()
        packet = r.handoff(self.store, self.sid, request).decode()
        self.assertNotIn("Paoli", packet)
        self.assertNotIn("ADHD", packet)
        self.assertNotIn("clinical_review", packet)
        self.assertNotIn("other.example", packet)
        self.assertEqual(r.evaluations(self.store, self.other, self.value["action_id"]), [])
        with self.assertRaises(ValueError):
            r.import_model(self.store, self.other, request["id"], t.canonical(model_output(request)).encode())
        self.assertTrue(request["payload"]["mechanical"]["improves"])
        self.snapshot(title="Different value")
        self.assertTrue(r.is_stale(self.store, self.sid, request))
        with self.assertRaises(ValueError):
            r.import_model(self.store, self.sid, request["id"], t.canonical(model_output(request)).encode())

    def test_deterministic_factual_and_technical_blockers_cannot_be_overridden_by_model(self):
        r.revise(self.store, self.sid, self.record(), {"proposed": "Licensed provider"})
        request = self.evaluate()
        r.import_model(self.store, self.sid, request["id"], t.canonical(model_output(request)).encode())
        self.assertTrue(any("qualifications" in s for s in t.readiness(self.store, self.sid, self.record())["reasons"]))
        r.revise(self.store, self.sid, self.record(), {"proposed": "<script>alert(1)</script>"}, owner_confirmed=True, confirmation_source="Synthetic owner")
        self.evaluate()
        self.assertTrue(any("Executable" in s for s in t.readiness(self.store, self.sid, self.record())["reasons"]))
        with self.assertRaises(ValueError):
            t.freeze_batch(self.store, self.sid, [(self.value["action_id"], self.record()["revision"])])

    def test_backup_restore_keeps_assessments_history_and_requires_fresh_review(self):
        request = self.evaluate()
        r.import_model(self.store, self.sid, request["id"], t.canonical(model_output(request)).encode())
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "restored")
        history = r.evaluations(restored, self.sid, self.value["action_id"])
        self.assertEqual(len(history), 2)
        self.assertTrue(all(r.is_stale(restored, self.sid, e) for e in history))
        self.assertEqual(history[-1]["payload"]["model"], model_output(request))
        self.assertFalse(t.readiness(restored, self.sid, t.actions(restored, self.sid)[0])["ready"])

    def test_restore_rejects_tampered_assessment_site_binding(self):
        request = self.evaluate()
        request["payload"]["binding"]["site_id"] = self.other
        with self.store.db() as db:
            db.execute("UPDATE proposal_evaluations SET payload=? WHERE id=?", (t.canonical(request["payload"]), request["id"]))
        archive = self.root / "tampered.zip"
        _backup(self.store, archive)
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            _restore(archive, self.root / "tampered-restored")

    def test_audit_completeness_is_pinned_and_model_input_has_source_dates(self):
        request = self.evaluate()
        self.assertEqual(request["payload"]["input"]["audit_context"]["status"], "running")
        self.store.finish_audit(self.sid, self.aid, "partial", {"windows": {"current_start": "2026-07-01"}, "stages": {"inspection": {"status": "failed"}}})
        self.assertTrue(r.is_stale(self.store, self.sid, request))
        record = t.action(self.store, self.sid, self.value["action_id"], 1)
        r.assess(self.store, self.sid, record["action_id"], 1)
        current = r.evaluations(self.store, self.sid, self.value["action_id"])[-1]
        self.assertEqual(current["payload"]["input"]["audit_context"]["stages"]["inspection"]["status"], "failed")
        self.assertIn("partial", current["payload"]["input"]["limits"])

    def test_recommendation_origin_is_preserved_and_start_is_idempotent(self):
        self.store.save_findings(self.sid, self.aid, [{"site_id": self.sid, "audit_id": self.aid, "rule": "relevance", "rule_version": "1.0", "industry": "general", "profile_version": "1.0", "url": self.value["url"], "detail": "Original evidence", "proposed_action": "Original direction", "evidence": [{"file": "crawl.csv", "row": 2}], "confirmations": ["Owner service question"]}])
        finding = self.store.findings(self.sid, self.aid)[0]
        identity = r.from_finding(self.store, self.sid, self.aid, finding["id"], "title")
        self.assertEqual(r.from_finding(self.store, self.sid, self.aid, finding["id"], "text"), identity)
        record = t.action(self.store, self.sid, identity, 1)
        self.assertIsNone(record["payload"]["current"])
        r.revise(self.store, self.sid, record, {"proposed": "User alternative"})
        self.assertEqual(self.store.findings(self.sid, self.aid)[0], finding)
        self.assertEqual(finding["state"], "proposed")
