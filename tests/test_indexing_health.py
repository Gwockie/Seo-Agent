import copy
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
from unittest.mock import Mock, patch

from seo_agent.indexing_health import BASE, SCOPE, TARGETS, collect_live, evaluate_record, evaluate_snapshot, main, sitemap_contract


def healthy(url):
    return {"inspectionResult": {"indexStatusResult": {
        "verdict": "PASS", "coverageState": "Submitted and indexed",
        "robotsTxtState": "ALLOWED", "indexingState": "INDEXING_ALLOWED",
        "pageFetchState": "SUCCESSFUL", "lastCrawlTime": "2026-10-02T09:21:53Z",
        "googleCanonical": url, "userCanonical": url,
    }}}


def make_xml(folder, urls):
    folder.mkdir(exist_ok=True)
    (folder / "sitemap_index.xml").write_text(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>'
        + BASE + 'page-sitemap.xml</loc></sitemap></sitemapindex>', encoding="utf-8")
    (folder / "page-sitemap.xml").write_text(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + ''.join('<url><loc>' + u + '</loc><lastmod>2026-10-01</lastmod></url>' for u in urls)
        + '</urlset>', encoding="utf-8")


class IndexingHealthTests(unittest.TestCase):
    def test_unknown_does_not_pass_as_healthy_live_access(self):
        result = evaluate_record(TARGETS[0], {"inspectionResult": {"indexStatusResult": {
            "verdict": "NEUTRAL", "coverageState": "URL is unknown to Google",
        }, "richResultsResult": {"verdict": "PASS"}}})
        self.assertEqual(result["stage"], "unknown")
        self.assertFalse(result["healthy"])

    def test_indexed_with_matching_canonical_and_crawl_passes(self):
        self.assertTrue(evaluate_record(TARGETS[0], healthy(TARGETS[0]))["healthy"])

    def test_canonical_drift_is_a_regression(self):
        records = [{"url": u, "response": healthy(u)} for u in TARGETS]
        old = evaluate_snapshot(records, TARGETS)
        current = copy.deepcopy(records)
        current[0]["response"]["inspectionResult"]["indexStatusResult"]["googleCanonical"] = BASE
        result = evaluate_snapshot(current, TARGETS, old)
        self.assertFalse(result["healthy"])
        self.assertEqual(result["pages"][0]["stage"], "canonical_conflict")
        self.assertTrue(result["pages"][0]["regression"])

    def test_discovered_and_crawled_excluded_are_distinct(self):
        discovered = {"inspectionResult": {"indexStatusResult": {"verdict": "NEUTRAL", "coverageState": "Discovered - currently not indexed"}}}
        self.assertEqual(evaluate_record(TARGETS[0], discovered)["stage"], "discovered_uncrawled")
        discovered["inspectionResult"]["indexStatusResult"].update(coverageState="Crawled - currently not indexed", lastCrawlTime="2026-10-06T12:00:00Z")
        self.assertEqual(evaluate_record(TARGETS[0], discovered)["stage"], "crawled_excluded")

    def test_aggregate_pass_without_ordinary_fields_cannot_confirm_recovery(self):
        response = healthy(TARGETS[0])
        del response["inspectionResult"]["indexStatusResult"]["lastCrawlTime"]
        self.assertFalse(evaluate_record(TARGETS[0], response)["healthy"])

    def test_invalid_or_future_crawl_timestamp_is_not_recovery(self):
        for timestamp in ("N/A", "2099-01-01T00:00:00Z", "2026-01-01T00:00:00"):
            response = healthy(TARGETS[0])
            response["inspectionResult"]["indexStatusResult"]["lastCrawlTime"] = timestamp
            self.assertFalse(evaluate_record(TARGETS[0], response)["healthy"])

    def test_missing_target_is_failure_not_silent_skip(self):
        result = evaluate_snapshot([], TARGETS)
        self.assertFalse(result["healthy"])
        self.assertEqual(len(result["pages"]), 3)
        self.assertTrue(all(p["stage"] == "missing_evidence" for p in result["pages"]))

    def test_xml_missing_service_challenge_and_duplicate_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_xml(folder, TARGETS[:1])
            self.assertFalse(sitemap_contract(folder, TARGETS)["healthy"])
            make_xml(folder, TARGETS + TARGETS[:1])
            self.assertFalse(sitemap_contract(folder, TARGETS)["healthy"])
            (folder / "page-sitemap.xml").write_text('<html><body>captcha</body></html>')
            self.assertFalse(sitemap_contract(folder, TARGETS)["healthy"])

    def test_child_locations_cannot_read_outside_xml_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_xml(folder, TARGETS)
            index = folder / "sitemap_index.xml"
            read_bytes = Path.read_bytes
            for path in ("..\\private.xml", "C:private.xml", "../private.xml"):
                with self.subTest(path=path):
                    index.write_text('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>' + BASE + path + '</loc></sitemap></sitemapindex>')
                    with patch.object(Path, "read_bytes", autospec=True, side_effect=read_bytes) as reads:
                        result = sitemap_contract(folder, TARGETS)
                    self.assertFalse(result["healthy"])
                    self.assertTrue(all(call.args[0] == index for call in reads.call_args_list))
            make_xml(folder, TARGETS)
            resolve = Path.resolve
            child = folder / "page-sitemap.xml"
            def outside_child(path):
                return folder.parent / "private.xml" if path == child else resolve(path)
            with patch.object(Path, "resolve", autospec=True, side_effect=outside_child), patch.object(Path, "read_bytes", autospec=True, side_effect=read_bytes) as reads:
                result = sitemap_contract(folder, TARGETS)
            self.assertFalse(result["healthy"])
            self.assertTrue(all(call.args[0] == index for call in reads.call_args_list))

    def test_lastmod_only_change_preserves_contract_but_new_url_requires_review(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_xml(folder, TARGETS)
            old = sitemap_contract(folder, TARGETS)
            path = folder / "page-sitemap.xml"
            path.write_text(path.read_text().replace("2026-10-01", "2026-10-02"))
            self.assertTrue(sitemap_contract(folder, TARGETS, old)["healthy"])
            make_xml(folder, TARGETS + [BASE + "new-page/"])
            self.assertFalse(sitemap_contract(folder, TARGETS, old)["healthy"])

    def test_replay_is_labelled_historical_and_cannot_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw.json"
            raw.write_text(json.dumps([{"url": u, "response": healthy(u)} for u in TARGETS]))
            out = root / "out"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--replay", str(raw), "--out", str(out)]), 0)
            self.assertEqual(json.loads((out / "health.json").read_text())["evidence_mode"], "historical_replay")
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                main(["--replay", str(raw), "--out", str(out)])

    def test_live_collect_has_only_bounded_read_methods(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            secrets = root / "secrets"
            secrets.mkdir()
            (secrets / "token.json").write_text(json.dumps({"scopes": [SCOPE], "token": "synthetic", "refresh_token": "synthetic", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "synthetic", "client_secret": "synthetic", "expiry": "2099-01-01T00:00:00Z"}))
            svc = Mock()
            svc.sites().list().execute.return_value = {"siteEntry": [{"siteUrl": BASE}]}
            svc.urlInspection().index().inspect().execute.return_value = healthy(TARGETS[0])
            with patch("seo_agent.gsc.services", return_value=svc):
                records, meta = collect_live(root, BASE, TARGETS)
            self.assertEqual(len(records), 3)
            self.assertEqual(svc.urlInspection().index().inspect.call_count, 4)  # fixture setup plus 3 requests
            self.assertEqual(svc.sitemaps().list.call_count, 2)
            svc.sitemaps().submit.assert_not_called()
            svc.sitemaps().delete.assert_not_called()
            svc.urlInspection().index().inspect.assert_called_with(body={"inspectionUrl": TARGETS[-1], "siteUrl": BASE, "languageCode": "en-US"})

    def test_missing_or_broadened_token_never_initiates_authentication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("seo_agent.gsc.services") as factory:
                with self.assertRaises(ValueError):
                    collect_live(root, BASE, TARGETS)
                (root / "secrets").mkdir()
                (root / "secrets/token.json").write_text(json.dumps({"scopes": [SCOPE, "https://www.googleapis.com/auth/webmasters"]}))
                with self.assertRaises(ValueError):
                    collect_live(root, BASE, TARGETS)
                factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
