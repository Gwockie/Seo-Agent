import copy
import io
import json
import tempfile
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from seo_agent import tracking as t, page_tracking as p, trends
from seo_agent.backup import _backup, _restore
from seo_agent.config import SiteConfig
from seo_agent.import_export import safe_csv, report_packet
from seo_agent.runner import run_lock, GLOBAL_LOCK, Jobs
from seo_agent.storage import Store, new_id, utc_now


class TrackingFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "workspace")
        self.sid = self.store.save_site(SiteConfig(name="Synthetic", url="https://example.com/", gsc_property="sc-domain:example.com"))
        self.other = self.store.save_site(SiteConfig(name="Other", url="https://other.example/", gsc_property="sc-domain:other.example"))
        self.aid = self.store.create_audit(self.sid)
        self.store.audit_file(self.sid, self.aid, "data", "crawl.csv").write_text("url,title\nhttps://example.com/,Before\n", encoding="utf-8")
        self.value = {"action_id": new_id(), "url": "https://example.com/", "action_kind": "title", "current": "Before", "proposed": "After",
            "current_source": "Synthetic capture", "capture_time_utc": utc_now(), "rationale": "Clearer service wording", "expected_effect": "Relevant visibility hypothesis",
            "primary_measure": "Page impressions", "measurement": "Equal final windows", "confirmations": [{"item": "Service is actually offered", "status": "confirmed", "source": "Synthetic owner assertion"}],
            "validation": "Check title and visible context", "rollback": "Restore Before", "evidence": [{"file": "crawl.csv", "row": 2, "revision": None, "node_id": None}]}
        self.handoff = {"schema": "seo-change-handoff/1", "kind": "proposal", "site_id": self.sid, "audit_id": self.aid, "prepared_utc": utc_now(), "actions": [self.value]}

    def tearDown(self):
        self.tmp.cleanup()

    def import_action(self):
        return t.import_handoff(self.store, self.sid, self.aid, t.canonical(self.handoff).encode())

    def snapshot(self, title="Before", *, checked=None, aid=None, url=None, extra=""):
        url = url or self.value["url"]
        html = f"<html><head><title>{title}</title><link rel='canonical' href='{url}'></head><body><h1>Service</h1><p>Price $42 on October 8</p>{extra}<a href='/service/'>Service link</a></body></html>"
        headers = {"content-type": "text/html"}
        return p.save_snapshot(self.store, self.sid, url, status="complete", checked=checked, audit_id=aid, payload={"html": html, "values": p.extract(html, url, headers), "headers": headers, "http_status": 200, "final_url": url, "synthetic": True})

    def approval(self):
        self.import_action()
        self.snapshot()
        bid = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        apid = t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=True, statement="I approve this exact publication batch", confirmation_source="Synthetic owner confirmed facts")
        return bid, apid

    def receipt(self, *, outcome="attempted", environment="local", approval=None, actual=None, attempt=None):
        return {"schema": "seo-implementation-receipt/1", "receipt_id": new_id(), "site_id": self.sid, "action_id": self.value["action_id"], "revision": 1,
            "attempt_id": attempt or new_id(), "environment": environment, "outcome": outcome, "occurred_utc": utc_now(), "current": "Before", "proposed": "After", "actual": actual,
            "approval_id": approval, "source": "Synthetic execution log", "verification": "", "corrects": None}


class TrackingTests(TrackingFixture, unittest.TestCase):
    def test_handoff_idempotence_literal_input_and_no_approval(self):
        self.value["rationale"] = "<script>alert(1)</script> =SUM(A1) is inert data"
        self.handoff["actions"] = [self.value]
        first = self.import_action()
        self.assertEqual(first, self.import_action())
        self.assertEqual(len(t.actions(Store(self.store.root), self.sid)), 1)
        self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
        self.assertEqual(t.rows(self.store, "implementation_receipts", self.sid), [])
        self.assertEqual(t.actions(self.store, self.sid)[0]["payload"]["rationale"], self.value["rationale"])

    def test_handoff_rejects_approval_claim_site_traversal_bad_rows_and_times(self):
        changes = [lambda h: h.update(approved=True), lambda h: h.update(site_id=self.other), lambda h: h.update(prepared_utc="2099-01-01T00:00:00Z"),
            lambda h: h["actions"][0].update(capture_time_utc="2026-01-01"), lambda h: h["actions"][0]["evidence"][0].update(file="../crawl.csv"),
            lambda h: h["actions"][0]["evidence"][0].update(row=99), lambda h: h["actions"][0].update(url="https://other.example/"),
            lambda h: h["actions"][0].update(approval_reference="agent said yes")]
        for change in changes:
            h = copy.deepcopy(self.handoff)
            change(h)
            with self.subTest(h=h), self.assertRaises(ValueError):
                t.import_handoff(self.store, self.sid, self.aid, t.canonical(h).encode())
        self.assertEqual(t.actions(self.store, self.sid), [])
        with self.assertRaises(ValueError):
            t.load_document(b'{"schema":"a","schema":"b"}')

    def test_markdown_and_missing_current_remain_planning_only(self):
        self.handoff["actions"][0].update(current=None, capture_time_utc=None, confirmations=[])
        raw = ("# Proposal\n```json\n" + t.canonical(self.handoff) + "\n```\n").encode()
        t.import_handoff(self.store, self.sid, self.aid, raw)
        r = t.actions(self.store, self.sid)[0]
        self.assertFalse(t.readiness(self.store, self.sid, r)["ready"])
        with self.assertRaises(ValueError):
            t.freeze_batch(self.store, self.sid, [(r["action_id"], 1)])

    def test_frozen_batch_requires_human_and_never_executes(self):
        self.import_action()
        self.snapshot()
        bid = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        for clicked, statement in ((False, "I approve this exact publication batch"), (True, "Agent approved")):
            with self.assertRaises(ValueError):
                t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=clicked, statement=statement, confirmation_source="assertion")
        self.assertEqual(t.rows(self.store, "human_approvals", self.sid), [])
        approval = t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=True, statement="I approve this exact publication batch", confirmation_source="Human facts confirmed")
        self.assertTrue(approval)
        self.assertEqual(t.rows(self.store, "implementation_receipts", self.sid), [])

    def test_revision_and_stale_value_invalidate_only_affected_action(self):
        bid, approval = self.approval()
        before = t.batch(self.store, self.sid, bid)
        changed = {**self.value, "proposed": "A newer title"}
        t.save_action(self.store, self.sid, self.aid, changed, revision=2)
        self.assertEqual(t.batch_validity(self.store, self.sid, bid), [self.value["action_id"]])
        self.assertEqual(t.batch(self.store, self.sid, bid), before)
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, self.receipt(environment="production", approval=approval))
        self.assertEqual(t.action(self.store, self.sid, self.value["action_id"], 1)["payload"], self.value)

    def test_public_value_change_invalidates_approval(self):
        bid, approval = self.approval()
        self.snapshot("Outside title")
        self.assertTrue(t.batch_validity(self.store, self.sid, bid))
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, self.receipt(environment="production", approval=approval))
        self.snapshot("Before")
        self.assertTrue(t.batch_validity(self.store, self.sid, bid), "Returning to the old value must not restore invalidated approval")

    def test_changed_action_does_not_invalidate_another_approved_action(self):
        self.import_action()
        self.snapshot()
        second = {**self.value, "action_id": new_id(), "action_kind": "text", "current": "Price $42 on October 8", "proposed": "Confirmed price $42 on October 8"}
        t.save_action(self.store, self.sid, self.aid, second)
        bid = t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1), (second["action_id"], 1)])
        approval = t.approve_from_human_ui(self.store, self.sid, bid, human_clicked=True, statement="I approve this exact publication batch", confirmation_source="Synthetic human confirmed both")
        t.save_action(self.store, self.sid, self.aid, {**self.value, "proposed": "Changed title"}, revision=2)
        self.assertEqual(t.batch_validity(self.store, self.sid, bid), [self.value["action_id"]])
        receipt = {**self.receipt(environment="production", approval=approval), "action_id": second["action_id"], "current": second["current"], "proposed": second["proposed"]}
        t.record_receipt(self.store, self.sid, receipt)
        t.record_receipt(self.store, self.sid, {**receipt, "receipt_id": new_id(), "occurred_utc": utc_now(), "outcome": "partial", "actual": "An intermediate exact value"})
        self.assertEqual(len(t.rows(self.store, "implementation_receipts", self.sid)), 2)
        self.assertEqual(len(t.rows(self.store, "approval_invalidations", self.sid)), 1)

    def test_pending_facts_old_capture_and_overlapping_actions_cannot_freeze(self):
        self.handoff["actions"][0]["confirmations"][0].update(status="pending", source=None)
        self.import_action()
        self.snapshot()
        with self.assertRaises(ValueError):
            t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 1)])
        self.value["confirmations"][0].update(status="confirmed", source="Synthetic owner")
        t.save_action(self.store, self.sid, self.aid, self.value, revision=2)
        second = {**self.value, "action_id": new_id(), "proposed": "Alternate title"}
        t.save_action(self.store, self.sid, self.aid, second)
        with self.assertRaises(ValueError):
            t.freeze_batch(self.store, self.sid, [(self.value["action_id"], 2), (second["action_id"], 1)])
        self.assertFalse(t.readiness(self.store, self.sid, t.action(self.store, self.sid, self.value["action_id"], 2), now=datetime.now(timezone.utc) + timedelta(days=2))["ready"])

    def test_receipt_write_and_packet_recheck_private_protection(self):
        self.import_action()
        self.store.enforce_protection = True
        with patch("seo_agent.protection.require_protected", side_effect=ValueError("Denied")) as gate:
            with self.assertRaises(ValueError):
                t.record_receipt(self.store, self.sid, self.receipt())
            with self.assertRaises(ValueError):
                t.packet(self.store, self.sid, self.aid)
            self.assertEqual(gate.call_count, 2)

    def test_outside_interval_cannot_establish_publication_for_measurement(self):
        self.import_action()
        self.snapshot()
        self.snapshot("After")
        comparison = trends.compare_action(self.store, self.sid, self.value["action_id"], 1, self.aid)
        self.assertEqual(comparison["status"], "not ready")
        rid = t.record_review(self.store, self.sid, self.value["action_id"], 1, self.aid, "Outside observation has unknown publication time; no causal result")
        review = t.rows(Store(self.store.root), "tracking_reviews", self.sid)[0]
        self.assertEqual(rid, review["id"])
        self.assertEqual(review["payload"]["comparison"]["status"], "not ready")

    def test_production_receipt_requires_own_prior_exact_approval(self):
        self.import_action()
        r = self.receipt(environment="production")
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, r)
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.other, r)

    def test_attempt_outcomes_replay_correction_rollback_and_restart(self):
        self.import_action()
        r = self.receipt()
        rid = t.record_receipt(self.store, self.sid, r)
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, r)
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, {**r, "receipt_id": new_id()})
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, {**r, "receipt_id": new_id(), "attempt_id": new_id()})
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, {**r, "receipt_id": new_id(), "attempt_id": new_id(), "occurred_utc": utc_now()})
        applied = {**r, "receipt_id": new_id(), "outcome": "reported_applied", "actual": "After", "occurred_utc": utc_now()}
        t.record_receipt(self.store, self.sid, applied)
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, {**applied, "receipt_id": new_id(), "outcome": "failed"})
        correction = {**applied, "receipt_id": new_id(), "outcome": "correction", "actual": "Partly changed", "corrects": applied["receipt_id"], "occurred_utc": utc_now()}
        t.record_receipt(self.store, self.sid, correction)
        rollback = {**applied, "receipt_id": new_id(), "outcome": "rolled_back", "actual": "Before", "occurred_utc": utc_now()}
        t.record_receipt(self.store, self.sid, rollback)
        reopened = Store(self.store.root)
        history = t.rows(reopened, "implementation_receipts", self.sid)
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["id"], rid)
        self.assertEqual(trends.markers(reopened, self.sid), [])

    def test_partial_failure_preserves_attempts_and_actual_values(self):
        self.import_action()
        first = self.receipt()
        t.record_receipt(self.store, self.sid, first)
        t.record_receipt(self.store, self.sid, {**first, "receipt_id": new_id(), "outcome": "partial", "actual": "Intermediate value", "occurred_utc": utc_now()})
        second = self.receipt()
        t.record_receipt(self.store, self.sid, second)
        t.record_receipt(self.store, self.sid, {**second, "receipt_id": new_id(), "outcome": "failed", "occurred_utc": utc_now()})
        values = [r["payload"] for r in t.rows(self.store, "implementation_receipts", self.sid)]
        self.assertEqual([v["outcome"] for v in values], ["attempted", "partial", "attempted", "failed"])
        self.assertEqual(values[1]["actual"], "Intermediate value")

    def test_timestamp_contradictions_and_revision_relationships(self):
        self.import_action()
        first = self.receipt()
        for change in ({"occurred_utc": "2026-01-01T00:00:00Z"}, {"occurred_utc": "2099-01-01T00:00:00Z"}, {"actual": "After"}, {"current": "Wrong"}, {"revision": 2}, {"outcome": "reported_applied", "actual": "After"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                t.record_receipt(self.store, self.sid, {**first, **change})
        t.record_receipt(self.store, self.sid, first)
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, {**first, "receipt_id": new_id(), "outcome": "reported_applied", "actual": "Wrong", "occurred_utc": utc_now()})

    def test_public_verification_is_separate_and_bound_to_snapshot(self):
        _, approval = self.approval()
        first = self.receipt(environment="production", approval=approval)
        t.record_receipt(self.store, self.sid, first)
        applied = {**first, "receipt_id": new_id(), "outcome": "reported_applied", "actual": "After", "occurred_utc": utc_now()}
        t.record_receipt(self.store, self.sid, applied)
        snap = self.snapshot("After")
        verification = {**applied, "receipt_id": new_id(), "outcome": "verification", "occurred_utc": utc_now(), "verification": "Exact title observed; unknown publication time", "verification_snapshot_id": snap}
        t.record_receipt(self.store, self.sid, verification)
        self.assertEqual(len(t.rows(self.store, "outside_changes", self.sid)), 1)
        self.assertIsNone(t.rows(self.store, "outside_changes", self.sid)[0]["payload"]["action_id"])
        with self.assertRaises(ValueError):
            t.record_receipt(self.store, self.sid, {**verification, "receipt_id": new_id(), "actual": "Wrong", "occurred_utc": utc_now()})

    def test_outside_changes_have_exact_diff_and_uncertainty_interval(self):
        first = self.snapshot(checked=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat())
        p.save_snapshot(self.store, self.sid, self.value["url"], status="unavailable", payload={"reason": "HTTP 202"}, checked=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        last = self.snapshot("Outside", extra="<h2>New heading</h2>")
        changes = t.rows(self.store, "outside_changes", self.sid)
        self.assertEqual(len(changes), 1)
        value = changes[0]["payload"]
        self.assertEqual(value["before_snapshot"], first)
        self.assertEqual(value["after_snapshot"], last)
        self.assertEqual(value["diff"]["title"], {"before": "Before", "after": "Outside"})
        self.assertIsNone(value["publication_time"])
        self.assertIsNone(value["approval"])
        self.assertEqual(value["author"], "unknown")

    def test_normalization_preserves_dates_prices_links_and_technical_fields(self):
        self.snapshot(extra="<script>timestamp=1</script>")
        self.snapshot(extra="<script>timestamp=2</script>")
        self.assertEqual(t.rows(self.store, "outside_changes", self.sid), [])
        html = "<html><head><title>Before</title><meta name='robots' content='noindex'></head><body><p>Price $43 on October 9</p><a href='/other/'>Other</a></body></html>"
        values = p.extract(html, self.value["url"], {"X-Robots-Tag": "nofollow"})
        self.assertIn("October 9", values["copy"][0])
        self.assertEqual(values["index_directive"], "noindex")
        self.assertEqual(values["x_robots_tag"], "nofollow")
        self.assertEqual(values["links"][0]["href"], "https://example.com/other/")

    def test_challenge_missing_markup_and_ambiguous_values_never_approve(self):
        for html in ("<html><title>Just a moment...</title><body>Challenge</body></html>", "<title>Incomplete</title>"):
            with self.assertRaises(ValueError):
                p.extract(html, self.value["url"], {})
        self.value.update(action_kind="text", current="Service", proposed="New service")
        self.import_action()
        self.snapshot(extra="<p>Service</p>")
        self.assertFalse(t.readiness(self.store, self.sid, t.actions(self.store, self.sid)[0])["ready"])

    def test_readonly_fetch_robots_tls_boundary_and_errors_preserve_baseline(self):
        self.import_action()
        self.snapshot()
        class Response:
            status_code = 200
            text = "User-agent: *\nDisallow: /blocked"
            url = "https://example.com/"
            headers = {"content-type": "text/html"}
        class Fetcher:
            calls = []
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs
            def get(self, url, *, rp=None):
                self.calls.append((url, rp))
                if rp:
                    r = Response()
                    r.status_code = 202
                    return r
                return Response()
            def close(self):
                pass
        result = p.observe(self.store, self.sid, fetcher_factory=Fetcher)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNotNone(Fetcher.calls[1][1])
        self.assertEqual(t.rows(self.store, "outside_changes", self.sid), [])
        self.assertEqual(p.latest_snapshot(self.store, self.sid, self.value["url"], successful=True)["payload"]["values"]["title"], "Before")
        from urllib.robotparser import RobotFileParser
        parser = RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /client-a/blocked"])
        scoped = p.SiteRobots("https://example.com/client-a/", parser)
        self.assertTrue(scoped.can_fetch("LocalSEOAudit", "https://example.com/client-a/page"))
        self.assertFalse(scoped.can_fetch("LocalSEOAudit", "https://example.com/client-b/page"))
        self.assertFalse(scoped.can_fetch("LocalSEOAudit", "https://example.com/client-a/blocked"))

    def test_throttle_persists_across_restart_and_manual_debounce(self):
        self.import_action()
        with patch("seo_agent.page_tracking.observe", return_value={"status": "complete"}) as observe:
            p.refresh(self.store, self.sid, demo=True)
            p.refresh(Store(self.store.root), self.sid, demo=True)
            p.refresh(Store(self.store.root), self.sid, demo=True, manual=True)
        observe.assert_called_once()
        self.assertEqual(len(t.rows(self.store, "tracking_checks", self.sid)), 1)

    def test_disabled_checks_and_bounds(self):
        p.save_settings(self.store, self.sid, {"enabled": False, "interval_minutes": 15, "max_pages": 1, "urls": []})
        with patch("seo_agent.page_tracking.observe") as observe:
            self.assertEqual(p.refresh(self.store, self.sid)["status"], "disabled")
        observe.assert_not_called()
        with self.assertRaises(ValueError):
            p.save_settings(self.store, self.sid, {"max_pages": 21})
        with self.assertRaises(ValueError):
            p.save_settings(self.store, self.sid, {"urls": ["https://other.example/"]})

    def test_check_audit_backup_file_lock_exclusion(self):
        with run_lock(GLOBAL_LOCK), self.assertRaises(ValueError):
            p.refresh(self.store, self.sid, demo=True)
        self.assertEqual(t.rows(self.store, "tracking_checks", self.sid), [])

    def test_concurrent_replays_only_one_commit(self):
        self.import_action()
        receipt = self.receipt()
        def submit():
            try:
                t.record_receipt(self.store, self.sid, receipt)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            result = list(executor.map(lambda _: submit(), range(2)))
        self.assertEqual(sum(result), 1)
        self.assertEqual(len(t.rows(self.store, "implementation_receipts", self.sid)), 1)

    def test_source_scoped_packet_formula_safe_and_new_backup_restore(self):
        bid, approval = self.approval()
        first = self.receipt(environment="production", approval=approval)
        t.record_receipt(self.store, self.sid, first)
        other_aid = self.store.create_audit(self.other)
        self.assertNotIn(self.value["action_id"], t.packet(self.store, self.other, other_aid).decode())
        packet = report_packet(self.store, self.sid, self.aid)
        with zipfile.ZipFile(io.BytesIO(packet)) as z:
            self.assertIn("tracking.json", z.namelist())
            self.assertEqual(len(json.loads(z.read("tracking.json"))["snapshots"]), 1)
        self.assertIn(b"'=HYPERLINK", safe_csv(pd.DataFrame([{"value": "=HYPERLINK(\"evil\")"}])))
        archive = self.root / "backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "restored")
        self.assertEqual(len(t.actions(restored, self.sid)), 1)
        self.assertEqual(len(t.rows(restored, "public_snapshots", self.sid)), 1)
        self.assertEqual(t.batch(restored, self.sid, bid), t.batch(self.store, self.sid, bid))
        self.assertTrue(t.rows(restored, "human_approvals", self.sid)[0]["payload"]["history_only"])

    def test_old_database_additive_migration_preserves_journal(self):
        from seo_agent.storage import TRACKING_TABLES
        cid = self.store.add_change(self.sid, date="2026-10-06", action="Unspecified historical fix", verification="user-reported")
        with self.store.db() as db:
            for name in TRACKING_TABLES:
                db.execute("DROP TABLE " + name)
            db.execute("PRAGMA user_version=1")
        reopened = Store(self.store.root)
        self.assertEqual(reopened.changes(self.sid)[0]["id"], cid)
        self.assertEqual(t.actions(reopened, self.sid), [])
        with reopened.db() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)


class TrendTests(TrackingFixture, unittest.TestCase):
    def audit(self, start, end, *, created, value, page_value=3, rows_missing=False):
        aid = self.store.create_audit(self.sid, created=created)
        date_rows = [] if rows_missing else [{"date": start, "clicks": value, "impressions": value * 10, "position": 6, "ctr": .99}]
        page_rows = [] if rows_missing else [{"date": start, "page": self.value["url"], "clicks": page_value, "impressions": page_value * 10, "position": 12, "ctr": .99}]
        pd.DataFrame(date_rows, columns=["date", "clicks", "impressions", "position", "ctr"]).to_csv(self.store.audit_file(self.sid, aid, "data", "gsc_daily.csv"), index=False)
        pd.DataFrame(page_rows, columns=["date", "page", "clicks", "impressions", "position", "ctr"]).to_csv(self.store.audit_file(self.sid, aid, "data", "gsc_daily_pages.csv"), index=False)
        self.store.finish_audit(self.sid, aid, "partial", {"synthetic": True, "windows": {"current": {"start": start, "end": end}, "timezone": "America/Los_Angeles"},
            "stages": {"gsc_current": {"status": "complete", "metadata": {"start": start, "end": end, "data_state": "final", "search_type": "web", "timezone": "America/Los_Angeles", "daily_pages_aggregation": "byPage"}}}})
        return aid

    def test_overlapping_dates_choose_source_never_sum_and_page_math(self):
        a = self.audit("2026-01-01", "2026-01-03", created="2026-01-05T12:00:00Z", value=2)
        b = self.audit("2026-01-01", "2026-01-03", created="2026-01-06T12:00:00Z", value=4, page_value=1)
        trends.ingest_audits(self.store, self.sid)
        frame = trends.series(self.store, self.sid, synthetic=True)
        self.assertEqual(frame.iloc[0]["clicks"], 4)
        self.assertEqual(frame.iloc[0]["audit_id"], b)
        self.assertEqual(frame.iloc[0]["ctr"], .1)
        self.assertEqual(frame.iloc[0]["aggregation"], "byProperty")
        page = trends.series(self.store, self.sid, synthetic=True, page=self.value["url"])
        self.assertEqual(page.iloc[0]["clicks"], 1)
        self.assertEqual(page.iloc[0]["position"], 12)
        self.assertEqual(page.iloc[0]["aggregation"], "byPage")
        self.assertEqual(len(t.rows(self.store, "trend_sources", self.sid)), 4)
        self.assertNotEqual(a, b)

    def test_newer_missing_row_unknown_gaps_and_immutable_source(self):
        aid = self.audit("2026-01-01", "2026-01-03", created="2026-01-05T12:00:00Z", value=2)
        trends.ingest_audits(self.store, self.sid)
        original = t.rows(self.store, "trend_sources", self.sid)
        self.audit("2026-01-01", "2026-01-03", created="2026-01-06T12:00:00Z", value=4, rows_missing=True)
        trends.ingest_audits(self.store, self.sid)
        frame = trends.series(self.store, self.sid, synthetic=True)
        self.assertTrue(frame.clicks.isna().all())
        self.assertEqual(frame.segment.tolist(), [1, 2, 3])
        self.assertEqual(t.rows(self.store, "trend_sources", self.sid)[:2], original)
        trends.ingest_audits(Store(self.store.root), self.sid)
        self.assertEqual(len(t.rows(self.store, "trend_sources", self.sid)), 4)
        self.assertEqual(trends.series(self.store, self.sid, synthetic=False).shape[0], 0)

    def test_page_daily_missing_cannot_use_whole_site_or_other_site(self):
        aid = self.audit("2026-01-01", "2026-01-03", created="2026-01-05T12:00:00Z", value=2)
        self.store.audit_file(self.sid, aid, "data", "gsc_daily_pages.csv").unlink()
        trends.ingest_audits(self.store, self.sid)
        frame = trends.series(self.store, self.sid, page=self.value["url"], synthetic=True)
        self.assertTrue(frame.clicks.isna().all())
        with self.assertRaises(ValueError):
            trends.series(self.store, self.other, page=self.value["url"])

    def test_missing_google_values_are_not_exported_as_zero(self):
        from seo_agent.gsc import rows_to_df
        frame = rows_to_df([{"keys": ["2026-01-01"]}], ["date"])
        self.assertTrue(frame.clicks.isna().all())
        aid = self.audit("2026-01-01", "2026-01-03", created="2026-01-05T12:00:00Z", value=2)
        frame.to_csv(self.store.audit_file(self.sid, aid, "data", "gsc_daily.csv"), index=False)
        trends.ingest_audits(self.store, self.sid)
        self.assertTrue(trends.series(self.store, self.sid, synthetic=True).clicks.isna().all())

    def test_trend_sources_restore_with_exact_provenance(self):
        self.audit("2026-01-01", "2026-01-03", created="2026-01-05T12:00:00Z", value=2)
        trends.ingest_audits(self.store, self.sid)
        before = t.rows(self.store, "trend_sources", self.sid)
        archive = self.root / "trends-backup.zip"
        _backup(self.store, archive)
        restored = _restore(archive, self.root / "trends-restored")
        self.assertEqual(t.rows(restored, "trend_sources", self.sid), before)
        self.assertEqual(trends.series(restored, self.sid, synthetic=True).iloc[0]["clicks"], 2)


if __name__ == "__main__":
    unittest.main()
