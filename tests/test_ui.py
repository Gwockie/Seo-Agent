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


if __name__ == "__main__":
    unittest.main()
