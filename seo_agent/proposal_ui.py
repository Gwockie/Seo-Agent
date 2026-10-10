"""Human proposal editing and local assessments, separate from approval controls."""
import pandas as pd
import streamlit as st

from . import proposal_review as review, tracking as t, page_tracking as p
from .import_export import spreadsheet_frame
from .learning import METRICS


def assessment_ui(store, sid, record):
    key = f"{sid}:{record['action_id']}:{record['revision']}"
    st.markdown("**Assessment of expected effectiveness**")
    st.caption("Evaluate the saved revision. Unsaved editor changes are excluded. No guaranteed ranking improvement or SEO-plugin score is inferred.")
    if st.button("Evaluate this saved revision", key=key + ":evaluate"):
        try:
            review.assess(store, sid, record["action_id"], record["revision"])
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    history = review.evaluations(store, sid, record["action_id"])
    if not history:
        st.info("No assessment saved. Model review unavailable: no configured executor. Evaluation runs local mechanical checks and prepares a private review request.")
        return
    for e in reversed(history):
        stale = review.is_stale(store, sid, e)
        with st.expander(f"Assessment · revision {e['revision']} · {e['created']}" + (" · STALE" if stale else " · current"), expanded=e == history[-1]):
            if stale:
                st.warning("Historical assessment: proposal, evidence, target or configuration changed. Evaluate the current revision before approval.")
            payload, mechanical = e["payload"], e["payload"]["mechanical"]
            st.markdown("**Mechanical validation**")
            for title, field in (("Mandatory blockers", "blockers"), ("Improves (literal checks)", "improves"), ("Weakens (literal checks)", "weakens"), ("Advisory suggestions", "advisory"), ("Uncertainty", "uncertainty")):
                st.text(title + ":\n" + ("\n".join(mechanical[field]) or "None identified by these checks"))
            st.text("Post-publication measurement:\n" + mechanical["measurement"])
            model = payload["model"]
            if model:
                st.markdown("**Model judgment · advisory interpretation**")
                st.text("Reported reviewer: " + model["reviewer"] + " · model: " + model["model"] + " (local handoff; identity is not independently authenticated)")
                for axis, judgment in model["axes"].items():
                    st.text(axis.replace("_", " ").capitalize() + ": " + judgment["assessment"] + "\nEvidence: " + ", ".join(judgment["evidence_ids"]))
                for title in ("improves", "weakens", "advisory"):
                    st.text(title.capitalize() + ":\n" + ("\n".join(j["assessment"] + " · evidence: " + ", ".join(j["evidence_ids"]) for j in model[title]) or "None reported"))
                st.text("Uncertainty: " + "\n".join(model["uncertainty"]))
                st.text("Mandatory owner questions: " + ("\n".join(model["missing_confirmations"]) or "None added; model cannot confirm owner facts"))
                st.text("Measurement suggestion: " + model["measurement"])
                st.caption("You may keep stylistic choices despite advisory feedback. Owner questions and deterministic blockers remain enforced separately; a model cannot approve or publish.")
            else:
                st.info("Model review unavailable. These mechanical checks are not a complete assessment of effectiveness. Use an authorized local reviewer with the pinned request below.")
                if not stale:
                    st.download_button("Download private model review request", review.handoff(store, sid, e), "proposal-review-request.json", "application/json", key=e["id"] + ":request")
                    upload = st.file_uploader("Model assessment JSON for this request", type=["json"], key=e["id"] + ":output")
                    if st.button("Import model assessment", key=e["id"] + ":import", disabled=upload is None):
                        try:
                            review.import_model(store, sid, e["id"], upload.getvalue())
                            st.rerun()
                        except (ValueError, TypeError):
                            st.error("Assessment rejected: use the exact current request, all five dimensions and its evidence IDs. Output cannot grant approval or confirm owner facts.")
            with st.expander("Pinned assessment evidence and configuration"):
                st.json({"binding": payload["binding"], "input": payload["input"]})


def editor(store, sid, record):
    a, revision, identity = record["payload"], record["revision"], record["action_id"]
    key = f"{sid}:{identity}:{revision}"
    history = [r for r in t.actions(store, sid, latest=False) if r["action_id"] == identity]
    with st.expander("Compare versions and restore"):
        comparison = st.selectbox("Compare latest proposal with", [r["revision"] for r in history], format_func=lambda v: f"Revision {v}" + (" · original" if v == 1 else ""), key=key + ":compare")
        earlier = next(r for r in history if r["revision"] == comparison)
        left, right = st.columns(2)
        with left:
            st.caption(f"Revision {comparison} · proposed wording/action")
            st.text(earlier["payload"]["proposed"])
        with right:
            st.caption(f"Latest revision {revision} · proposed wording/action")
            st.text(a["proposed"])
        fields = ("proposed", "rationale", "expected_effect", "primary_measure", "measurement", "validation", "rollback", "confirmations", "revision_note")
        st.dataframe(spreadsheet_frame(pd.DataFrame([{"Field": field.replace("_", " "), f"Revision {comparison}": t.canonical(earlier["payload"].get(field)) if isinstance(earlier["payload"].get(field), list) else earlier["payload"].get(field, ""),
                                                   "Latest proposal": t.canonical(a[field]) if isinstance(a.get(field), list) else a.get(field, "")} for field in fields])), hide_index=True)
        st.caption("Restore appends a new proposal revision. It does not restore old evidence, confirmations for changed wording, assessments or approval.")
        if st.button("Restore as new revision", key=key + ":restore", disabled=comparison == revision):
            try:
                review.restore(store, sid, record, comparison)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.text("Revision history:\n" + "\n".join(f"r{r['revision']} · {r['created']} · {r['payload'].get('revision_note', '')}" for r in history))
    with st.expander("Edit / Revise proposal", expanded=st.session_state.get(sid + ":edit_action") == identity):
        st.caption("Saving creates a local proposal revision. It does not approve, reject or publish. The target URL/field and audit evidence stay attached to this action; a different target requires its own exact action.")
        st.text("Observed baseline (separate from editable proposal): " + (a["current"] or "Unknown") + "\nSource: " + a["current_source"])
        with st.form(key + ":revision"):
            proposed = st.text_area("Exact proposed value", a["proposed"], key=key + ":proposed", max_chars=8000)
            rationale = st.text_area("Rationale", a["rationale"], key=key + ":rationale", max_chars=4000)
            expected = st.text_area("Expected effect", a["expected_effect"], key=key + ":expected", max_chars=4000)
            measurement = st.text_area("How to measure results", a["measurement"], key=key + ":measurement", max_chars=4000)
            measure = st.selectbox("Primary proposal measure", METRICS, index=METRICS.index(a["primary_measure"]), key=key + ":measure")
            validation = st.text_area("Validation plan", a["validation"], key=key + ":validation", max_chars=4000)
            rollback = st.text_area("Rollback plan", a["rollback"], key=key + ":rollback", max_chars=4000)
            questions = sorted({c["item"] for c in a["confirmations"]} | set(review.required_questions(store, sid, record)))
            facts = st.text_area("Factual items (one per line)", "\n".join(questions), key=key + ":fact_items", max_chars=100000)
            st.caption("Existing questions are retained even if removed here. Changed wording resets facts to pending unless you explicitly confirm the exact revised wording.")
            confirmed = st.checkbox("I have confirmed these factual items with the responsible owner/clinician", key=key + ":facts")
            source = st.text_input("Factual confirmation source", key=key + ":fact_source", max_chars=2000)
            note = st.text_area("Reason for revision / disagreement (optional)", key=key + ":note", max_chars=4000)
            if st.form_submit_button("Save new proposal revision"):
                try:
                    if confirmed and not source.strip():
                        raise ValueError("Provide the responsible owner's confirmation source")
                    review.revise(store, sid, record, {"proposed": proposed, "rationale": rationale, "expected_effect": expected, "measurement": measurement, "primary_measure": measure, "validation": validation, "rollback": rollback,
                        "confirmations": [{"item": item.strip(), "status": "pending", "source": None} for item in facts.splitlines() if item.strip()]}, note=note, owner_confirmed=confirmed, confirmation_source=source)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with st.expander("Adopt independently observed public values"):
            captured = p.latest_snapshot(store, sid, a["url"])
            target = p.capture_target(store, sid, record) if a["action_kind"] in ("text", "href") else None
            current = p.observed_value(captured["payload"]["values"], a, target=target, html=captured["payload"]["html"]) if captured and captured["status"] == "complete" else None
            st.text("Latest matching public value: " + (current or "Unavailable / exact target unresolved"))
            st.caption("An observation is adopted from an independent capture, never from editor text. Text/link targets require captured structural evidence; unresolved targets remain blocked.")
            if st.button("Adopt public capture as new revision", key=key + ":adopt", disabled=current is None or current == a["proposed"]):
                try:
                    t.save_action(store, sid, record["audit_id"], {**a, "current": current, "current_source": "Public snapshot " + captured["id"], "capture_time_utc": captured["checked"], "revision_note": "Adopted independent public capture", "restored_from": None}, revision=revision + 1)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    assessment_ui(store, sid, record)
