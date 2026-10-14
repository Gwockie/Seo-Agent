import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent import discovery as d, publishing
from seo_agent.config import SiteConfig
from seo_agent.storage import Store
from tests.test_discovery import FakeReader


def app_ui(root):
    import streamlit as st
    from pathlib import Path
    from seo_agent.storage import Store
    from seo_agent.discovery_ui import render
    store = Store(Path(root))
    sid = st.selectbox("Test site", [s["id"] for s in store.sites()], key="test_site")
    render(store, sid)


class DiscoveryUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "workspace")
        self.a = self.store.save_site(SiteConfig(name="A", url="https://example.com/", gsc_property="sc-domain:example.com"))
        self.b = self.store.save_site(SiteConfig(name="B", url="https://other.example/", gsc_property="sc-domain:other.example"))
    def tearDown(self):
        self.tmp.cleanup()
    def app(self):
        return AppTest.from_function(app_ui, args=(str(self.store.root),), default_timeout=30).run()
    def test_setup_refresh_history_and_site_switch(self):
        app = self.app()
        self.assertFalse(app.exception)
        next(t for t in app.text_input if t.label.startswith("Installation identity")).set_value("synthetic-A")
        next(b for b in app.button if b.label == "Save discovery connection").click().run()
        self.assertFalse(app.exception)
        saved = d.connections(self.store, self.a)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["installation_id"], "synthetic-A")
        self.assertIsNone(publishing.destination(self.store, self.a))
        next(t for t in app.text_input if t.label.startswith("Published page IDs")).set_value("9001")
        original = d.refresh
        with patch.object(d, "refresh", side_effect=lambda *a, **kw: original(*a, **kw, client_factory=FakeReader)):
            next(b for b in app.button if b.label == "Refresh read-only discovery").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Public REST page 9001" in t.value for t in app.text))
        self.assertTrue(any("public clue only" in t.value for t in app.text))
        app.selectbox[0].set_value(self.b).run()
        self.assertFalse(app.exception)
        self.assertEqual(d.connections(self.store, self.b), [])
        self.assertFalse(any("9001" in t.value for t in app.text))
        self.assertEqual(next(t.value for t in app.text_input if t.label.startswith("Canonical CMS home")), "https://other.example/")
        self.assertEqual(next(t.value for t in app.text_input if t.label.startswith("Installation identity")), "")
        self.assertEqual(next(t.value for t in app.text_input if t.label.startswith("Discovery application password")), "")
    def test_unknown_installation_and_failure_are_visible_without_losing_last_success(self):
        cid = d.configure(self.store, self.a, dict(label="Synthetic", provider="Unknown", method="public", url="https://example.com/", environment="production"))
        d.refresh(self.store, self.a, cid, client_factory=FakeReader)
        app = self.app()
        next(s for s in app.selectbox if s.label == "Discovery environment").set_value(cid).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("installation: unknown" in t.value for t in app.text))
        with patch.object(d, "refresh", side_effect=ValueError("secret failure sentinel")):
            next(b for b in app.button if b.label == "Refresh read-only discovery").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertNotIn("sentinel", app.error[0].value)
        self.assertTrue(any("Public REST page 9001" in t.value for t in app.text))
