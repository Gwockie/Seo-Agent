"""Explicitly synthetic acceptance fixtures; never reads or connects to client sites."""
import pandas as pd

from .config import SiteConfig, Phrase
from .storage import Store


class Response:
    def __init__(self, data):
        self.data = data
    def execute(self):
        return self.data


class SyntheticService:
    def __init__(self, config):
        self.config = config
    def searchanalytics(self):
        return self
    def query(self, *, siteUrl, body):
        assert siteUrl == self.config.gsc_property
        dims = body["dimensions"]
        if body["startRow"]:
            return Response({"rows": []})
        phrase = self.config.phrases[0].phrase if self.config.phrases else "sample service"
        values = {"query": phrase, "page": self.config.url, "device": "DESKTOP", "country": "usa", "date": body["startDate"]}
        return Response({"rows": [{"keys": [values[d] for d in dims], "clicks": 2, "impressions": 150, "ctr": 2/150, "position": 7}]})
    def sitemaps(self):
        return self
    def list(self, **kwargs):
        return Response({"sitemap": []})
    def urlInspection(self):
        return self
    def index(self):
        return self
    def inspect(self, body):
        return Response({"inspectionResult": {"indexStatusResult": {"verdict": "FAIL", "coverageState": "Excluded by noindex", "indexingState": "BLOCKED_BY_META_TAG", "googleCanonical": body["inspectionUrl"], "userCanonical": body["inspectionUrl"]}}})


def synthetic_crawl(root, out_csv, *, config, **_):
    landing = config.phrases[0].landing_page if config.phrases and config.phrases[0].landing_page else root
    df = pd.DataFrame([{"url": landing, "final_url": landing, "status": 200, "content_type": "text/html", "title": "Services", "h1": "Welcome", "h2": "", "robots_meta": "noindex", "canonical": landing, "internal_link_urls": "[]"}])
    df.to_csv(out_csv, index=False)
    return df


def seed_demo(store: Store):
    if store.sites():
        return
    for name, host, industry, phrase, terms, location, fact in [
        ("Demo psychology A", "psychology-a.example", "psychology", "ADHD testing Paoli", ["ADHD testing", "ADHD assessment"], "Paoli", "Synthetic adult assessment service"),
        ("Demo psychology B", "psychology-b.example", "psychology", "therapy Exton", ["therapy", "therapist"], "Exton", "Synthetic therapy service"),
        ("Demo electrician", "electrician.example", "general", "electrician Reading", ["electrician", "wiring"], "Reading", "Synthetic electrical service"),
    ]:
        cid = store.add_connection(name + " synthetic account reference")
        root = "https://" + host + "/"
        config = SiteConfig(name=name, url=root, gsc_property=root, industry=industry, connection_id=cid, location=location,
            confirmed_facts={"fixture": fact}, service_groups={"primary": terms},
            phrases=[Phrase(phrase=phrase, group="primary", landing_page=root + "service/", priority=5)])
        store.save_site(config)
