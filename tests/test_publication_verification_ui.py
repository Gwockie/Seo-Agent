import copy
import json
import unittest
from io import BytesIO
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from seo_agent import publication_verification as verification
from tests import test_publication_verification as fixtures


def verification_app(root, sid):
    from pathlib import Path
    from seo_agent.storage import Store
    from seo_agent.publication_verification_ui import render
    render(Store(Path(root), read_only=True), sid)


class PublicationVerificationUITests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.PublicationVerificationTests()
        self.f.setUp()
        f = self.f
        self.before = f.capture(f.url, "Old", 1)
        self.after = f.capture(f.url, "New", 2)
        self.later = f.capture(f.url, "Unrelated later", 3)
        self.declaration = f.declaration(self.before, self.after, [
            {"kind": "heading", "selector": "#service", "before": "Old", "after": "New"},
            {"kind": "breadcrumb", "selector": "#crumb > span", "before": "Old", "after": "New"},
            {"kind": "navigation_label", "selector": "nav a[href='/service/']", "before": "Old", "after": "New"},
            {"kind": "document_title", "before": "Old | Example", "after": "New | Example"},
            {"kind": "canonical", "before": f.url, "after": f.url},
            {"kind": "robots", "before": "index, follow", "after": "index, follow"},
            {"kind": "googlebot", "before": "noarchive", "after": "noarchive"},
            {"kind": "x_robots_tag", "before": "", "after": ""},
        ])

    def tearDown(self):
        self.f.tearDown()

    def app(self, sid=None):
        return AppTest.from_function(verification_app, args=(str(self.f.store.root), sid or self.f.sid), default_timeout=20).run()

    def click(self, app, label):
        next(b for b in app.button if b.label == label).click().run()
        self.assertFalse(app.exception)

    def load(self, app, declaration=None):
        app.text_area[0].set_value(json.dumps(declaration or self.declaration))
        self.click(app, "Import expectations")

    def result(self, app):
        return app.session_state[self.f.sid + ":publication_verification:result"]["report"]

    def test_import_all_kinds_exact_historical_report_and_downloads_are_read_only(self):
        original = self.f.store.db_path.read_bytes()
        downloads = {}
        actual_download = st.download_button

        def download(label, data, *args, **kwargs):
            downloads[label] = data
            return actual_download(label, data, *args, **kwargs)

        with patch("streamlit.download_button", side_effect=download), \
                patch.object(verification, "report", wraps=verification.report) as verifier, \
                patch("socket.create_connection", side_effect=AssertionError("No network allowed")):
            app = self.app()
            self.assertFalse(app.exception)
            self.assertTrue(all(s.value is None for s in app.selectbox if "capture" in s.label))
            self.load(app)
            self.assertEqual(len([s for s in app.selectbox if s.label == "Effect kind"]), 8)
            self.click(app, "Run read-only verifier")
            self.assertEqual(verifier.call_count, 1)
            result = self.result(app)
            self.assertEqual(result, verification.report(self.f.store, self.declaration))
            self.assertEqual(len(app.success), 8)
            self.assertEqual(json.loads(downloads["Download expectations JSON"]),
                             verification.Expectations.model_validate(self.declaration).model_dump())
            self.assertEqual(json.loads(downloads["Download verification report JSON"]), result)
            reference = result["pages"][0]["after_capture"]
            self.assertEqual(reference["snapshot_id"], self.after)
            self.assertEqual(reference["checked_utc"], "2025-01-02T00:00:00+00:00")
            self.assertEqual(reference["status"], "complete")
            self.assertEqual(len(reference["record_sha256"]), 64)
            self.assertIn("not publication approval", " ".join(c.value for c in app.caption))
        self.assertEqual(self.f.store.db_path.read_bytes(), original)

    def test_edit_form_invalidate_result_then_rerun_with_exact_capture(self):
        app = self.app()
        self.load(app)
        self.click(app, "Run read-only verifier")
        next(a for a in app.text_area if a.label == "Expected after").set_value("Wrong expectation").run()
        self.assertTrue(any("form changed" in w.value for w in app.warning))
        self.assertFalse(app.get("download_button") and any(
            b.proto.label == "Download verification report JSON" for b in app.get("download_button")))
        self.click(app, "Run read-only verifier")
        self.assertEqual(self.result(app)["pages"][0]["effects"][0]["status"], "mismatch")
        self.assertTrue(any('After expected: "Wrong expectation"' in t.value and 'After observed: "New"' in t.value for t in app.text))
        newer = self.f.capture(self.f.url, "Yet newer", 4)
        app.run()
        self.assertEqual(next(s for s in app.selectbox if s.label == "After capture").value, self.after)
        self.assertNotEqual(self.after, newer)

    def test_multi_page_grouping_and_unavailable_reasons(self):
        declaration = copy.deepcopy(self.declaration)
        declaration["pages"][0]["effects"][0]["after"] = "Unexpected"
        before = self.f.capture(self.f.shared, "Old", 1)
        after = self.f.capture(self.f.shared, "New", 2, body="<main>No heading</main>")
        declaration["pages"] += self.f.declaration(before, after, [
            {"kind": "heading", "selector": "#service", "before": "Old", "after": "New"}], url=self.f.shared)["pages"]
        app = self.app()
        self.load(app, declaration)
        self.click(app, "Run read-only verifier")
        self.assertEqual([p["url"] for p in self.result(app)["pages"]], [self.f.url, self.f.shared])
        self.assertEqual(self.result(app)["pages"][1]["effects"][0]["status"], "unavailable")
        self.assertTrue(any("Expected exactly one element" in t.value for t in app.text))
        self.assertTrue(app.error)
        self.assertTrue(app.warning)

    def test_file_import_rejects_wrong_site_and_invalid_schema_preserving_form(self):
        app = self.app()
        with patch("streamlit.file_uploader", return_value=BytesIO(json.dumps(self.declaration).encode())):
            self.click(app, "Import expectations")
        self.assertEqual(next(s for s in app.selectbox if s.label == "After capture").value, self.after)
        for raw in ["{bad", json.dumps({**self.declaration, "site_id": self.f.other}),
                    json.dumps({**self.declaration, "schema_version": "unknown"})]:
            app.text_area[0].set_value(raw)
            self.click(app, "Import expectations")
            self.assertTrue(app.error)
            self.assertEqual(next(s for s in app.selectbox if s.label == "After capture").value, self.after)

    def test_missing_and_cross_site_references_are_never_substituted(self):
        wrong = self.f.capture("https://other.example/", "Private other site", 2, sid=self.f.other)
        declaration = copy.deepcopy(self.declaration)
        declaration["pages"][0]["after_snapshot_id"] = wrong
        app = self.app()
        self.load(app, declaration)
        self.assertEqual(next(s for s in app.selectbox if s.label == "After capture").value, wrong)
        self.click(app, "Run read-only verifier")
        result = self.result(app)
        self.assertEqual(result["pages"][0]["after_capture"], {"snapshot_id": wrong})
        self.assertTrue(all(e["status"] == "unavailable" for e in result["pages"][0]["effects"]))
        self.assertNotIn("Private other site", " ".join(t.value for t in app.text))

    def test_manual_entry_requires_explicit_captures_and_supports_effect_edits(self):
        app = self.app()
        next(t for t in app.text_input if t.label == "Exact page URL").set_value(self.f.url).run()
        self.click(app, "Run read-only verifier")
        self.assertTrue(app.error)
        next(s for s in app.selectbox if s.label == "Before capture").select(self.before)
        next(s for s in app.selectbox if s.label == "After capture").select(self.after)
        next(t for t in app.text_input if t.label == "Exact CSS selector").set_value("#service")
        next(t for t in app.text_area if t.label == "Expected before").set_value("Old")
        next(t for t in app.text_area if t.label == "Expected after").set_value("New")
        self.click(app, "Run read-only verifier")
        self.assertEqual(self.result(app)["pages"][0]["effects"][0]["status"], "matches_expectation")
        next(n for n in app.number_input if n.label == "Number of expected effects").set_value(2).run()
        self.assertEqual(len([s for s in app.selectbox if s.label == "Effect kind"]), 2)
        next(n for n in app.number_input if n.label == "Number of expected effects").set_value(1).run()
        next(s for s in app.selectbox if s.label == "Effect kind").select("document_title").run()
        self.assertFalse(any(t.label == "Exact CSS selector" for t in app.text_input))


if __name__ == "__main__":
    unittest.main()
