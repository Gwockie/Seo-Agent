"""Seed an isolated, synthetic UI demonstration; never collect or connect."""
import argparse
from pathlib import Path
from seo_agent.config import SiteConfig, Phrase
from seo_agent.storage import Store, new_id, utc_now
from seo_agent import tracking as t, page_tracking as p


def seed(root):
    store = Store(root)
    if store.sites():
        raise ValueError("Use an empty dedicated demonstration workspace")
    url = "https://synthetic-electrician.example/"
    sid = store.save_site(SiteConfig(name="Synthetic revision demo", url=url, gsc_property=url, location="Reading",
        service_groups={"wiring": ["Wiring services"]}, confirmed_facts={"fixture": "Synthetic business; no real owner/account"},
        phrases=[Phrase(phrase="wiring Reading", landing_page=url)]))
    aid = store.create_audit(sid)
    store.audit_file(sid, aid, "data", "crawl.csv").write_text(f"url,title\n{url},Electrical services\n", encoding="utf-8")
    store.audit_file(sid, aid, "data", "gsc_query_page.csv").write_text(f"query,page,impressions,clicks,position\nwiring Reading,{url},120,3,8\n", encoding="utf-8")
    store.save_findings(sid, aid, [{"site_id": sid, "audit_id": aid, "rule": "relevance", "rule_version": "1.0", "industry": "general", "profile_version": "1.0", "priority": "P1", "category": "Service relevance", "url": url, "query": "wiring Reading",
        "detail": "Synthetic title omits the configured wiring offering/location", "proposed_action": "Wiring Reading | Synthetic business", "measurement": "Compare finalized affected-query/page impressions and CTR after reported publication",
        "confirmations": ["Owner confirms wiring service and Reading service area"], "evidence": [{"file": "crawl.csv", "row": 2}, {"file": "gsc_query_page.csv", "row": 2}]}])
    rid = store.findings(sid, aid)[0]["id"]
    html = '<html><head><title>Electrical services</title></head><body><h1>Synthetic electrical services</h1><p>Wiring service demonstration</p></body></html>'
    p.save_snapshot(store, sid, url, status="complete", audit_id=aid, payload={"html": html, "headers": {}, "http_status": 200, "final_url": url, "values": p.extract(html, url, {}), "synthetic": True})
    t.save_action(store, sid, aid, {"action_id": new_id(), "recommendation_id": rid, "url": url, "action_kind": "title", "current": "Electrical services", "proposed": "Wiring Reading | Synthetic business", "current_source": "Synthetic fixture capture", "capture_time_utc": utc_now(),
        "rationale": "Clarify offering and service area", "expected_effect": "Relevance and clarity hypothesis", "primary_measure": "Page impressions", "measurement": "Compare finalized affected-query/page windows after reported publication", "confirmations": [{"item": "Owner confirms wiring service and Reading service area", "status": "pending", "source": None}],
        "validation": "Inspect exact title and canonical/indexing state", "rollback": "Restore Electrical services from saved baseline", "evidence": [{"file": "crawl.csv", "row": 2, "revision": None, "node_id": None}]})
    p.save_settings(store, sid, {"enabled": False})
    store.finish_audit(sid, aid, "complete", {"synthetic": True})
    print("Synthetic revision demo ready; no jobs or website writes enabled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    seed(parser.parse_args().workspace)
