import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from seo_agent.backup import _backup, _restore
from seo_agent.config import SiteConfig, Phrase, RuleOverride
from seo_agent.learning import create_plan, plans, link_change, compare, save_review, reviews
from seo_agent.setup_fields import service_rows, services_from_rows, facts_from_rows, rule_rows, overrides_from_rows, phrase_rows, phrases_from_rows
from seo_agent.storage import Store


class GuidedFieldsTests(unittest.TestCase):
    def test_service_and_fact_rows_preserve_unicode_empty_groups_and_literal_text(self):
        groups = {"group": ["Service, including variant", "café & repair"], "empty": []}
        self.assertEqual(services_from_rows(service_rows(groups)), groups)
        facts = {"address": "  Original wording & punctuation ’  "}
        self.assertEqual(facts_from_rows([{"Fact": k, "Confirmed value": v} for k, v in facts.items()]), facts)
        self.assertEqual(facts_from_rows([{"Fact": "", "Confirmed value": ""}]), {})
        for rows in ([{"Fact": "address", "Confirmed value": ""}], [{"Fact": "x", "Confirmed value": "y"}] * 2):
            with self.assertRaises(ValueError):
                facts_from_rows(rows)
        with self.assertRaises(ValueError):
            services_from_rows([{"Service group": "", "Related search term": "service"}])
        with self.assertRaises(ValueError):
            services_from_rows(service_rows({"g": ["same", "same"]}))

    def test_rule_rows_keep_overrides_and_clinical_guard(self):
        config = SiteConfig(name="Example", url="https://example.com/", gsc_property="sc-domain:example.com", industry="psychology", overrides={"ctr": RuleOverride(min_impressions=250, ctr_threshold=.025), "alignment": RuleOverride(enabled=False)})
        self.assertEqual(overrides_from_rows(rule_rows(config), config), config.overrides)
        for rule, field, value in (("clinical_review", "Enabled", False), ("ctr", "Minimum impressions", 250.5), ("canonical", "CTR threshold (%)", 3)):
            rows = copy.deepcopy(rule_rows(config))
            next(r for r in rows if r["Rule"] == rule)[field] = value
            with self.assertRaises(ValueError):
                config.model_validate({**config.model_dump(), "overrides": {k: v.model_dump(exclude_none=True) for k, v in overrides_from_rows(rows, config).items()}})

    def test_phrase_table_round_trip_and_new_rows(self):
        phrases = [Phrase(phrase="café repair", related_terms=["Original, wording", "second term"], priority=4, active=False)]
        self.assertEqual(phrases_from_rows(phrase_rows(phrases)), phrases)
        row = {"phrase": "new service", "group": None, "related_terms": None, "location": None, "landing_page": None, "priority": None, "active": None}
        self.assertEqual(phrases_from_rows([row])[0], Phrase(phrase="new service"))


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "workspace")
        self.url = "https://example.com/service/"
        self.sid = self.store.save_site(SiteConfig(name="Example", url="https://example.com/", gsc_property="sc-domain:example.com", brand_aliases=["Example"], phrases=[Phrase(phrase="service Town", group="primary", landing_page=self.url)], service_groups={"primary": ["service"]}))
        self.other = self.store.save_site(SiteConfig(name="Other", url="https://other.example/", gsc_property="sc-domain:other.example"))
        self.before = self.audit("2026-01-01", "2026-01-28", 2, 200, 9.5)
        self.after = self.audit("2026-02-02", "2026-03-01", 4, 300, 8.)
        self.value = {"title": "Clarify heading", "why": "Captured heading is vague", "expected_effect": "Relevant visibility may improve", "measurement": "Compare exact page in equal final windows", "metric": "Page impressions", "url": self.url, "current": "Service", "proposed": "Service in Town"}
        self.pid = create_plan(self.store, self.sid, self.before, self.value)

    def tearDown(self):
        self.tmp.cleanup()

    def audit(self, start, end, clicks, impressions, position, *, sid=None):
        sid = sid or self.sid
        aid = self.store.create_audit(sid)
        pd.DataFrame([{"page": self.url, "clicks": clicks, "impressions": impressions, "position": position}]).to_csv(self.store.audit_file(sid, aid, "data", "gsc_pages.csv"), index=False)
        pd.DataFrame([{"query": "service Town", "clicks": clicks, "impressions": impressions, "position": position}, {"query": "Example service", "clicks": 90, "impressions": 9999, "position": 1}]).to_csv(self.store.audit_file(sid, aid, "data", "gsc_queries.csv"), index=False)
        self.store.finish_audit(sid, aid, "partial", {"windows": {"current": {"start": start, "end": end}, "timezone": "America/Los_Angeles"}, "stages": {"gsc_current": {"status": "complete", "metadata": {"start": start, "end": end, "data_state": "final", "search_type": "web", "timezone": "America/Los_Angeles"}}, "crawl": {"status": "failed"}}})
        return aid

    def publish_record(self, *, when="2026-02-01", url=None):
        cid = self.store.add_change(self.sid, date=when, action="User-reported heading edit", url=self.url if url is None else url, evidence="Manual verification", verification="user-reported; unverified")
        link_change(self.store, self.sid, self.pid, cid)
        return cid

    def test_saved_plan_reopens_and_unpublished_preview_has_no_result(self):
        self.assertEqual(compare(self.store, self.sid, self.pid, self.after)["status"], "not ready")
        reopened = Store(self.store.root)
        self.assertEqual(plans(reopened, self.sid)[0]["payload"], self.value)
        rid = save_review(reopened, self.sid, self.pid, self.after, "Still waiting for publication; no observed result")
        self.assertEqual(reviews(self.store, self.sid, self.pid)[0]["id"], rid)
        self.assertEqual(self.store.changes(self.sid), [])

    def test_comparison_uses_page_rows_not_property_totals_and_retains_other_changes(self):
        self.publish_record()
        self.store.add_change(self.sid, date="2026-02-05", action="Other change could affect results")
        result = compare(self.store, self.sid, self.pid, self.after)
        self.assertEqual(result["status"], "comparable")
        self.assertEqual(result["baseline"]["value"], 200)
        self.assertEqual(result["followup"]["value"], 300)
        self.assertEqual(result["difference"], 100)
        self.assertEqual(result["baseline"]["aggregation"], "byPage")
        self.assertEqual(len(result["other_changes"]), 1)
        self.assertIn("association", result["reason"])

    def test_cross_site_plan_audit_and_change_are_rejected(self):
        other_aid = self.audit("2026-02-02", "2026-03-01", 4, 300, 8, sid=self.other)
        cid = self.store.add_change(self.other, date="2026-02-01", action="Other site's change")
        for call in (lambda: plans(self.store, "f" * 32), lambda: compare(self.store, self.other, self.pid, other_aid), lambda: compare(self.store, self.sid, self.pid, other_aid), lambda: create_plan(self.store, self.other, self.before, self.value), lambda: link_change(self.store, self.sid, self.pid, cid), lambda: create_plan(self.store, self.sid, self.before, {**self.value, "url": "https://other.example/"})):
            with self.assertRaises(ValueError):
                call()
        with self.assertRaises(ValueError):
            self.publish_record(url="")

    def test_overlapping_unequal_nonfinal_partial_and_missing_rows_are_unknown(self):
        self.publish_record()
        for start, end in (("2026-01-10", "2026-02-06"), ("2026-02-02", "2026-03-02")):
            aid = self.audit(start, end, 2, 200, 9)
            self.assertEqual(compare(self.store, self.sid, self.pid, aid)["status"], "unavailable")
        raw = json.loads(self.store.audit(self.sid, self.after)["manifest"])
        for update in ({"status": "partial"}, {"metadata": {**raw["stages"]["gsc_current"]["metadata"], "data_state": "all"}}):
            changed = copy.deepcopy(raw)
            changed["stages"]["gsc_current"].update(update)
            with self.store.db() as db:
                db.execute("UPDATE audits SET manifest=? WHERE id=?", (json.dumps(changed), self.after))
            self.assertEqual(compare(self.store, self.sid, self.pid, self.after)["status"], "unavailable")
        with self.store.db() as db:
            db.execute("UPDATE audits SET manifest=? WHERE id=?", (json.dumps(raw), self.after))
        pd.DataFrame(columns=["page", "clicks", "impressions", "position"]).to_csv(self.store.audit_file(self.sid, self.after, "data", "gsc_pages.csv"), index=False)
        result = compare(self.store, self.sid, self.pid, self.after)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("not zero", result["reason"])

    def test_ctr_and_nonbranded_definitions_are_consistent_between_audits(self):
        for metric, expected in (("Page CTR", 4 / 300 - 2 / 200), ("Target non-branded impressions", 100)):
            self.pid = create_plan(self.store, self.sid, self.before, {**self.value, "metric": metric})
            self.publish_record()
            result = compare(self.store, self.sid, self.pid, self.after)
            self.assertAlmostEqual(result["difference"], expected)
        config = self.store.site(self.sid)
        config.brand_aliases = ["service"]
        self.store.save_site(config, self.sid)
        self.assertEqual(compare(self.store, self.sid, self.pid, self.after)["difference"], 100)

    def test_reviews_append_and_back_up_without_overwriting_audit_evidence(self):
        self.publish_record()
        path = self.store.audit_file(self.sid, self.before, "data", "gsc_pages.csv")
        original = path.read_bytes()
        save_review(self.store, self.sid, self.pid, self.after, "Traffic increased; cause remains uncertain")
        save_review(self.store, self.sid, self.pid, self.after, "Another edit is a possible explanation")
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "restored")
        self.assertEqual(len(reviews(restored, self.sid, self.pid)), 2)
        self.assertEqual(compare(restored, self.sid, self.pid, self.after)["difference"], 100)
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(ValueError):
            self.publish_record()

    def test_old_backup_remains_restorable(self):
        # A real old schema contains neither journal table. Restore adds empty ones.
        from seo_agent.storage import TRACKING_TABLES, SCHEDULING_TABLES, EVALUATION_TABLES
        with self.store.db() as db:
            for table in TRACKING_TABLES | SCHEDULING_TABLES | EVALUATION_TABLES:
                db.execute("DROP TABLE " + table)
            db.execute("DROP TABLE result_reviews")
            db.execute("DROP TABLE change_plans")
            db.execute("PRAGMA user_version=1")
        archive = self.root / "old-backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "old-restored")
        self.assertEqual(plans(restored, self.sid), [])
        self.assertEqual(len(restored.audits(self.sid)), 2)
