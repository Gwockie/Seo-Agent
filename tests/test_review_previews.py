import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from seo_agent.appearance import DEFAULT, app_css, capture_appearance, load_appearance, save_appearance, validate_appearance
from seo_agent.backup import _backup, _restore
from seo_agent.config import SiteConfig
from seo_agent.import_export import report_packet
from seo_agent.previews import difference, load_preview, page_document, preview_frame, save_preview, validate_preview
from seo_agent.review_format import report_html
from seo_agent.storage import Store


def fixture(sid, aid, url):
    appearance = {**DEFAULT, "site_id": sid, "url": url, "status": "captured", "captured_utc": "2026-10-08T12:00:00Z", "note": "Public fixture"}
    action = {"kind": "text", "node_id": "r2", "current": "Our service", "proposed": "Our service in City",
              "rationale": "Local intent", "confirmations": "Confirm location", "validation": "Recheck the exact heading", "rollback": "Restore Our service"}
    return {"schema": 1, "site_id": sid, "audit_id": aid, "appearance": appearance, "images": {}, "pages": [{
        "url": url, "title": "Our service", "captured_utc": "2026-10-08T12:00:00Z", "width": 1280,
        "tree": {"id": "r1", "tag": "body", "children": [{"id": "r2", "tag": "h1", "children": [{"text": "Our service"}], "style": {"color": "rgb(20, 20, 20)"}}]}, "actions": [action]}]}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "workspace")
        self.sid = self.store.save_site(SiteConfig(name="Example", url="https://example.com/", gsc_property="sc-domain:example.com"))
        self.aid = self.store.create_audit(self.sid)
        self.bundle = fixture(self.sid, self.aid, self.store.site(self.sid).url)

    def tearDown(self):
        self.tmp.cleanup()

    def test_report_formatting_keeps_source_markup_and_remote_content_inert(self):
        report = '# Review\n\n**Strong** and `code`\n\n- One\n- Two\n\n| Item | Value |\n| --- | --- |\n| x | y |\n\n<script>bad()</script> ![image](https://other.example/track) [link](javascript:bad())'
        output = report_html(report)
        soup = BeautifulSoup(output, "html.parser")
        self.assertEqual(soup.h1.get_text(), "Review")
        self.assertEqual(len(soup.select("tbody tr")), 1)
        self.assertEqual(len(soup.find_all("li")), 2)
        self.assertEqual(soup.strong.get_text(), "Strong")
        self.assertFalse(soup.find_all(["a", "img", "script", "iframe"]))
        self.assertIn("<script>bad()</script>", soup.get_text())

    def test_preview_is_offline_sandboxed_and_changes_only_exact_text(self):
        before = copy.deepcopy(self.bundle)
        bundle = validate_preview(self.bundle, self.sid, self.aid, self.store.site(self.sid))
        original = page_document(bundle, bundle["pages"][0])
        proposed = page_document(bundle, bundle["pages"][0], proposed=True)
        self.assertEqual(before, self.bundle)
        self.assertIn("<h1", original)
        self.assertNotIn("in City", original)
        self.assertIn('<mark class="added"> in City</mark>', proposed)
        inner = BeautifulSoup(proposed, "html.parser")
        self.assertIn("connect-src 'none'", inner.find("meta", attrs={"http-equiv": "Content-Security-Policy"})["content"])
        frame = BeautifulSoup(preview_frame(proposed), "html.parser").iframe
        self.assertEqual(frame["sandbox"], [])
        self.assertNotIn("allow", frame.attrs)

    def test_script_forms_css_network_and_original_links_are_discarded(self):
        tree = self.bundle["pages"][0]["tree"]
        tree["children"] += [{"tag": "script", "id": "r3", "children": [{"text": "bad()"}]},
            {"tag": "form", "id": "r4", "action": "https://evil.example", "children": []},
            {"tag": "a", "id": "r5", "href": "javascript:bad()", "onclick": "bad()", "style": {"color": "red; background:url(https://evil.example/x)", "background-image": "url(https://evil.example/x)"}, "children": [{"text": "link"}]}]
        validate_preview(self.bundle, self.sid, self.aid, self.store.site(self.sid))
        soup = BeautifulSoup(page_document(self.bundle, self.bundle["pages"][0]), "html.parser")
        self.assertFalse(soup.find_all(["script", "form"]))
        self.assertNotIn("href", soup.a.attrs)
        self.assertNotIn("onclick", soup.a.attrs)
        self.assertNotIn("evil.example", str(soup))
        self.assertNotIn("bad()", str(soup))

    def test_stale_values_cross_site_and_missing_action_details_fail_closed(self):
        for update in (lambda b: b.update(site_id="f" * 32), lambda b: b.update(audit_id="f" * 32),
                       lambda b: b["pages"][0].update(url="https://other.example/"),
                       lambda b: b["pages"][0]["actions"][0].update(current="Stale heading"),
                       lambda b: b["pages"][0]["actions"][0].update(rollback="")):
            candidate = copy.deepcopy(self.bundle)
            update(candidate)
            with self.assertRaises(ValueError):
                validate_preview(candidate, self.sid, self.aid, self.store.site(self.sid))

    def test_preview_artifact_is_immutable_and_included_in_scoped_exports(self):
        save_preview(self.store, self.sid, self.aid, self.bundle)
        with self.assertRaises(FileExistsError):
            save_preview(self.store, self.sid, self.aid, self.bundle)
        self.assertEqual(load_preview(self.store, self.sid, self.aid), self.bundle)
        other = self.store.save_site(SiteConfig(name="Other", url="https://other.example/", gsc_property="sc-domain:other.example"))
        with self.assertRaises(ValueError):
            load_preview(self.store, other, self.aid)
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(report_packet(self.store, self.sid, self.aid))) as z:
            self.assertIn("data/review-preview.json", z.namelist())

    def test_appearance_is_independent_validated_and_backed_up_with_preview(self):
        save_appearance(self.store, self.sid, self.bundle["appearance"])
        save_preview(self.store, self.sid, self.aid, self.bundle)
        other = self.store.save_site(SiteConfig(name="Other", url="https://other.example/", gsc_property="sc-domain:other.example"))
        self.assertIsNone(load_appearance(self.store, other))
        with self.assertRaises(ValueError):
            save_appearance(self.store, other, self.bundle["appearance"])
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "restored")
        self.assertEqual(load_appearance(restored, self.sid), self.bundle["appearance"])
        self.assertEqual(load_preview(restored, self.sid, self.aid), self.bundle)

    def test_css_injection_and_unreadable_color_are_rejected_or_normalized(self):
        value = copy.deepcopy(self.bundle["appearance"])
        value["heading_font"] = "x';}body{background:url(https://evil.example)}"
        with self.assertRaises(ValueError):
            validate_appearance(value, self.sid, value["url"])
        value = copy.deepcopy(self.bundle["appearance"])
        value["text"] = "#ffffff"
        safe = validate_appearance(value, self.sid, value["url"])
        self.assertEqual(safe["text"], DEFAULT["text"])
        self.assertNotIn("https://", app_css(safe))

    def test_capture_respects_robots_failure_and_synthetic_mode_never_fetches(self):
        with patch("seo_agent.appearance.PublicFetcher") as factory:
            capture_appearance(self.store, self.sid, demo=True)
            factory.assert_not_called()
        with patch("seo_agent.appearance.PublicFetcher") as factory:
            factory.return_value.get.return_value.status_code = 202
            value = capture_appearance(self.store, self.sid)
            self.assertEqual(value["status"], "unavailable")
            self.assertIn("HTTP 202", value["note"])
            self.assertEqual(factory.return_value.get.call_count, 1)
            factory.return_value.close.assert_called_once()

    def test_capture_reads_own_theme_without_fetching_external_css(self):
        def response(url, text, content_type):
            return Mock(url=url, status_code=200, text=text, content=text.encode(), headers={"Content-Type": content_type})
        root = self.store.site(self.sid).url
        def get(url, **kwargs):
            if url.endswith("robots.txt"):
                return response(url, "User-agent: *\nAllow: /", "text/plain")
            if url == root:
                return response(url, '<link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="https://evil.example/css">', "text/html")
            self.assertEqual(url, root + "theme.css")
            return response(url, 'body{background-color:#fff;color:#333;font-family:Verdana}h1{font-family:Cambria}a{color:#ac7658}', "text/css")
        with patch("seo_agent.appearance.PublicFetcher") as factory:
            factory.return_value.get.side_effect = get
            value = capture_appearance(self.store, self.sid)
        self.assertEqual(value["accent"], "#ac7658")
        self.assertEqual(value["heading_font"], "Cambria")
        self.assertEqual(value["body_font"], "Verdana")
        self.assertEqual(factory.return_value.get.call_count, 3)

    def test_word_diff_escapes_html_in_proposed_copy(self):
        soup = BeautifulSoup(difference("Our service", "Our <img src=x> service", True), "html.parser")
        self.assertFalse(soup.img)
        self.assertIn("<img src=x>", soup.get_text())

    def test_text_child_edit_preserves_surrounding_page_structure(self):
        node = self.bundle["pages"][0]["tree"]["children"][0]
        node["tag"] = "div"
        node["children"] = [{"id": "r3", "tag": "h2", "children": [{"text": "Keep heading"}]}, {"text": "Our service"}, {"id": "r4", "tag": "strong", "children": [{"text": "Keep emphasis"}]}]
        self.bundle["pages"][0]["actions"][0]["text_child"] = 1
        validate_preview(self.bundle, self.sid, self.aid, self.store.site(self.sid))
        soup = BeautifulSoup(page_document(self.bundle, self.bundle["pages"][0], proposed=True), "html.parser")
        self.assertEqual(soup.h2.get_text(), "Keep heading")
        self.assertEqual(soup.strong.get_text(), "Keep emphasis")
        self.assertIn("Our service in City", soup.get_text())

    def test_capture_revisions_preserve_earlier_page_evidence(self):
        save_preview(self.store, self.sid, self.aid, self.bundle)
        newer = copy.deepcopy(self.bundle)
        newer["pages"][0]["captured_utc"] = "2026-10-08T13:00:00Z"
        save_preview(self.store, self.sid, self.aid, newer, revision=2)
        self.assertEqual(load_preview(self.store, self.sid, self.aid), newer)
        self.assertEqual(load_preview(self.store, self.sid, self.aid, revision=1), self.bundle)
        with self.assertRaises(FileExistsError):
            save_preview(self.store, self.sid, self.aid, newer, revision=2)

    def test_frame_declares_utf8_for_both_documents(self):
        self.bundle["pages"][0]["tree"]["children"].append({"text": "We’ll review — together."})
        document = page_document(self.bundle, self.bundle["pages"][0])
        source = preview_frame(document)
        self.assertTrue(source.isascii())
        wrapper = BeautifulSoup(source, "html.parser")
        self.assertEqual(wrapper.head.find("meta")["charset"], "utf-8")
        inner = BeautifulSoup(wrapper.iframe["srcdoc"], "html.parser")
        self.assertEqual(inner.head.find("meta")["charset"], "utf-8")
        self.assertIn("We’ll review — together.", inner.get_text())

    def test_inert_inline_markup_retains_all_captured_words(self):
        node = self.bundle["pages"][0]["tree"]["children"][0]
        node["children"] = [{"text": "Our "}, {"id": "r3", "tag": "u", "children": [{"text": "service"}]}]
        soup = BeautifulSoup(page_document(self.bundle, self.bundle["pages"][0]), "html.parser")
        self.assertEqual(soup.h1.get_text(), "Our service")
        # A different element without a proposed edit retains its underline.
        self.bundle["pages"][0]["tree"]["children"].append({"id": "r4", "tag": "u", "children": [{"text": "here"}]})
        soup = BeautifulSoup(page_document(self.bundle, self.bundle["pages"][0]), "html.parser")
        self.assertEqual(soup.u.get_text(), "here")
