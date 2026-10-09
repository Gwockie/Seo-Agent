import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent import tracking as t, page_tracking as p, trends
from tests.test_tracking import TrackingFixture

ROOT = Path(__file__).resolve().parent.parent


class TrackingUITests(TrackingFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.import_action()
        self.snapshot()
        p.save_settings(self.store, self.sid, {"enabled": False})
        self.env = patch.dict(os.environ, {"SEO_DEMO": "1", "SEO_WORKSPACE": str(self.store.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def app(self, view="Recommendations & changes"):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(self.sid).run()
        app.sidebar.radio[0].set_value(view).run()
        self.assertFalse(app.exception)
        return app

    def test_frozen_review_records_explicit_human_only_and_no_implementation(self):
        with patch("seo_agent.page_tracking.PublicFetcher") as fetch:
            app = self.app()
            next(c for c in app.checkbox if c.label.startswith("Include title")).check().run()
            next(b for b in app.button if b.label == "Freeze selected publication batch").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
            next(c for c in app.checkbox if c.label.startswith("I reviewed the exact actions")).check()
            next(i for i in app.text_input if i.label == "Who confirmed the factual items and when?").set_value("Synthetic human confirmed on October 8")
            next(i for i in app.text_input if i.label.startswith('Type "I approve')).set_value("I approve this exact publication batch")
            next(b for b in app.button if b.label == "Record my exact human approval").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(t.rows(self.store, "human_approvals", self.sid)), 1)
        self.assertEqual(t.rows(self.store, "implementation_receipts", self.sid), [])
        fetch.assert_not_called()
        self.assertTrue(any("Publishing remains unavailable" in box.value for box in app.info))

    def test_revised_proposal_keeps_frozen_history_and_disables_old_approval(self):
        bid = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        app = self.app()
        next(i for i in app.text_area if i.label == "Exact proposed value").set_value("Newer proposal")
        next(b for b in app.button if b.label == "Save new proposal revision").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(t.actions(self.store, self.sid)[0]["revision"], 2)
        self.assertEqual(t.batch(self.store, self.sid, bid)["payload"]["actions"][0]["action"]["proposed"], "After")
        self.assertTrue(next(b for b in app.button if b.label == "Record my exact human approval").disabled)

    def test_outside_marker_details_stay_literal_and_site_scoped(self):
        self.snapshot("Outside title", extra="<p>New exact copy</p>")
        app = self.app("Changes & results")
        self.assertTrue(any(s.label == "Select a change marker" for s in app.selectbox))
        self.assertTrue(app.get("json"))
        self.assertFalse(app.exception)
        self.assertTrue(any("No causal attribution" in c.value for c in app.caption))
        app.sidebar.selectbox[0].select(self.other).run()
        self.assertFalse(any(s.label == "Select a change marker" for s in app.selectbox))
        self.assertFalse(app.exception)

    def test_moved_heading_disables_frozen_human_approval(self):
        from seo_agent.previews import save_preview
        from seo_agent.storage import utc_now
        from tests.test_review_previews import fixture
        bundle = fixture(self.sid, self.aid, self.value["url"])
        page = bundle["pages"][0]
        page["captured_utc"] = utc_now()
        page["tree"]["children"] = [
            {"id": "r2", "tag": "h1", "children": [{"text": "Service"}]},
            {"id": "r3", "tag": "p", "children": [{"text": "Price $42 on October 8"}]},
            {"id": "r4", "tag": "a", "href": self.value["url"], "children": [{"text": "Service link"}]}]
        page["actions"][0].update(current="Service", proposed="New service")
        save_preview(self.store, self.sid, self.aid, bundle)
        t.from_preview(self.store, self.sid, self.aid, 1)
        record = next(r for r in t.actions(self.store, self.sid) if r["payload"]["action_kind"] == "text")
        t.save_action(self.store, self.sid, self.aid, {**record["payload"], "confirmations": self.value["confirmations"]}, revision=2)
        t.freeze_batch(self.store, self.sid, [(record["action_id"], 2)])
        app = self.app()
        self.assertFalse(next(b for b in app.button if b.label == "Record my exact human approval").disabled)
        html = p.latest_snapshot(self.store, self.sid, self.value["url"])["payload"]["html"]
        html = html.replace("<h1>Service</h1>", "<h1>Changed heading</h1>").replace("</body>", "<footer>Service</footer></body>")
        p.save_snapshot(self.store, self.sid, self.value["url"], status="complete", payload={"html": html, "headers": {}, "http_status": 200,
            "final_url": self.value["url"], "values": p.extract(html, self.value["url"], {}), "synthetic": True})
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(next(b for b in app.button if b.label == "Record my exact human approval").disabled)
        self.assertTrue(next(c for c in app.checkbox if c.label.startswith("Include text")).disabled)

    def test_reruns_do_not_duplicate_refresh_and_settings_are_bounded(self):
        p.save_settings(self.store, self.sid, {"enabled": True})
        with patch("seo_agent.page_tracking.observe", return_value={"status": "complete"}) as observe:
            app = self.app("Changes & results")
            app.run()
            app.run()
            app.run()
        self.assertFalse(app.exception)
        observe.assert_called_once()
        self.assertEqual(len(t.rows(self.store, "tracking_checks", self.sid)), 1)
        self.assertEqual(next(i for i in app.number_input if i.label == "Maximum pages per check").max, 20)


if __name__ == "__main__":
    unittest.main()
