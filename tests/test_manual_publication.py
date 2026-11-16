import os
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent import manual_publication as m, page_tracking as p, proposal_review, publishing, tracking as t
from seo_agent.previews import save_preview
from seo_agent.storage import utc_now
from tests.test_review_previews import fixture
from tests.test_tracking import TrackingFixture


class ManualPublicationTests(TrackingFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.url = self.value["url"]
        bundle = fixture(self.sid, self.aid, self.url)
        page = bundle["pages"][0]
        page["captured_utc"] = utc_now()
        heading = page["tree"]["children"][0]
        page["tree"]["children"] = [{"id": "r3", "tag": "div", "children": [
            {"id": "r4", "tag": "div", "children": [heading]}]}]
        save_preview(self.store, self.sid, self.aid, bundle)
        t.from_preview(self.store, self.sid, self.aid, 1)
        record = t.actions(self.store, self.sid)[0]
        self.identity = record["action_id"]
        self.before, self.after = (record["payload"][k] for k in ("current", "proposed"))
        proposal_review.revise(self.store, self.sid, record, {"manual_post_title": {
            "page_id": 716, "widget_id": "022c973", "source": "Synthetic read-only page and widget export",
            "shared_effects": "Document title and navigation on the synthetic site reflect the page title",
        }}, owner_confirmed=True, confirmation_source="Synthetic owner")
        self.capture(self.before)

    def capture(self, heading, *, widget="022c973", title=None):
        html = (f"<html><head><title>{title or heading}</title></head><body>"
                f'<div data-elementor-type="wp-page" data-elementor-id="716">'
                f'<div data-id="{widget}" data-widget_type="heading.default"><h1>{heading}</h1></div>'
                "</div></body></html>")
        return p.save_snapshot(self.store, self.sid, self.url, status="complete", payload={
            "html": html, "headers": {}, "values": p.extract(html, self.url, {}),
            "final_url": self.url, "http_status": 200, "synthetic": True})

    def freeze(self):
        return t.freeze_batch(self.store, self.sid, [(self.identity, 2)])

    def approve(self, bid):
        return t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=True,
                                       statement="I approve this exact publication batch", confirmation_source="Synthetic owner")

    def test_requires_frozen_scope_and_fresh_human_approval(self):
        bid = self.freeze()
        with self.assertRaisesRegex(ValueError, "human approval"):
            m.begin(self.store, self.sid, bid, preflight_confirmed=True, source="Synthetic preflight")
        self.approve(bid)
        with self.assertRaisesRegex(ValueError, "manual page title"):
            publishing.approval(self.store, self.sid, bid)
        self.capture(self.before, title="Changed document title")
        self.capture(self.before)
        with self.assertRaisesRegex(ValueError, "stale"):
            m.begin(self.store, self.sid, bid, preflight_confirmed=True, source="Synthetic preflight")
        self.assertFalse(t.rows(self.store, "implementation_receipts", self.sid))

    def test_manual_report_and_public_verification_through_app(self):
        bid = self.freeze()
        p.save_settings(self.store, self.sid, {"enabled": False})
        app_path = Path(__file__).resolve().parent.parent / "app.py"
        with patch.dict(os.environ, {"SEO_DEMO": "1", "SEO_WORKSPACE": str(self.store.root)}):
            app = AppTest.from_file(str(app_path), default_timeout=20).run()
            app.sidebar.selectbox[0].select(self.sid).run()
            app.sidebar.radio[0].set_value("Recommendations & changes").run()
            next(c for c in app.checkbox if "authorize the listed manual" in c.label).check()
            next(i for i in app.text_input if i.label.startswith("Who confirmed")).set_value("Synthetic owner")
            next(i for i in app.text_input if i.label.startswith('Type "I approve')).set_value("I approve this exact publication batch")
            next(b for b in app.button if b.label == "Record my exact human approval").click().run()
            next(c for c in app.checkbox if c.label.startswith("I rechecked the approved CMS")).check()
            next(i for i in app.text_input if i.label == "Read-only preflight evidence reference").set_value("Synthetic preflight")
            next(b for b in app.button if b.label == "Record start of manual attempt").click().run()
            self.assertTrue(any("In WordPress Pages" in v.value for v in app.text))
            next(s for s in app.selectbox if s.label == "Manual publication outcome").select("reported_applied")
            next(i for i in app.text_input if i.label.startswith("Outcome time")).set_value(utc_now())
            next(i for i in app.text_area if i.label.startswith("Operator and outcome")).set_value("Synthetic editor report")
            next(b for b in app.button if b.label == "Record operator report").click().run()
            frozen, approval = m.context(self.store, self.sid, bid)
            self.assertEqual([v["outcome"] for v in m.history(self.store, self.sid, frozen, approval)], ["attempted", "reported_applied"])
            self.capture(self.after, widget="fffffff")
            app.run()
            self.assertFalse(any(b.label.startswith("Record independent public") for b in app.button))
            snapshot = self.capture(self.after)
            app.run()
            next(b for b in app.button if b.label == "Record independent public heading verification").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Public heading verified at capture" in v.value for v in app.text))
            self.assertTrue(any("Rollback requires fresh evidence" in v.value for v in app.caption))
            events = m.history(self.store, self.sid, frozen, approval)
            self.assertEqual(events[-1]["verification_snapshot_id"], snapshot)
            self.assertFalse(publishing.rows(self.store, self.sid, "cms_attempts"))

    def test_partial_report_preserves_actual_and_disallows_verification(self):
        bid = self.freeze()
        self.approve(bid)
        m.begin(self.store, self.sid, bid, preflight_confirmed=True, source="Synthetic preflight")
        m.report(self.store, self.sid, bid, outcome="partial", occurred=utc_now(), source="Synthetic operator", partial_value="Unexpected title")
        self.capture(self.after)
        with self.assertRaisesRegex(ValueError, "operator report"):
            m.verify(self.store, self.sid, bid)
        frozen, approval = m.context(self.store, self.sid, bid)
        self.assertEqual(m.history(self.store, self.sid, frozen, approval)[-1]["actual"], "Unexpected title")

    def test_outer_widget_cannot_claim_nested_heading(self):
        html = ('<html><body><div data-elementor-id="716" data-elementor-type="wp-page">'
                '<div data-id="022c973" data-widget_type="heading.default">'
                '<div data-id="fffffff" data-widget_type="heading.default"><h1>Our service</h1></div>'
                '</div></div></body></html>')
        record = t.action(self.store, self.sid, self.identity, 2)
        target = p.capture_target(self.store, self.sid, record)
        path = target["path"]
        nested_target = {**target, "path": [*path[:2], path[1], path[2]]}
        self.assertIsNone(p.observed_value({}, record["payload"], target=nested_target, html=html))
        inner = {**record["payload"], "manual_post_title": {**record["payload"]["manual_post_title"], "widget_id": "fffffff"}}
        self.assertEqual(p.observed_value({}, inner, target=nested_target, html=html), self.before)

    def test_staging_receipts_keep_their_existing_verification_contract(self):
        from seo_agent.storage import new_id

        base = {**self.receipt(environment="staging"), "action_id": self.identity, "revision": 2,
                "current": self.before, "proposed": self.after}
        t.record_receipt(self.store, self.sid, base)
        t.record_receipt(self.store, self.sid, {**base, "receipt_id": new_id(), "outcome": "reported_applied",
                                               "actual": self.after, "occurred_utc": utc_now()})
        t.record_receipt(self.store, self.sid, {**base, "receipt_id": new_id(), "outcome": "verification",
                                               "actual": self.after, "occurred_utc": utc_now(), "verification": "Synthetic staging evidence"})
