"""Successful ancillary resources must not conceal missing HTML evidence."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from seo_agent.config import Phrase, SiteConfig
from seo_agent.crawl import crawl
from seo_agent.demo import SyntheticService
from seo_agent.runner import AuditContext, run_snapshot
from seo_agent.storage import new_id


class CrawlCompletenessTests(unittest.TestCase):
    def test_mislabeled_html_challenge_cannot_be_exempted_as_non_html(self):
        config = SiteConfig(name="Synthetic", url="https://example.com/", gsc_property="sc-domain:example.com")
        fetcher = Mock()
        fetcher.get.return_value = Mock(status_code=200, text="User-agent: *\nAllow: /")
        body = '<html><title>Security check</title><body>Verify that you are human</body></html>'
        response = Mock(status_code=200, url=config.url + 'locations.kml', text=body, content=body.encode(), headers={"content-type": "text/xml"}, retry_after_seconds=0)
        with tempfile.TemporaryDirectory() as folder:
            with patch("seo_agent.crawl.PublicFetcher", return_value=fetcher), patch("seo_agent.crawl.discover_sitemaps", return_value=[]), patch("seo_agent.crawl.safe_get", return_value=response):
                frame = crawl(config.url, Path(folder) / "crawl.csv", config=config)
            self.assertEqual(frame.iloc[0]["status"], "content_unavailable")
            self.assertNotIn("content_kind", frame.columns)
            self.assertNotIn("title", frame.columns)

    def test_real_crawler_records_non_html_without_failing_complete_snapshot(self):
        config = SiteConfig(name="Synthetic", url="https://example.com/", gsc_property="sc-domain:example.com")
        html = '<html><head><title>Services</title></head><body><h1>Services</h1><a href="/locations.kml">Map</a></body></html>'
        xml = '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><description><![CDATA[<html>Map description</html>]]></description></Document></kml>'
        with tempfile.TemporaryDirectory() as folder:
            for index, content_type in enumerate(("text/xml; charset=UTF-8", "text/html; charset=UTF-8")):
                with self.subTest(content_type=content_type):
                    responses = {
                        config.url: Mock(status_code=200, url=config.url, text=html, content=html.encode(), headers={"content-type": "text/html"}),
                        config.url + "locations.kml": Mock(status_code=200, url=config.url + "locations.kml", text=xml, content=xml.encode(), headers={"content-type": content_type}),
                    }
                    fetcher = Mock()
                    fetcher.get.return_value = Mock(status_code=200, text="User-agent: *\nAllow: /")
                    root = Path(folder) / str(index)
                    ctx = AuditContext(new_id(), new_id(), config, root / "data", root / "reports")
                    with patch("seo_agent.crawl.PublicFetcher", return_value=fetcher), patch("seo_agent.crawl.discover_sitemaps", return_value=[]), patch("seo_agent.crawl.safe_get", side_effect=lambda url, *_: responses[url]), patch("seo_agent.crawl.time.sleep"):
                        manifest, _ = run_snapshot(ctx, SyntheticService(config))
                    frame = pd.read_csv(ctx.data_dir / "crawl.csv")
                    self.assertEqual(frame.content_kind.tolist(), ["html", "non_html"])
                    self.assertTrue(pd.isna(frame.iloc[1].title))
                    self.assertEqual(manifest["status"], "complete")
                    self.assertEqual(manifest["stages"]["crawl"]["content_page_count"], 1)
                    self.assertEqual(manifest["stages"]["crawl"]["non_html_resource_count"], 1)
                    self.assertEqual(manifest["stages"]["crawl"]["unavailable_page_count"], 0)
                    self.assertEqual(manifest["stages"]["inspection"]["result_count"], 2)

    def test_exemption_never_satisfies_missing_or_unavailable_page_content(self):
        root_url = "https://example.com/"
        page = {"url": root_url, "final_url": root_url, "status": 200, "title": "Services", "content_type": "text/html", "content_kind": "html"}
        resource = {"url": root_url + "locations.kml", "final_url": root_url + "locations.kml", "status": 200, "content_type": "text/xml", "content_kind": "non_html"}
        cases = {
            "failed_resource": ([page, {**resource, "status": 403}], None, 1),
            "challenged_html": ([page, {**resource, "status": "content_unavailable", "content_kind": "html"}], None, 1),
            "untitled_html": ([page, {**resource, "content_kind": "html", "content_type": "text/html"}], None, 1),
            "unknown_classification": ([page, {k: v for k, v in resource.items() if k != "content_kind"}], None, 1),
            "missing_priority": ([page, resource], root_url + "service/", 0),
            "non_html_priority": ([page, {**resource, "title": "Not page evidence"}], resource["url"], 1),
            "only_non_html": ([resource], None, 0),
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, (rows, priority, unavailable) in cases.items():
                with self.subTest(name=name):
                    config = SiteConfig(name="Synthetic", url=root_url, gsc_property="sc-domain:example.com", phrases=[Phrase(phrase="sample service", group="service", landing_page=priority)] if priority else [])
                    ctx = AuditContext(new_id(), new_id(), config, Path(folder) / name / "data", Path(folder) / name / "reports")
                    def crawler(url, path, **kwargs):
                        frame = pd.DataFrame(rows)
                        frame.to_csv(path, index=False)
                        return frame
                    manifest, _ = run_snapshot(ctx, SyntheticService(config), crawl_fn=crawler)
                    self.assertEqual(manifest["status"], "partial")
                    self.assertEqual(manifest["stages"]["crawl"]["status"], "partial")
                    self.assertEqual(manifest["stages"]["crawl"]["unavailable_page_count"], unavailable)
                    self.assertEqual(manifest["stages"]["gsc_current"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
