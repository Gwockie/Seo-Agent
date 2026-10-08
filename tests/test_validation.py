import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests

from seo_agent.analysis import build_opportunities, write_markdown_summary
from seo_agent.crawl import analyze_html, get_robot_parser, safe_get, sitemap_urls
from seo_agent.gsc import rows_to_df


class ValidationTests(unittest.TestCase):
    def test_sitemap_excludes_image_locations(self):
        rp = RobotFileParser()
        rp.parse([])
        session = Mock()
        session.get.return_value = Mock(status_code=200, ok=True, headers={"content-type": "application/xml"}, content=b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"><url><loc>https://example.com/page/</loc><image:image><image:loc>https://example.com/image.jpg</image:loc></image:image></url></urlset>')
        urls = sitemap_urls("https://example.com/sitemap.xml", session, root_url="https://example.com/", rp=rp)
        self.assertEqual(urls, {"https://example.com/page/"})

    def test_empty_export_can_be_read_and_summarized(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows_to_df([], ["query", "page"]).to_csv(root / "gsc_query_page.csv", index=False)
            self.assertTrue(build_opportunities(root).empty)
            write_markdown_summary(root, root / "reports")
            self.assertIn("No Search Console", (root / "reports/snapshot.md").read_text())

    def test_robots_failure_does_not_allow_crawl(self):
        for status in (201, 202, 204, 206, 403, 429, 500):
            session = Mock()
            session.get.return_value = Mock(ok=status < 400, status_code=status, text="CAPTCHA_REQUIRED")
            with self.assertRaises(ValueError):
                get_robot_parser("https://example.com/", session)
        session.get.side_effect = requests.ConnectionError()
        with self.assertRaises(ValueError):
            get_robot_parser("https://example.com/", session)

    def test_missing_robots_allows_public_pages(self):
        session = Mock()
        session.get.return_value = Mock(ok=False, status_code=404)
        self.assertTrue(get_robot_parser("https://example.com/", session).can_fetch("audit", "https://example.com/"))

    def test_redirect_checked_before_request(self):
        rp = RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /private"])
        for target in ("/private", "https://other.example/"):
            session = Mock()
            session.get.return_value = Mock(status_code=302, headers={"Location": target})
            with self.assertRaises(ValueError):
                safe_get("https://example.com/", "https://example.com/", session, rp)
            self.assertEqual(session.get.call_count, 1)

    def test_html_extracts_audit_evidence(self):
        html = '<title>ADHD Assessment Paoli</title><h1>ADHD assessment</h1><link rel="canonical" href="/assessment/"><script type="application/ld+json">{"@type":"WebPage"}</script><a href="/therapy/">Therapy</a>'
        row, links = analyze_html("https://example.com/", "https://example.com/", 200, html)
        self.assertEqual(row["schema_types"], "WebPage")
        self.assertTrue(row["text_mentions_paoli"])
        self.assertEqual(row["canonical"], "https://example.com/assessment/")
        self.assertIn("https://example.com/therapy/", links)


if __name__ == "__main__":
    unittest.main()
