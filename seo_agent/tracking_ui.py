"""Single-user review controls; imported content is rendered as literal text."""
import json

import altair as alt
import pandas as pd
import streamlit as st

from . import tracking, page_tracking, trends
from .import_export import safe_csv, spreadsheet_frame
from .learning import plans
from .storage import new_id


def show_action(a):
    st.text(a["action_kind"].capitalize() + " · " + a["url"])
    st.text("Before: " + (a["current"] if a["current"] is not None else "Unknown") + "\nProposed: " + a["proposed"])
    st.text("Why: " + a["rationale"] + "\nExpected effect: " + a["expected_effect"] + "\nHow to measure: " + a["measurement"])
    for c in a["confirmations"]:
        st.text("Confirm: " + c["item"] + " · " + c["status"] + " · " + (c["source"] or "source missing"))
    st.text("Validation: " + a["validation"] + "\nRollback: " + a["rollback"])


def controls(store, sid, jobs, *, demo=False):
    s = page_tracking.settings(store, sid)
    st.sidebar.caption("Read-only tracking while this app is open. A closed app is not monitoring.")
    history = tracking.rows(store, "tracking_checks", sid)
    if history:
        last = history[-1]
        st.sidebar.text("Last checked (UTC): " + last["started"] + "\n" + last["payload"]["status"])
    key_name = sid + ":tracking_job"
    opened = sid + ":tracking_opened"
    manual = st.sidebar.button("Refresh tracked pages", disabled=jobs.busy())
    if manual or (s["enabled"] and not st.session_state.get(opened) and not jobs.busy()):
        try:
            st.session_state[key_name] = jobs.submit_check(store, sid, new_id(), manual=manual, demo=demo)
            st.session_state[opened] = True
        except ValueError:
            st.sidebar.info("Another collection/backup is active. Refresh when it finishes.")
    key = st.session_state.get(key_name)
    if key:
        @st.fragment(run_every=1)
        def status():
            state = jobs.snapshot(key)
            if state and not state["done"]:
                st.sidebar.caption(state["progress"])
            elif state:
                if state.get("error"):
                    st.sidebar.warning("Read-only check unavailable; prior evidence preserved.")
                else:
                    st.sidebar.caption("Check: " + state.get("tracking", {}).get("status", "done"))
        status()


def settings_ui(store, sid):
    s = page_tracking.settings(store, sid)
    with st.expander("Tracked pages and check settings"):
        with st.form(sid + ":tracking_settings"):
            enabled = st.checkbox("Check on site opening and audit completion", value=s["enabled"])
            interval = st.number_input("Minimum automatic check interval (minutes)", min_value=15, max_value=10080, value=s["interval_minutes"])
            limit = st.number_input("Maximum pages per check", min_value=1, max_value=20, value=s["max_pages"])
            urls = st.text_area("Additional exact tracked URLs (one per line)", "\n".join(s["urls"]), max_chars=42000)
            st.caption("Latest proposal pages and configured target landing pages are included, up to the page limit. Successful captures are compared; incomplete content remains unknown.")
            if st.form_submit_button("Save tracking settings"):
                try:
                    page_tracking.save_settings(store, sid, {"enabled": enabled, "interval_minutes": int(interval), "max_pages": int(limit), "urls": [u.strip() for u in urls.splitlines() if u.strip()]})
                    st.success("Saved. Use Refresh tracked pages to check now.")
                except ValueError:
                    st.error("Settings rejected; use exact selected-site URLs and bounded values.")
        captures = tracking.rows(store, "public_snapshots", sid)[-40:]
        if captures:
            st.dataframe(spreadsheet_frame(pd.DataFrame([{k: r[k] for k in ("url", "checked", "status")} for r in captures])), hide_index=True)
            with st.expander("Source limits / check failures"):
                for r in captures:
                    st.text(r["url"] + " · " + r["checked"] + "\n" + r["payload"].get("reason", r["payload"].get("values", {}).get("limits", "")))


def proposals(store, sid, aid):
    st.subheader("Exact publication review")
    st.caption("Import proposals or use saved page copies. Review values, facts, validation and rollback, then freeze the exact batch. Publishing requires a separate authorized WordPress implementation step; this app cannot publish.")
    upload = st.file_uploader("Proposal handoff (JSON or Markdown)", type=["json", "md", "txt"], key=sid + ":handoff:" + aid)
    if st.button("Import proposal handoff", key=sid + ":handoff_import:" + aid, disabled=upload is None):
        try:
            tracking.import_handoff(store, sid, aid, upload.getvalue())
            st.success("Proposal imported idempotently. Imported assertions are not human approval.")
        except (ValueError, TypeError, OSError):
            st.error("Handoff rejected. Check the version, site/audit, exact values and own-audit evidence references.")
    from .previews import preview_revisions
    revisions = preview_revisions(store, sid, aid)
    if revisions:
        rev = st.selectbox("Preview to track", revisions, key=sid + ":tracking_preview:" + aid)
        if st.button("Track these saved preview actions", key=sid + ":preview_import:" + aid):
            try:
                tracking.from_preview(store, sid, aid, rev)
                st.success("Preview actions saved as proposals; factual assertions remain pending.")
            except ValueError:
                st.info("These actions may already be tracked, or the saved capture is incomplete. Earlier records were preserved.")
    records = [r for r in tracking.actions(store, sid) if r["audit_id"] == aid]
    if not records:
        st.info("No exact actions tracked for this audit yet.")
        return
    selected = []
    for r in records:
        identity, revision, a = r["action_id"], r["revision"], r["payload"]
        key = f"{sid}:{identity}:{revision}"
        ready = tracking.readiness(store, sid, r)
        with st.expander(a["action_kind"] + " · " + a["url"] + f" · revision {revision}", expanded=st.session_state.get(sid + ":edit_action") == identity):
            st.text("Current: " + (a["current"] if a["current"] is not None else "Unknown") + "\nProposed: " + a["proposed"])
            st.text("Reason: " + a["rationale"] + "\nExpectation: " + a["expected_effect"] + "\nMeasure: " + a["measurement"])
            st.text("Validation: " + a["validation"] + "\nRollback: " + a["rollback"])
            st.json(a["evidence"])
            for c in a["confirmations"]:
                st.text("Factual assertion: " + c["item"] + " · " + c["status"] + " · " + (c["source"] or "source unavailable"))
            st.caption("Ready for frozen review" if ready["ready"] else "Review incomplete: " + "; ".join(ready["reasons"]))
            from .proposal_ui import editor
            editor(store, sid, r)
        if st.checkbox("Include " + a["action_kind"] + " on " + a["url"] + f" (r{revision})", key=key + ":include", disabled=not ready["ready"]):
            selected.append((identity, revision))
    if st.button("Freeze selected publication batch", key=sid + ":freeze:" + aid, disabled=not selected):
        try:
            tracking.freeze_batch(store, sid, selected)
            st.rerun()
        except ValueError:
            st.error("Batch could not be frozen. Refresh and review changed/overlapping values.")
    for b in tracking.rows(store, "publication_batches", sid):
        if not all(a["audit_id"] == aid for a in b["payload"]["actions"]):
            continue
        with st.expander("Frozen batch " + b["id"]):
            st.caption("Frozen at " + b["created"] + " · " + b["payload"]["fingerprint"])
            for a in b["payload"]["actions"]:
                show_action(a["action"])
                st.caption("Revision " + str(a["revision"]) + " · action " + a["action_id"])
            with st.expander("Frozen evidence and capture references"):
                st.json(b["payload"])
            invalid = tracking.batch_validity(store, sid, b["id"])
            approved = [a for a in tracking.rows(store, "human_approvals", sid) if a["batch_id"] == b["id"]]
            if invalid:
                st.warning("Approval cannot be reused for changed/stale actions: " + ", ".join(invalid))
            if approved:
                st.text("Human approval reference: " + approved[-1]["id"])
                st.caption("Approval is separate from attempted, reported applied, publicly observed and measured outcomes.")
                if approved[-1]["payload"].get("history_only"):
                    st.warning("Restored approval is historical evidence. Freeze a new batch and obtain fresh human approval before another attempt.")
            else:
                with st.form(sid + ":approve:" + b["id"]):
                    confirm = st.checkbox("I reviewed the exact actions, factual confirmations, validation and rollback", key=b["id"] + ":reviewed")
                    source = st.text_input("Who confirmed the factual items and when?", max_chars=4000)
                    statement = st.text_input('Type "I approve this exact publication batch"', max_chars=100)
                    if st.form_submit_button("Record my exact human approval", disabled=bool(invalid)):
                        try:
                            tracking.approve_from_human_ui(store, sid, b["id"], human_clicked=confirm, statement=statement, confirmation_source=source)
                            st.rerun()
                        except ValueError:
                            st.error("Approval not recorded. Explicit human authorization and a current unchanged batch are required.")
            st.info("Next: a separately authorized agent/human applies only these actions in WordPress, records implementation receipts and verifies public values. Publishing remains unavailable here.")


def charts(store, sid, *, demo=False):
    st.subheader("Persistent SEO trends and website history")
    pages = page_tracking.tracked_urls(store, sid)
    page = st.selectbox("Trend scope", [None, *pages], format_func=lambda u: "Whole site · byProperty" if u is None else u + " · byPage", key=sid + ":trend_page")
    metric = st.selectbox("Trend metric", ["impressions", "clicks", "ctr", "position"], key=sid + ":trend_metric")
    frame = trends.series(store, sid, page=page, synthetic=demo)
    markers = trends.markers(store, sid, page=page)
    x = alt.X("date:T", title="Pacific reporting date", scale=alt.Scale(type="utc"), axis=alt.Axis(format="%Y-%m-%d"))
    tooltip = [alt.Tooltip("date:N", title="Pacific reporting date"), alt.Tooltip(metric + ":Q"), "status:N", "audit_id:N", "source_id:N"]
    if not frame.empty:
        if frame[metric].isna().all():
            st.info("The selected metric is unavailable for every saved date in this scope. Values remain unknown; only change markers can be shown.")
        line = alt.Chart(frame).mark_line(point=True).encode(x=x, y=alt.Y(metric + ":Q", axis=alt.Axis(format=".1%") if metric == "ctr" else alt.Axis()), detail="segment:N", tooltip=tooltip)
        layers = [line]
        if markers:
            marks = pd.DataFrame([{k: v for k, v in m.items() if k != "detail"} for m in markers])
            layers.append(alt.Chart(marks).mark_rule(color="#b76d10").encode(x=x, tooltip=["date:N", "label:N", "type:N"]))
            intervals = marks[marks["type"].eq("uncertain interval")]
            if not intervals.empty:
                layers.append(alt.Chart(intervals).mark_rect(opacity=.12, color="#b76d10").encode(x=alt.X("date_before:T", scale=alt.Scale(type="utc")), x2="date:T", tooltip=["date_before:N", "date:N", "label:N"]))
        st.altair_chart(alt.layer(*layers), width="stretch")
        st.download_button("Download selected trend with provenance", safe_csv(frame), "seo-trend.csv", "text/csv")
        with st.expander("Daily values, chosen sources and collection gaps"):
            st.dataframe(spreadsheet_frame(frame), hide_index=True)
    else:
        st.info("Daily source unavailable for this scope. Use Refresh after a finalized audit. Historical whole-site exports cannot supply page trends.")
    st.caption("Markers show reported publication or first observation, with uncertainty intervals. Local/staging work has no live marker. Missing rows remain unknown; lines stop at gaps. No causal attribution, qualified inquiry count or map-pack rank is inferred.")
    if markers:
        selected = st.selectbox("Select a change marker", [m["id"] for m in markers], format_func=lambda key: next(m["date"] + " · " + m["label"] + " · " + m["url"] for m in markers if m["id"] == key), key=sid + ":marker")
        detail = next(m["detail"] for m in markers if m["id"] == selected)
        if "action" in detail and isinstance(detail["action"], dict):
            show_action(detail["action"]["payload"])
            receipt = detail["receipt"]["payload"]
            st.text("Reported actual: " + (receipt["actual"] or "Unknown") + "\nReported implementation (UTC): " + receipt["occurred_utc"])
            st.text("Approval reference: " + (receipt["approval_id"] or "Unavailable") + "\nVerification: " + (receipt["verification"] or "Not verified by this receipt"))
            for v in detail["reviews"]:
                st.text("Saved review: " + v["created"] + "\n" + v["payload"]["notes"])
        elif "payload" in detail and "diff" in detail["payload"]:
            d = detail["payload"]
            st.text("Outside edit observed between " + d["last_known_before_utc"] + " and " + d["first_observed_after_utc"] + " (UTC)")
            st.text("Author, publication time, rationale and expected effect are unknown. No approval or plan association is inferred.")
            for field, values in d["diff"].items():
                st.text(field.replace("_", " ").capitalize() + "\nBefore: " + json.dumps(values["before"], ensure_ascii=False) + "\nAfter: " + json.dumps(values["after"], ensure_ascii=False))
        else:
            st.text("Before: " + detail.get("prior_value", "Unknown") + "\nReported value: " + detail.get("proposed_value", "Unknown") + "\nVerification: " + detail.get("verification", "Unknown"))
        with st.expander("Exact marker evidence, approval reference, verification and saved reviews"):
            st.json(detail)
    with st.expander("Implementation attempts, failures and local/staging receipts"):
        for r in tracking.rows(store, "implementation_receipts", sid)[-100:]:
            st.json(r)
    with st.expander("Saved exact-action outcome reviews"):
        records = tracking.actions(store, sid, latest=False)
        if records and store.audits(sid):
            labels = {f"{r['action_id']}:{r['revision']}": r for r in records}
            choice = st.selectbox("Exact action/revision to review", list(labels), key=sid + ":review_action")
            r = labels[choice]
            aids = [a["id"] for a in store.audits(sid)]
            aid = st.selectbox("Later audit for exact action", aids, key=sid + ":review_after")
            st.json(trends.compare_action(store, sid, r["action_id"], r["revision"], aid))
            with st.form(sid + ":action_review"):
                notes = st.text_area("Observed results and uncertainty", max_chars=4000)
                if st.form_submit_button("Save exact-action evidence review"):
                    try:
                        tracking.record_review(store, sid, r["action_id"], r["revision"], aid, notes)
                        st.rerun()
                    except ValueError:
                        st.error("Review rejected; preserve site association and describe the uncertainty.")
            for v in tracking.rows(store, "tracking_reviews", sid):
                if v["action_id"] == r["action_id"] and v["revision"] == r["revision"]:
                    st.json(v)
    with st.expander("Use an existing tracking plan as an exact proposal"):
        existing = plans(store, sid)
        if existing:
            lookup = {r["id"]: r["payload"]["title"] for r in existing}
            pid = st.selectbox("Saved plan to extend", list(lookup), format_func=lookup.get, key=sid + ":extend_plan")
            with st.form(sid + ":extend_plan_form"):
                kind = st.selectbox("Exact action kind", ["title", "text", "href", "canonical", "index_directive", "setting"])
                confirmations = st.text_area("Factual items requiring confirmation", max_chars=2000)
                validation = st.text_area("Validation before and after implementation", max_chars=4000)
                rollback = st.text_area("Rollback for this exact action", max_chars=4000)
                if st.form_submit_button("Prepare exact proposal from saved plan"):
                    try:
                        tracking.from_plan(store, sid, pid, kind, confirmations, validation, rollback)
                        st.success("Exact proposal created. Review it in Recommendations & changes; refresh current public values.")
                    except ValueError:
                        st.error("Plan lacks an exact page/value or required review details.")
