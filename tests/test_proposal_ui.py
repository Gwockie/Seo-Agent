import os
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from seo_agent import tracking as t, proposal_review as r, page_tracking as p
from tests.test_tracking import TrackingFixture
from tests.test_proposal_review import model_output

ROOT = Path(__file__).resolve().parent.parent


class ProposalUITests(TrackingFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.import_action()
        self.snapshot()
        p.save_settings(self.store, self.sid, {"enabled": False})
        p.save_settings(self.store, self.other, {"enabled": False})
        self.env = patch.dict(os.environ, {"SEO_DEMO": "1", "SEO_WORKSPACE": str(self.store.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(self.sid).run()
        app.sidebar.radio[0].set_value("Recommendations & changes").run()
        self.assertFalse(app.exception)
        return app

    def test_edit_compare_evaluate_restore_saved_revision_without_approval(self):
        app = self.app()
        self.assertFalse(any(i.label == "Exact current value" for i in app.text_area))
        next(i for i in app.text_area if i.label == "Exact proposed value").set_value("User alternative")
        next(i for i in app.text_area if i.label.startswith("Reason for revision")).set_value("Less promotional language")
        next(i for i in app.text_area if i.label == "How to measure results").set_value("Inspect title and compare complete finalized windows")
        next(b for b in app.button if b.label == "Save new proposal revision").click().run()
        self.assertFalse(app.exception)
        record = t.actions(self.store, self.sid)[0]
        self.assertEqual(record["revision"], 2)
        self.assertEqual(record["payload"]["revision_note"], "Less promotional language")
        self.assertEqual(record["payload"]["current"], "Before")
        self.assertTrue(app.dataframe)
        next(i for i in app.text_area if i.label == "Exact proposed value").set_value("Unsaved wording")
        next(b for b in app.button if b.label == "Evaluate this saved revision").click().run()
        self.assertFalse(app.exception)
        evaluation = r.evaluations(self.store, self.sid, self.value["action_id"])[0]
        self.assertEqual(evaluation["revision"], 2)
        self.assertEqual(evaluation["payload"]["input"]["proposal"]["proposed"], "User alternative")
        self.assertTrue(any("Model review unavailable" in i.value for i in app.info))
        self.assertTrue(any("Mandatory blockers" in i.value and "Owner confirmation" in i.value for i in app.text))
        next(s for s in app.selectbox if s.label == "Compare latest proposal with").select(1).run()
        next(b for b in app.button if b.label == "Restore as new revision").click().run()
        self.assertEqual(t.actions(self.store, self.sid)[0]["revision"], 3)
        self.assertEqual(t.actions(self.store, self.sid)[0]["payload"]["proposed"], "After")
        self.assertTrue(any("Historical assessment" in i.value for i in app.warning))
        self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
        self.assertEqual(t.rows(self.store, "implementation_receipts", self.sid), [])
        self.assertFalse(app.exception)

    def test_model_judgment_and_mandatory_questions_are_distinct_from_advice(self):
        request_id = r.assess(self.store, self.sid, self.value["action_id"], 1)
        request = r.evaluations(self.store, self.sid, self.value["action_id"])[-1]
        raw = model_output(request, questions=["Owner confirms emergency availability"])
        r.import_model(self.store, self.sid, request_id, t.canonical(raw).encode())
        app = self.app()
        self.assertTrue(any("advisory interpretation" in m.value for m in app.markdown))
        self.assertTrue(any("Mandatory owner questions" in i.value for i in app.text))
        self.assertTrue(any("Prefer a shorter title" in i.value for i in app.text))
        self.assertTrue(next(c for c in app.checkbox if c.label.startswith("Include title")).disabled)
        self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
        app.sidebar.selectbox[0].select(self.other).run()
        self.assertFalse(any("Synthetic local reviewer" in i.value for i in app.text))
        self.assertFalse(app.exception)

    def test_recommendation_edit_action_preserves_original_finding(self):
        self.store.save_findings(self.sid, self.aid, [{"site_id": self.sid, "audit_id": self.aid, "rule": "relevance", "rule_version": "1.0", "industry": "general", "profile_version": "1.0", "priority": "P1", "category": "Relevance", "url": self.value["url"], "detail": "Original source evidence", "proposed_action": "Original direction", "evidence": [{"file": "crawl.csv", "row": 2}], "confirmations": ["Owner confirms service"]}])
        original = self.store.findings(self.sid, self.aid)[0]
        app = self.app()
        next(b for b in app.button if b.label == "Edit / Revise recommendation").click().run()
        self.assertFalse(app.exception)
        linked = next(a for a in t.actions(self.store, self.sid) if a["payload"].get("recommendation_id") == original["id"])
        self.assertEqual(linked["revision"], 1)
        self.assertIsNone(linked["payload"]["current"])
        self.assertEqual(self.store.findings(self.sid, self.aid)[0], original)
        next(b for b in app.button if b.label == "Edit / Revise recommendation").click().run()
        self.assertEqual(len(t.actions(self.store, self.sid)), 2)
        self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
