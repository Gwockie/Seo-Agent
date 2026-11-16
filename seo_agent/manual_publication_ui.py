"""Human controls for a manual WordPress page title update."""
import streamlit as st

from . import manual_publication as manual, page_tracking, tracking


def scope(a):
    m = a["manual_post_title"]
    st.text(f"WordPress page {m['page_id']} · Title (post_title)\n"
            f"Public effect · Elementor Post Title heading widget {m['widget_id']}\n"
            f"CMS mapping evidence · {m['source']}\nShared effects and affected URLs · {m['shared_effects']}")
    st.caption("Exact action covers opening the production page editor, its autosave effects, and updating this one Title field. Review all affected surfaces before authorizing that action.")
    st.text(f"Rollback candidate · page {m['page_id']} · Title (post_title)\n"
            f"From: {a['proposed']}\nTo: {a['current']}")
    st.caption("Rollback requires fresh evidence of the current value and shared effects, then separate exact human approval before opening the production editor.")


def panel(store, sid, batch, invalid):
    bid = batch["id"]
    try:
        frozen, approval = manual.context(store, sid, bid)
    except ValueError:
        return
    a = frozen["action"]
    events = manual.history(store, sid, frozen, approval)
    st.markdown("**Manual CMS handoff**")
    if not events:
        if invalid:
            st.info("Refresh and review a new exact batch before a manual attempt.")
            return
        st.caption("Use separately authorized access and read-only CMS evidence to recheck the page identity, raw Title, dynamic binding and shared effects. Preserve the existing title and revision reference. Stop if any of these checks is unavailable or differs from the frozen review.")
        with st.form(bid + ":manual_begin"):
            confirmed = st.checkbox("I rechecked the approved CMS baseline and scope and preserved the revision reference")
            source = st.text_input("Read-only preflight evidence reference", max_chars=3900)
            if st.form_submit_button("Record start of manual attempt"):
                try:
                    manual.begin(store, sid, bid, preflight_confirmed=confirmed, source=source)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        return
    st.text("Attempt started (UTC) · " + events[0]["occurred_utc"])
    if len(events) == 1:
        if invalid:
            st.warning("The approved baseline has changed or is stale. Stop any further CMS edits and reconcile the attempt.")
        else:
            st.text(f"1. In WordPress Pages, open the standard editor for page {a['manual_post_title']['page_id']} at {a['url']}.\n"
                    f"2. Recheck the Title and replace {a['current']!r} with {a['proposed']!r}. Leave the slug, Elementor widgets and other fields alone.\n"
                    "3. Update the page once. Record what happened below, including any uncertain or partial result.")
        with st.form(bid + ":manual_report"):
            choices = {"reported_applied": "I published the exact title", "failed": "Publication failed or the result is unknown", "partial": "A different title or partial result was observed"}
            outcome = st.selectbox("Manual publication outcome", list(choices), index=None, format_func=choices.get)
            occurred = st.text_input("Outcome time in UTC (ISO 8601)", max_chars=40)
            actual = st.text_input("Actual title for a partial result", max_chars=8000)
            source = st.text_area("Operator and outcome evidence or uncertainty", max_chars=3900)
            if st.form_submit_button("Record operator report"):
                try:
                    manual.report(store, sid, bid, outcome=outcome, source=source, occurred=occurred, partial_value=actual)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        return
    for event in events[1:]:
        label = "Public heading verified at capture" if event.get("verification_snapshot_id") else "Reported " + event["outcome"].replace("_", " ")
        st.text(label + " · " + event["occurred_utc"] + "\n" + event["source"])
        if event["outcome"] == "partial":
            st.text("Operator-reported actual title · " + event["actual"])
        if event.get("verification_snapshot_id"):
            st.text("Public capture reference · " + event["verification_snapshot_id"])
    snapshot, status = manual.observation(store, sid, frozen, events)
    st.caption(status)
    st.caption("Public evidence covers the saved HTML for this page. Confirm the raw CMS title, cross-page effects, and browser or cache behavior separately.")
    if snapshot:
        compare_public(store, sid, frozen, snapshot)
        if not any(v.get("verification_snapshot_id") == snapshot["id"] for v in events):
            if st.button("Record independent public heading verification", key=bid + ":manual_verify"):
                try:
                    manual.verify(store, sid, bid)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    if events[-1]["outcome"] in {"partial", "failed", "correction", "rolled_back"}:
        st.warning("Reconcile the actual CMS title and shared effects before proposing any inverse operation. The original rollback candidate assumes the exact proposed title was saved.")


def compare_public(store, sid, frozen, snapshot=None):
    a = frozen["action"]
    baseline = next(r for r in tracking.rows(store, "public_snapshots", sid) if r["id"] == frozen["snapshot_id"])
    with st.expander("Public title, links and index directives"):
        for label, capture in (("Frozen baseline", baseline), ("Latest public capture", snapshot)):
            if capture is None:
                continue
            st.text(label + " · " + capture["checked"])
            st.json(page_tracking.title_surfaces(capture["payload"]["values"], a["url"]))
