import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from seo_agent import scheduling as weekly
from seo_agent.demo import seed_demo
from seo_agent.storage import Store

ROOT = Path(__file__).resolve().parent.parent


class WeeklyUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "demo")
        seed_demo(self.store)
        from seo_agent.page_tracking import save_settings
        for site in self.store.sites():
            save_settings(self.store, site["id"], {"enabled": False})
        self.sid, self.other = [s["id"] for s in self.store.sites()][:2]
        self.env = patch.dict(os.environ, {"SEO_DEMO": "1", "SEO_WORKSPACE": str(self.store.root)})
        self.env.start()
        self.app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.app.sidebar.selectbox[0].select(self.sid).run()
        self.app.sidebar.radio[0].set_value("Overview & audits").run()

    def tearDown(self):
        from app import jobs
        current = jobs().current
        if current:
            jobs().records[current]["future"].result(timeout=20)
        self.env.stop()
        self.tmp.cleanup()

    def test_save_enable_disable_and_site_isolation_no_task_side_effect(self):
        app = self.app
        with patch("seo_agent.windows_tasks.invoke") as task:
            next(c for c in app.checkbox if c.label == "Enable this site's weekly schedule").check()
            next(b for b in app.button if b.label == "Save weekly schedule").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(weekly.schedule(self.store, self.sid)["settings"]["enabled"])
            app.run()
            next(b for b in app.button if b.label == "Disable weekly schedule").click().run()
            self.assertFalse(weekly.schedule(self.store, self.sid)["settings"]["enabled"])
            app.sidebar.selectbox[0].select(self.other).run()
            self.assertTrue(any("Last attempt: None" in t.value for t in app.text))
        task.assert_not_called()

    def test_run_now_reruns_do_not_repeat_collection(self):
        app = self.app
        next(b for b in app.button if b.label == "Run weekly audit now").click().run()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if weekly.attempts(self.store, self.sid) and weekly.attempts(self.store, self.sid)[0]["finished"]:
                break
            time.sleep(.1)
        app.run(); app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(weekly.attempts(self.store, self.sid)), 1)
        self.assertEqual(weekly.attempts(self.store, self.sid)[0]["payload"]["status"], "complete")
        self.assertTrue(any("Last complete collection:" in t.value and "None" not in t.value for t in app.text))
        self.assertTrue(any("Last attempt:" in t.value and "— complete" in t.value and " at " in t.value for t in app.text))

    def test_invalid_timezone_shows_local_actionable_error(self):
        app = self.app
        next(i for i in app.text_input if i.label == "Time zone").set_value("Unknown/Zone")
        next(b for b in app.button if b.label == "Save weekly schedule").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Check the time zone" in e.value for e in app.error))
        self.assertFalse(weekly.schedule(self.store, self.sid)["settings"]["enabled"])
