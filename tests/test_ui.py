import os
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent.demo import seed_demo
from seo_agent.runner import run_site
from seo_agent.storage import Store

ROOT = Path(__file__).resolve().parent.parent


class UITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "demo"
        self.store = Store(self.workspace)
        seed_demo(self.store)
        self.ids = {s["name"]: s["id"] for s in self.store.sites()}
        for sid in self.ids.values():
            run_site(self.store, sid, demo=True, max_pages=5)
        self.env = patch.dict(os.environ, {"SEO_DEMO": "1", "SEO_WORKSPACE": str(self.workspace)})
        self.env.start()
        self.protection = patch("seo_agent.protection.storage_status", return_value={"verified": False, "reason": "Synthetic tests: live protected storage unavailable."})
        self.protection.start()

    def tearDown(self):
        self.protection.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_four_views_and_site_switch_no_stale_records(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        a, b, c = [self.ids[n] for n in ("Demo psychology A", "Demo psychology B", "Demo electrician")]
        app.sidebar.selectbox[0].select(a).run()
        app.sidebar.radio[0].set_value("Overview & audits").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "2.00")
        chart = json.loads(app.get("vega_lite_chart")[0].proto.spec)
        self.assertEqual(chart["encoding"]["x"]["scale"]["type"], "utc")
        self.assertEqual(chart["encoding"]["tooltip"][0]["type"], "nominal")
        rendered = "\n".join(t.value for t in app.text)
        self.assertIn("ADHD testing Paoli", rendered)
        app.sidebar.selectbox[0].select(b).run()
        self.assertFalse(app.exception)
        rendered = "\n".join(t.value for t in app.text)
        self.assertNotIn("ADHD testing Paoli", rendered)
        self.assertNotIn("psychology-a.example", rendered)
        app.sidebar.selectbox[0].select(c).run()
        self.assertFalse(app.exception)
        rendered = "\n".join(t.value for t in app.text)
        self.assertNotIn("clinical_review", rendered)
        self.assertNotIn("ADHD", rendered)
        self.assertNotIn("Paoli", rendered)
        for view in ("Target phrases", "Recommendations & changes", "Setup"):
            app.sidebar.radio[0].set_value(view).run()
            self.assertFalse(app.exception)
        app.sidebar.selectbox[0].select(None).run()
        self.assertFalse(app.exception)
        self.assertEqual([box for box in app.selectbox if box.label == "Industry"][0].value, "general")

    def test_guided_setup_rows_and_save_preserve_existing_settings(self):
        from streamlit import config as streamlit_config
        sid = self.ids["Demo psychology A"]
        before = self.store.site(sid).model_dump()
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(sid).run()
        app.sidebar.radio[0].set_value("Setup").run()
        self.assertFalse(app.exception)
        self.assertFalse(any("JSON" in a.label for a in app.text_area))
        self.assertTrue(streamlit_config.get_option("client.disableDataExport"))
        columns = [set(df.value.columns) for df in app.dataframe]
        self.assertIn({"Service group", "Related search term"}, columns)
        self.assertIn({"Fact", "Confirmed value"}, columns)
        self.assertTrue(next(t for t in app.text_input if t.label == "Final public URL").disabled)
        self.assertTrue(next(t for t in app.text_input if t.label == "Business name").proto.help)
        next(b for b in app.button if b.label == "Save local profile").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.store.site(sid).model_dump(), before)

    def test_tracking_seed_explanations_and_reviews_are_scoped_and_persistent(self):
        from seo_agent.learning import plans, reviews
        sid = self.ids["Demo psychology A"]
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(sid).run()
        app.sidebar.radio[0].set_value("Recommendations & changes").run()
        self.assertTrue(any(m.value == "**What we expect**" for m in app.markdown))
        next(b for b in app.button if b.label == "Prepare a tracking plan").click().run()
        self.assertEqual(app.sidebar.radio[0].value, "Changes & results")
        self.assertFalse(app.exception)
        self.assertTrue(next(t for t in app.text_area if t.label == "Why we recommend it").value)
        self.assertTrue(next(t for t in app.text_area if t.label == "Expected effect — a hypothesis").value)
        next(b for b in app.button if b.label == "Save tracking plan").click().run()
        self.assertFalse(app.exception)
        record = plans(self.store, sid)[0]
        self.assertTrue(any("No published implementation" in c.value for c in app.caption))
        next(t for t in app.text_area if t.label == "What we learned / what remains uncertain").set_value("Waiting for implementation; no outcome yet")
        next(b for b in app.button if b.label == "Save evidence review").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(reviews(self.store, sid, record["id"])[0]["payload"]["comparison"]["status"], "not ready")
        app.sidebar.selectbox[0].select(self.ids["Demo psychology B"]).run()
        self.assertEqual(plans(self.store, self.ids["Demo psychology B"]), [])
        self.assertNotIn("Waiting for implementation; no outcome yet", [t.value for t in app.text])

    def test_single_saved_site_reopens_in_review_without_changing_its_profile(self):
        sid = self.ids["Demo electrician"]
        original = self.store.site(sid).model_dump()
        only = [{"id": sid, "name": original["name"]}]
        with patch("seo_agent.storage.Store.sites", return_value=only):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.sidebar.selectbox[0].value, sid)
        self.assertEqual(app.sidebar.radio[0].value, "Recommendations & changes")
        self.assertEqual(self.store.site(sid).model_dump(), original)

    def test_rerun_does_not_duplicate_launch_or_redirect_job(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        a = self.ids["Demo psychology A"]
        app.sidebar.selectbox[0].select(a).run()
        app.sidebar.radio[0].set_value("Overview & audits").run()
        launch = [b for b in app.button if b.label == "Run synthetic audit"][0]
        launch.click().run()
        # Completion happens off-thread; wait in short bounded intervals.
        for _ in range(30):
            if len(self.store.audits(a)) == 2 and self.store.audits(a)[0]["status"] != "running":
                break
            time.sleep(.05)
        app.run()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(self.store.audits(a)), 2)
        [button for button in app.button if button.label == "Refresh history"][0].click().run()
        self.assertEqual([box for box in app.selectbox if box.label == "Audit"][0].value, self.store.audits(a)[0]["id"])
        b = self.ids["Demo psychology B"]
        app.sidebar.selectbox[0].select(b).run()
        self.assertEqual(len(self.store.audits(b)), 1)
        self.assertNotIn("psychology-a.example", "\n".join(t.value for t in app.text))

    def test_untrusted_report_is_literal_text(self):
        sid = self.ids["Demo electrician"]
        aid = self.store.audits(sid)[0]["id"]
        payload = '<script>window.SECRET="bad"</script> [click](javascript:alert(1))'
        path = self.store.audit_file(sid, aid, "reports", "executive-summary.md")
        path.write_text(payload, encoding="utf-8")
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(sid).run()
        app.sidebar.radio[0].set_value("Overview & audits").run()
        self.assertFalse(app.exception)
        self.assertIn(payload, [t.value for t in app.text])
        self.assertFalse(any("window.SECRET" in str(m.value) for m in app.markdown))

    def test_reviewed_reports_are_literal_and_stay_with_selected_audit(self):
        sid = self.ids["Demo psychology A"]
        aid = self.store.audits(sid)[0]["id"]
        payload = 'REVIEWED_SENTINEL <script>untrusted()</script>'
        self.store.audit_file(sid, aid, "reports", "reviewed-executive-summary.md").write_text(payload, encoding="utf-8")
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(sid).run()
        app.sidebar.radio[0].set_value("Overview & audits").run()
        report = [box for box in app.selectbox if box.label == "View report"][0]
        self.assertEqual(report.value, "reviewed-executive-summary.md")
        self.assertIn(payload, [text.value for text in app.text])
        self.assertFalse(any("untrusted()" in str(text.value) for text in app.markdown))
        app.sidebar.selectbox[0].select(self.ids["Demo psychology B"]).run()
        self.assertNotIn("reviewed-executive-summary.md", [box for box in app.selectbox if box.label == "View report"][0].options)
        self.assertNotIn(payload, [text.value for text in app.text])
        self.assertFalse(app.exception)

    def test_review_view_uses_selected_audit_and_keeps_reports_inert(self):
        sid = self.ids["Demo psychology A"]
        aid = self.store.audits(sid)[0]["id"]
        summary = 'SUMMARY_SENTINEL ![untrusted](https://external.example/image)'
        edits = 'EDITS_SENTINEL <script>untrusted()</script>'
        for name, content in (("reviewed-executive-summary.md", summary), ("reviewed-proposed-edits.md", edits)):
            self.store.audit_file(sid, aid, "reports", name).write_text(content, encoding="utf-8")
        with self.store.db() as db:
            db.execute("UPDATE audits SET status='partial' WHERE id=?", (aid,))
        newer = run_site(self.store, sid, demo=True, max_pages=5)
        before = self.store.changes(sid)
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(sid).run()
        app.sidebar.radio[0].set_value("Recommendations & changes").run()
        self.assertFalse(any(r.label == "Review document" for r in app.radio))
        [box for box in app.selectbox if box.label == "Audit"][0].select(aid).run()
        review = [radio for radio in app.radio if radio.label == "Review document"][0]
        self.assertEqual(review.value, "Summary")
        self.assertIn(summary, [text.value for text in app.text])
        self.assertTrue(any("audit is incomplete" in w.value for w in app.warning))
        review.set_value("Proposed edits").run()
        self.assertIn(edits, [text.value for text in app.text])
        self.assertFalse(any("EDITS_SENTINEL" in str(m.value) or "external.example" in str(m.value) for m in app.markdown))
        self.assertTrue(any("does not approve" in str(info.value) for info in app.info))
        [box for box in app.selectbox if box.label == "Audit"][0].select(newer).run()
        self.assertFalse(any(r.label == "Review document" for r in app.radio))
        self.assertNotIn(edits, [text.value for text in app.text])
        app.sidebar.selectbox[0].select(self.ids["Demo psychology B"]).run()
        self.assertFalse(any(r.label == "Review document" for r in app.radio))
        self.assertNotIn(summary, [text.value for text in app.text])
        self.assertEqual(self.store.changes(sid), before)
        self.assertFalse(app.exception)

    def test_native_table_csv_downloads_receive_escaped_cells(self):
        import pandas as pd
        sid = self.ids["Demo electrician"]
        aid = self.store.audits(sid)[0]["id"]
        path = self.store.audit_file(sid, aid, "data", "gsc_query_page.csv")
        pd.DataFrame([{"query": "=SYNTHETIC_FORMULA", "page": self.store.site(sid).url, "clicks": 1, "impressions": 10, "ctr": .1, "position": 5}]).to_csv(path, index=False)
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(sid).run()
        app.sidebar.radio[0].set_value("Overview & audits").run()
        self.assertFalse(app.exception)
        table = [t.value for t in app.dataframe if "query" in t.value.columns][0]
        self.assertEqual(table.iloc[0]["query"], "'=SYNTHETIC_FORMULA")
        self.assertEqual(pd.read_csv(path).iloc[0]["query"], "=SYNTHETIC_FORMULA")

    def test_live_app_stops_before_private_workspace_creation_when_unprotected(self):
        from seo_agent.protection import ProtectionError
        target = self.workspace.parent / "private-unprotected"
        with patch.dict(os.environ, {"SEO_DEMO": "0", "SEO_WORKSPACE": str(target)}), patch("seo_agent.protection.require_protected", side_effect=ProtectionError("Storage protection unavailable")):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertFalse(target.exists())
        self.assertTrue(any("Storage protection unavailable" in w.value for w in app.warning))
        self.assertFalse(app.sidebar.selectbox)
        self.assertFalse(any(b.label == "Run read-only audit" for b in app.button))

    def test_unencrypted_local_setup_keeps_audit_disabled_without_account(self):
        sid = self.ids["Demo electrician"]
        config = self.store.site(sid)
        config.connection_id = None
        self.store.save_site(config, sid)
        status = {"verified": True, "encrypted": False, "encryption_required": False,
                  "reason": "Restricted folder access verified. Disk encryption is optional for this local app."}
        with patch.dict(os.environ, {"SEO_DEMO": "0"}), patch("seo_agent.protection.storage_status", return_value=status), patch("seo_agent.credentials.load_connection") as load:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
            app.sidebar.selectbox[0].select(sid).run()
            self.assertTrue(any("encryption is optional" in info.value for info in app.info))
            app.sidebar.radio[0].set_value("Overview & audits").run()
        self.assertFalse(app.exception)
        self.assertTrue([button for button in app.button if button.label == "Run read-only audit"][0].disabled)
        load.assert_not_called()

    def test_new_site_imports_appearance_once_and_demo_stays_offline(self):
        with patch("seo_agent.appearance.capture_appearance") as capture:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
            for label, value in (("Business name", "New site"), ("Final public URL", "https://new.example/"), ("Exact Search Console property", "sc-domain:new.example")):
                [field for field in app.text_input if field.label == label][0].set_value(value)
            [button for button in app.button if button.label == "Save local profile"][0].click().run()
            app.run()
        self.assertFalse(app.exception)
        capture.assert_called_once()
        self.assertTrue(capture.call_args.kwargs["demo"])
        self.assertEqual(self.store.site(capture.call_args.args[1]).name, "New site")

    def test_page_previews_stay_with_selected_site_and_keep_approval_requirement(self):
        from seo_agent.previews import save_preview
        from tests.test_review_previews import fixture
        sid = self.ids["Demo psychology A"]
        aid = self.store.audits(sid)[0]["id"]
        save_preview(self.store, sid, aid, fixture(sid, aid, self.store.site(sid).url))
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(sid).run()
        app.sidebar.radio[0].set_value("Recommendations & changes").run()
        self.assertTrue(any(box.label == "Page to compare" for box in app.selectbox))
        self.assertTrue(any("separate approval" in info.value for info in app.info))
        self.assertEqual(len(app.get("iframe")), 1)
        [r for r in app.radio if r.label == "Page display"][0].set_value("Side by side").run()
        self.assertEqual(len(app.get("iframe")), 2)
        app.sidebar.selectbox[0].select(self.ids["Demo electrician"]).run()
        self.assertFalse(any(box.label == "Page to compare" for box in app.selectbox))
        self.assertFalse(app.exception)

    def test_site_appearance_switches_without_leaking_previous_fonts(self):
        from seo_agent.appearance import save_appearance
        from tests.test_review_previews import fixture
        a, b = self.ids["Demo psychology A"], self.ids["Demo electrician"]
        for sid, font, accent in ((a, "Cambria", "#ac7658"), (b, "Verdana", "#245ba1")):
            appearance = fixture(sid, self.store.audits(sid)[0]["id"], self.store.site(sid).url)["appearance"]
            appearance.update(heading_font=font, accent=accent)
            save_appearance(self.store, sid, appearance)
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.sidebar.selectbox[0].select(a).run()
        self.assertTrue(any("Cambria" in e.proto.body for e in app.get("html")))
        app.sidebar.selectbox[0].select(b).run()
        self.assertTrue(any("Verdana" in e.proto.body for e in app.get("html")))
        self.assertFalse(any("Cambria" in e.proto.body for e in app.get("html")))
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
