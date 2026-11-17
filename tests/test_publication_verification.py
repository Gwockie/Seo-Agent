import copy
import io
import json
import sqlite3
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from seo_agent import page_tracking, tracking
from seo_agent.__main__ import main
from seo_agent.publication_verification import Expectations, report
from seo_agent.storage import Store, new_id
from tests.test_tracking import TrackingFixture


class PublicationVerificationTests(TrackingFixture, unittest.TestCase):
    url = "https://example.com/service/"
    shared = "https://example.com/contact/"

    def capture(self, url, label, day, *, metadata=None, body=None, headers=None, sid=None, synthetic=True):
        if metadata is None:
            metadata = (f'<title>{label} | Example</title><link rel="canonical" href="{url}">'
                        '<meta name="robots" content="index, follow"><meta name="googlebot" content="noarchive">')
        if body is None:
            body = (f'<h1 id="service">{label}</h1><div id="crumb"><span>{label}</span></div>'
                    f'<nav><a href="/service/">{label}</a><a href="/other/">Other</a></nav>')
        html = f"<html><head>{metadata}</head><body>{body}</body></html>"
        if headers is None:
            headers = {"X-Robots-Tag": ""}
        return page_tracking.save_snapshot(self.store, sid or self.sid, url, status="complete",
            checked=f"2025-01-{day:02d}T00:00:00Z", payload={
                "html": html, "headers": headers, "values": page_tracking.extract(html, url, headers),
                "final_url": url, "http_status": 200, "synthetic": synthetic})

    def declaration(self, before, after, effects, *, url=None):
        return {"schema_version": "seo-publication-expectations/1", "site_id": self.sid, "pages": [
            {"url": url or self.url, "before_snapshot_id": before, "after_snapshot_id": after, "effects": effects}]}

    def test_all_surfaces_across_exact_pages_and_historical_captures(self):
        before = self.capture(self.url, "Old", 1)
        after = self.capture(self.url, "New", 2, headers={"x-robots-tag": "noindex"})
        self.capture(self.url, "Later unrelated capture", 3)
        shared_before = self.capture(self.shared, "Old", 1)
        shared_after = self.capture(self.shared, "Unexpected", 2)
        nav = {"kind": "navigation_label", "selector": 'nav a[href="/service/"]', "before": "Old", "after": "New"}
        declaration = self.declaration(before, after, [
            {"kind": "heading", "selector": "h1#service", "before": "Old", "after": "New"},
            {"kind": "breadcrumb", "selector": "#crumb > span", "before": "Old", "after": "New"},
            nav,
            {"kind": "document_title", "before": "Old | Example", "after": "New | Example"},
            {"kind": "canonical", "before": self.url, "after": self.url},
            {"kind": "robots", "before": "index, follow", "after": "index, follow"},
            {"kind": "googlebot", "before": "noarchive", "after": "noarchive"},
            {"kind": "x_robots_tag", "before": "", "after": "noindex"},
        ])
        declaration["pages"] += self.declaration(shared_before, shared_after, [nav], url=self.shared)["pages"]
        result = report(self.store, declaration)
        first, second = result["pages"]
        self.assertEqual([item["status"] for item in first["effects"]], ["matches_expectation"] * 8)
        self.assertEqual(first["before_capture"]["snapshot_id"], before)
        self.assertEqual(first["after_capture"]["snapshot_id"], after)
        self.assertRegex(first["after_capture"]["record_sha256"], "^[a-f0-9]{64}$")
        self.assertTrue(first["after_capture"]["synthetic"])
        self.assertEqual(second["effects"][0]["status"], "mismatch")
        self.assertEqual(second["effects"][0]["after"]["value"], "Unexpected")
        self.assertEqual(result["expectations_sha256"], tracking.digest(Expectations.model_validate(declaration).model_dump()))
        changed = copy.deepcopy(declaration)
        changed["pages"][0]["effects"][0]["before"] = "Incorrect baseline"
        changed_result = report(self.store, changed)
        self.assertEqual(changed_result["pages"][0]["effects"][0]["status"], "mismatch")
        self.assertNotEqual(result["expectations_sha256"], changed_result["expectations_sha256"])

    def test_missing_duplicate_and_hidden_surfaces_remain_unknown(self):
        before = self.capture(self.url, "Old", 1)
        after = self.capture(self.url, "New", 2, headers={}, metadata=(
            '<title>New</title><title>Another title</title><link rel="canonical">'
            '<meta name="robots" content="index"><meta name="ROBOTS" content="noindex">'),
            body='<h1 id="service">New</h1><h1 id="service" hidden>New</h1>'
                 '<div id="crumb"><span aria-hidden="true">New</span></div><nav>Fixture menu</nav>')
        effects = [
            {"kind": "heading", "selector": "#service", "before": "Old", "after": "New"},
            {"kind": "breadcrumb", "selector": "#crumb span", "before": "Old", "after": "New"},
            {"kind": "navigation_label", "selector": "nav a", "before": "Old", "after": "New"},
            {"kind": "document_title", "before": "Old | Example", "after": "New"},
            {"kind": "canonical", "before": self.url, "after": self.url},
            {"kind": "robots", "before": "index, follow", "after": "index"},
            {"kind": "googlebot", "before": "noarchive", "after": ""},
            {"kind": "x_robots_tag", "before": "", "after": ""},
        ]
        results = report(self.store, self.declaration(before, after, effects))["pages"][0]["effects"]
        self.assertEqual([result["status"] for result in results], ["unavailable"] * 8)
        self.assertTrue(all(result["after"]["value"] is None and result["after"]["reason"] for result in results))

    def test_wrong_reversed_unavailable_and_mixed_captures(self):
        before = self.capture(self.url, "Old", 1)
        after = self.capture(self.url, "New", 2)
        wrong_url = self.capture(self.shared, "New", 2)
        wrong_site = self.capture("https://other.example/", "New", 2, sid=self.other)
        mixed = self.capture(self.url, "New", 3, synthetic=False)
        failed = page_tracking.save_snapshot(self.store, self.sid, self.url, status="unavailable",
            checked="2025-01-04T00:00:00Z", payload={"synthetic": True})
        effects = [{"kind": "heading", "selector": "#service", "before": "Old", "after": "New"}]
        for left, right in [(before, new_id()), (before, wrong_url), (before, wrong_site), (before, failed),
                            (after, before), (before, before), (before, mixed)]:
            with self.subTest(left=left, right=right):
                page = report(self.store, self.declaration(left, right, effects))["pages"][0]
                self.assertEqual(page["effects"][0]["status"], "unavailable")
                self.assertEqual(page["after_capture"]["snapshot_id"], right)
                if right in {wrong_url, wrong_site}:
                    self.assertEqual(set(page["after_capture"]), {"snapshot_id"})

    def test_duplicate_source_attribute_cannot_pass_as_exact_canonical(self):
        before = self.capture(self.url, "Old", 1)
        after = self.capture(self.url, "New", 2, metadata=(
            f'<title>New</title><link rel="canonical" href="/other/" HREF="{self.url}">'))
        effects = [{"kind": "canonical", "before": self.url, "after": self.url}]
        result = report(self.store, self.declaration(before, after, effects))["pages"][0]["effects"][0]
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["after"]["value"])
        self.assertIn("duplicate attributes", result["after"]["reason"])

    def test_scope_must_be_explicit_and_site_local(self):
        before, after = new_id(), new_id()
        heading = {"kind": "heading", "selector": "#service", "before": "Old", "after": "New"}
        for declaration in [
            self.declaration(before, after, [], url=self.url),
            self.declaration(before, after, [heading], url="https://other.example/"),
            self.declaration(before, after, [heading, heading]),
            self.declaration(before, after, [{**heading, "selector": "["}]),
            self.declaration(before, after, [{**heading, "selector": None}]),
        ]:
            with self.subTest(declaration=declaration), self.assertRaises(ValueError):
                report(self.store, declaration)

    def test_selector_cannot_switch_between_unchanged_elements(self):
        body = '<main data-state="{}"><h1 id="old">Old</h1><h1 id="new">New</h1></main>'
        before = self.capture(self.url, "Fixture", 1, body=body.format("before"))
        after = self.capture(self.url, "Fixture", 2, body=body.format("after"))
        effect = {"kind": "heading", "selector": '[data-state="before"] #old, [data-state="after"] #new',
                  "before": "Old", "after": "New"}
        result = report(self.store, self.declaration(before, after, [effect]))["pages"][0]["effects"][0]
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["before"]["value"], "Old")
        self.assertEqual(result["after"]["value"], "New")
        self.assertIn("different element locations", result["reason"])

    def test_cli_uses_existing_database_read_only(self):
        before, after = self.capture(self.url, "Old", 1), self.capture(self.url, "New", 2)
        declaration = self.declaration(before, after, [
            {"kind": "heading", "selector": "#service", "before": "Old", "after": "New"}])
        manifest = self.root / "expectations.json"
        manifest.write_text(json.dumps(declaration), encoding="utf-8")
        original = self.store.db_path.read_bytes()
        output = io.StringIO()
        with patch("sys.argv", ["seo_agent", "--workspace", str(self.store.root), "publication-verification", str(manifest)]), \
                patch("seo_agent.protection.require_protected"), redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(output.getvalue())["pages"][0]["effects"][0]["status"], "matches_expectation")
        self.assertEqual(self.store.db_path.read_bytes(), original)
        with Store(self.store.root, read_only=True).db() as db, self.assertRaises(sqlite3.OperationalError):
            db.execute("DELETE FROM public_snapshots")
        missing = self.root / "missing"
        with self.assertRaises(ValueError):
            Store(missing, read_only=True)
        self.assertFalse(missing.exists())
