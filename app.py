"""Streamlit entrypoint. Use python -m seo_agent app for guarded loopback launch."""
import json
import os
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from seo_agent.appearance import app_css, capture_appearance, load_appearance
from seo_agent.previews import load_preview, page_document, preview_frame, preview_revisions, walk
from seo_agent.review_format import report_html
from seo_agent.config import SiteConfig, Phrase, resolve_rules, legacy_phrases
from seo_agent.credentials import WindowsVault, load_connection
from seo_agent.demo import seed_demo
from seo_agent.gsc import service_for_credentials, validate_access
from seo_agent.import_export import export_phrases, import_phrases, report_packet, spreadsheet_frame, safe_csv
from seo_agent.metrics import totals, query_groups, exact_queries
from seo_agent.protection import storage_status, require_protected, ProtectionError
from seo_agent.rules import read_csv, LIMITATIONS
from seo_agent.runner import Jobs
from seo_agent.storage import Store, new_id
from seo_agent.setup_fields import service_rows, services_from_rows, facts_from_rows, rule_rows, overrides_from_rows, phrase_rows, phrases_from_rows
from seo_agent.learning import METRICS, create_plan, plans, link_change, compare, save_review, reviews, explanation
from seo_agent import tracking_ui

ROOT = Path(__file__).resolve().parent
DEMO = os.environ.get("SEO_DEMO") == "1"
WORKSPACE = Path(os.environ.get("SEO_WORKSPACE", str(ROOT / "workspace" / ("demo" if DEMO else "private"))))


@st.cache_resource
def jobs():
    return Jobs()  # Job IDs/progress only; no credential or API result cache.


def table(frame, **kwargs):
    # Streamlit built-in CSV downloads must be safe too; raw evidence stays intact.
    return st.dataframe(spreadsheet_frame(frame), **kwargs)


def error():
    st.error("Operation rejected or unavailable. Check site association, validated configuration, secure storage and source access. No external changes were made.")


def protection_for_ui(store):
    if DEMO:
        return {"verified": False, "reason": "Synthetic demonstration: live Google access and private backup are disabled."}
    # Reuse only this rerun's fresh complete check, never a cross-rerun cache.
    return store.initial_protection or storage_status(store.root)


def formatted_report(content):
    st.caption("Saved reports retain their original wording. The current staging and publication policy shown in the app supersedes older approval wording.")
    st.html(report_html(content))
    with st.expander("Original report text"):
        st.text(content)


def page_previews(store, sid, aid):
    try:
        revisions = preview_revisions(store, sid, aid)
        revision = st.selectbox("Saved page capture", revisions[::-1], format_func=lambda r: f"Capture {r}" , key=sid + ":preview_capture:" + aid) if len(revisions) > 1 else None
        bundle = load_preview(store, sid, aid, revision=revision)
    except (ValueError, KeyError, TypeError):
        st.warning("This preview could not be validated against the selected site and captured values. The saved report remains available.")
        return
    if not bundle:
        st.info("No page copies have been prepared for this audit yet. Proposed edits need a captured page and exact current values before a visual preview can be shown.")
        return
    st.subheader("See the proposed page changes")
    st.caption("Local copies of public pages. Links and forms are inactive. Green marks proposed wording; red marks wording it would replace. Gold outlines mark changed link destinations.")
    names = {i: p["url"].split("/")[-2] or p["title"] for i, p in enumerate(bundle["pages"])}
    number = st.selectbox("Page to compare", list(names), format_func=names.get, key=sid + ":preview_page:" + aid)
    page = bundle["pages"][number]
    st.text(page["url"])
    st.caption("Public page captured " + page["captured_utc"] + f" at {page['width']}px wide. Static layout; interactive and unsupported decorative elements are omitted. This capture supplements the audit and does not complete its automated crawl.")
    display = st.radio("Page display", ["Proposed", "Before", "Side by side"], horizontal=True, key=sid + ":preview_display:" + aid)
    highlights = st.checkbox("Highlight differences", value=True, key=sid + ":preview_highlights:" + aid)
    proposed_title = next((a["proposed"] for a in page["actions"] if a["kind"] == "title"), page["title"])
    if display == "Side by side":
        columns = st.columns(2)
        for column, proposed in zip(columns, (False, True)):
            with column:
                st.markdown("**Proposed**" if proposed else "**Before**")
                st.caption("Browser title: " + (proposed_title if proposed else page["title"]))
                st.iframe(preview_frame(page_document(bundle, page, proposed=proposed, highlights=highlights)), height=870, alt="Proposed page" if proposed else "Captured page")
    else:
        proposed = display == "Proposed"
        st.caption("Browser title: " + (proposed_title if proposed else page["title"]))
        st.iframe(preview_frame(page_document(bundle, page, proposed=proposed, highlights=highlights)), height=870, alt="Proposed page" if proposed else "Captured page")
    with st.expander("Why these changes? Expected effects and how to check", expanded=True):
        nodes = {n.get("id"): n.get("tag") for n in walk(page["tree"])}
        for action_number, action in enumerate(page["actions"]):
            expected = explanation(action, nodes.get(action.get("node_id"), ""))
            st.markdown("**" + action["kind"].capitalize() + " change**")
            st.text("Current: " + action["current"] + "\nProposed: " + action["proposed"])
            st.markdown("**Why it is recommended**")
            st.text(action["rationale"])
            st.markdown("**What we expect**")
            st.text(expected["expected_effect"])
            st.markdown("**How we will check**")
            st.text(expected["measurement"])
            st.text("Confirm: " + action["confirmations"] + "\nValidation: " + action["validation"] + "\nRollback: " + action["rollback"])
            if st.button("Prepare a tracking plan", key=f"{sid}:plan_action:{aid}:{revision}:{number}:{action_number}"):
                st.session_state[sid + ":plan_seed"] = {"audit_id": aid, "title": action["kind"].capitalize() + " change on " + names[number],
                    "why": action["rationale"], "url": page["url"], "current": action["current"], "proposed": action["proposed"], **expected}
                st.session_state[sid + ":plan_baseline"] = aid
                st.session_state["pending_view"] = "Changes & results"
                st.rerun()
    st.info("These are local review drafts. Agents may revise a verified, separate staging copy and report the changes. Publishing or affecting the live site requires your separate approval of the exact actions and factual confirmation. Nothing has been staged or published on the website.")


def setup(store, sid, config):
    protection = protection_for_ui(store)
    st.info(protection["reason"])
    if not protection["verified"]:
        st.warning("Private profile writes, live audit and Google setup are unavailable until storage verification passes. Use the synthetic demonstration meanwhile.")
    connections = store.connections()
    connection_labels = {None: "No connection", **{r["id"]: r["label"] for r in connections}}
    st.subheader("Set up this site")
    st.caption("Start with the business and website. The lists below describe what this business offers. Save local profile keeps these settings on this computer; it does not change the website.")
    with st.form("setup_" + (sid or "new")):
        name = st.text_input("Business name", value=config.name if config else "", max_chars=150, help="The name customers recognize. This labels this site's reports and settings.")
        url = st.text_input("Final public URL", value=config.url if config else "", help="Paste the website's public home address, including https://. Existing site addresses stay fixed to preserve their history.", disabled=bool(config))
        prop = st.text_input("Exact Search Console property", value=config.gsc_property if config else "", help="Copy the property selected in Google Search Console exactly: either https://example.com/ or sc-domain:example.com. This selects the data source; it grants no extra access.", disabled=bool(config))
        industry = st.selectbox("Industry", ["general", "psychology"], index=1 if config and config.industry == "psychology" else 0, help="Psychology adds clinician-review safeguards. General sites use their own services and locations.")
        cid = st.selectbox("Google connection", list(connection_labels), format_func=connection_labels.get, index=list(connection_labels).index(config.connection_id) if config and config.connection_id in connection_labels else 0, help="Choose the saved Google account that has read-only access to this exact property. A missing connection does not delete saved reports.")
        location = st.text_input("Primary location", value=config.location if config else "", max_chars=120, help="The genuine town or area the business serves. Leave blank if no specific location applies.")
        audience = st.text_input("Audience", value=config.audience if config else "", max_chars=300, help="Who the services are for, using confirmed business information. Leave uncertain details out.")
        brands = st.text_area("Brand aliases (one per line)", value="\n".join(config.brand_aliases) if config else "", max_chars=6000, help="Business-name spellings people may search for. These help distinguish people already looking for this business from new discovery searches.")
        st.markdown("**Services and related search terms**")
        st.caption("Add one search term per row. Repeat the service group to keep synonyms together. Existing group names link to your target phrases; changing them affects future audits.")
        groups = st.data_editor(pd.DataFrame(service_rows(config.service_groups if config else {}), columns=["Service group", "Related search term"]), num_rows="dynamic", hide_index=True, key="setup_services:" + (sid or "new"), column_config={
            "Service group": st.column_config.TextColumn(help="A service category, such as electrical_repairs. Repeat it for related terms."),
            "Related search term": st.column_config.TextColumn(help="One phrase someone might use for this service, such as wiring repair. Do not add services the business does not offer.")})
        st.markdown("**Confirmed business facts**")
        st.caption("Optional. Add only facts checked with the business owner or clinician. Leave uncertain claims out. Do not enter patient or customer records.")
        facts = st.data_editor(pd.DataFrame([{"Fact": k, "Confirmed value": v} for k, v in (config.confirmed_facts if config else {}).items()], columns=["Fact", "Confirmed value"]), num_rows="dynamic", hide_index=True, key="setup_facts:" + (sid or "new"), column_config={
            "Fact": st.column_config.TextColumn(help="What was confirmed, such as office address or available service."),
            "Confirmed value": st.column_config.TextColumn(help="The precise confirmed information. Saving a fact is your assertion; the app does not independently verify it.")})
        exclusions = st.text_area("Intentionally excluded URLs (one per line)", value="\n".join(config.exclusions) if config else "", max_chars=30000, help="Optional: pages deliberately kept out of search, such as a private thank-you page. These are excluded from indexing recommendations; they are not a crawl blocklist.")
        original = st.checkbox("This is the original Paoli practice: seed its ten documented phrases", value=False, help="Use only for the original practice. Checking this replaces its target list with the ten original phrases.")
        save = st.form_submit_button("Save local profile", disabled=not DEMO and not protection["verified"])
    if save:
        try:
            payload = {"name": name, "url": url, "gsc_property": prop, "connection_id": cid, "industry": industry, "location": location, "audience": audience,
                "brand_aliases": [b.strip() for b in brands.splitlines() if b.strip()], "service_groups": services_from_rows(groups.to_dict("records")), "confirmed_facts": facts_from_rows(facts.to_dict("records")), "exclusions": [v.strip() for v in exclusions.splitlines() if v.strip()], "overrides": {k: v.model_dump(exclude_none=True) for k, v in config.overrides.items()} if config else {}, "phrases": [p.model_dump() for p in config.phrases] if config else []}
            if original:
                if industry != "psychology" or location.casefold() != "paoli":
                    raise ValueError("Original profile must deliberately select psychology and Paoli")
                payload["phrases"] = [p.model_dump() for p in legacy_phrases()]
            saved_id = store.save_site(SiteConfig.model_validate(payload), sid)
            if not sid:
                with st.spinner("Reading this site's public colors and typography…"):
                    capture_appearance(store, saved_id, demo=DEMO)
            if original and not any("User reported indexing fixes" in c["action"] for c in store.changes(saved_id)):
                store.add_change(saved_id, date="2026-10-06", action="User reported indexing fixes; exact actions and affected URLs were not supplied.", verification="user-reported; unverified", evidence="Implementation handoff dated 2026-10-07")
            st.session_state["pending_site"] = saved_id
            st.rerun()
        except (ValueError, TypeError) as exc:
            st.error("Profile not saved. Check the fields and list rows below.")
            st.text(str(exc)[:1600])
    with st.expander("Manage Google connection references"):
        st.caption("Separate IDs retain separate accounts. One connection can deliberately serve several accessible properties. Account hints do not verify identity.")
        with st.form("new_connection"):
            label = st.text_input("Connection display label", max_chars=150)
            if st.form_submit_button("Add local connection reference", disabled=not DEMO and not protection["verified"]):
                try:
                    store.add_connection(label)
                    st.rerun()
                except ValueError:
                    error()
        for row in connections:
            st.text(row["label"] + " — " + row["id"])
            st.code(f'python -m seo_agent auth --connection {row["id"]}', language="powershell")
        st.caption("Run consent from the local CLI after storage validation. Tokens stay outside browser state, SQLite and reports. Reconnect only the exact connection ID.")
        if st.button("Check Windows credential backend", disabled=DEMO or not protection["verified"]):
            try:
                vault = WindowsVault()
                vault.probe()
                st.success("Windows WinVaultKeyring non-sensitive probe passed.")
            except ValueError:
                error()
        if config and st.button("Validate chosen account and exact property", disabled=DEMO or not protection["verified"] or not config.connection_id):
            try:
                require_protected(store.root)
                svc = service_for_credentials(load_connection(config.connection_id))
                entries = svc.sites().list().execute().get("siteEntry", [])
                validate_access(svc, config.gsc_property, config.url)
                st.success("Selected connection can access this exact property.")
                table(pd.DataFrame(entries), hide_index=True)
            except Exception:
                error()
    if config:
        with st.expander("Advanced audit options"):
            st.caption("Defaults work for ordinary audits. Minimum impressions avoids interpreting very small samples. CTR is the percentage of impressions that turn into clicks; its threshold is a review lead, not a success score. Clinical confirmation cannot be disabled.")
            with st.form("audit_options_" + sid):
                options = st.data_editor(pd.DataFrame(rule_rows(config)), hide_index=True, disabled=["Rule"], column_config={
                    "Enabled": st.column_config.CheckboxColumn(help="Whether this diagnostic runs. Clinical review remains mandatory for psychology."),
                    "Minimum impressions": st.column_config.NumberColumn(min_value=10, max_value=10000, step=1, help="Leave empty for rules that do not use a sample threshold."),
                    "CTR threshold (%)": st.column_config.NumberColumn(min_value=0.1, max_value=10., step=0.1, help="A percentage, such as 3 for 3%. Leave empty for other rules.")}, key=sid + ":rule_options")
                if st.form_submit_button("Save audit options", disabled=not DEMO and not protection["verified"]):
                    try:
                        overrides = overrides_from_rows(options.to_dict("records"), config)
                        store.save_site(SiteConfig.model_validate({**config.model_dump(), "overrides": {k: v.model_dump(exclude_none=True) for k, v in overrides.items()}}), sid)
                        st.rerun()
                    except (ValueError, TypeError) as exc:
                        st.error("Audit options not saved.")
                        st.text(str(exc)[:1000])
        with st.expander("Site appearance", expanded=True):
            st.caption("New sites automatically import public colors and typography. Appearance stays with this site. Fonts are stored locally; no third-party styles run inside the app.")
            try:
                appearance = load_appearance(store, sid)
                if appearance:
                    st.text("Status: " + appearance["status"] + " · " + appearance["captured_utc"])
                    st.caption(appearance["note"])
                    st.text("Headings: " + appearance["heading_font"] + " · Body: " + appearance["body_font"] + " · Accent: " + appearance["accent"])
                else:
                    st.info("Appearance has not been captured for this site. A readable default is in use.")
                if st.button("Refresh site appearance", disabled=not DEMO and not protection["verified"], key=sid + ":appearance_refresh"):
                    with st.spinner("Reading public site appearance…"):
                        capture_appearance(store, sid, demo=DEMO)
                    st.rerun()
            except (ValueError, KeyError, TypeError):
                st.warning("Saved appearance is unavailable or invalid. A readable default is in use.")
        with st.expander("Effective profile/settings for future audits"):
            st.json({"site": config.model_dump(), "effective": resolve_rules(config)})


def phrases(store, sid, config):
    st.caption("Exact phrases remain separate from related groups. Near-me phrases express local intent. Imports replace this site's phrase list only.")
    table(pd.DataFrame([p.model_dump() for p in config.phrases]), hide_index=True)
    with st.form("add_phrase_" + sid):
        text = st.text_input("Exact target phrase", max_chars=200)
        group = st.text_input("Service/intent group", value="service", max_chars=80)
        related = st.text_area("Related terms (one per line)", max_chars=6000)
        loc = st.text_input("Phrase location intent", value=config.location, max_chars=120)
        priority = st.slider("Priority", 1, 5, 3)
        landing = st.text_input("Intended landing page (optional)")
        if st.form_submit_button("Add phrase locally"):
            try:
                new = Phrase(phrase=text, group=group, related_terms=[t.strip() for t in related.splitlines() if t.strip()], location=loc, priority=priority, landing_page=landing)
                candidate = {**config.model_dump(), "phrases": [p.model_dump() for p in config.phrases] + [new.model_dump()]}
                store.save_site(SiteConfig.model_validate(candidate), sid)
                st.rerun()
            except ValueError:
                error()
    with st.form("edit_phrases_" + sid):
        st.caption("Edit rows, add a row at the bottom, or select a row to delete it. Related terms stay one per line within their cell. Save writes only this site's future target list.")
        raw = st.data_editor(pd.DataFrame(phrase_rows(config.phrases), columns=list(Phrase.model_fields)), num_rows="dynamic", hide_index=True, key=sid + ":phrase_editor", column_config={
            "phrase": st.column_config.TextColumn("Target phrase", required=True, help="The exact search you want to measure."),
            "group": st.column_config.TextColumn("Service group", help="Match a group from Setup to connect its related terms."),
            "related_terms": st.column_config.TextColumn("Related terms", help="One term per line; the exact target phrase is measured separately."),
            "priority": st.column_config.NumberColumn("Priority", min_value=1, max_value=5, step=1, default=3),
            "active": st.column_config.CheckboxColumn("Active", default=True),
            "landing_page": st.column_config.TextColumn("Intended page", help="The public page on this site that should answer this search.")})
        if st.form_submit_button("Save phrase list locally"):
            try:
                store.save_site(SiteConfig.model_validate({**config.model_dump(), "phrases": [p.model_dump() for p in phrases_from_rows(raw.to_dict("records"))]}), sid)
                st.rerun()
            except (ValueError, TypeError):
                error()
    st.download_button("Export phrase CSV", export_phrases(sid, config), "target-phrases.csv", "text/csv")
    upload = st.file_uploader("Import phrase CSV", type="csv", key=sid + ":phrase_upload")
    associate = st.checkbox("Explicitly associate an unscoped CSV with this selected site", key=sid + ":associate")
    if upload and st.button("Validate and replace local phrases"):
        try:
            store.save_site(import_phrases(upload.getvalue(), sid, config, associate=associate), sid)
            st.rerun()
        except (ValueError, TypeError):
            error()


def choose_audit(store, sid):
    audits = store.audits(sid)
    if not audits:
        st.info("No audit evidence for this site yet.")
        return None
    labels = {a["id"]: f'{a["created"]} — {a["status"]}' for a in audits}
    aid = st.selectbox("Audit", list(labels), format_func=labels.get, key=sid + ":audit_choice")
    return store.audit(sid, aid)


def audit_view(store, sid, config):
    protection = protection_for_ui(store)
    with st.form("launch_" + sid):
        days = st.selectbox("Days per comparison window", [28, 90])
        max_pages = st.slider("Maximum public pages", 1, 200, 50)
        inspect = st.checkbox("Read-only Google URL Inspection", value=True)
        limit = st.slider("Maximum inspections (priority pages first)", 1, 100, 20)
        launch = st.form_submit_button("Run synthetic audit" if DEMO else "Run read-only audit", disabled=jobs().busy() or (not DEMO and (not protection["verified"] or not config.connection_id)))
    if not DEMO and not protection["verified"]:
        st.warning(protection["reason"])
    if launch:
        try:
            request_id = new_id()
            key = jobs().submit(store, sid, request_id, demo=DEMO, days=days, max_pages=max_pages, inspect=inspect, inspect_limit=limit)
            st.session_state["active_job"] = key
            st.rerun()
        except ValueError:
            error()
    key = st.session_state.get("active_job")
    if key and key[0] == str(store.root) and key[1] == sid:
        @st.fragment(run_every=2)
        def progress():
            state = jobs().snapshot(key)
            if state and not state["done"]:
                st.info("Audit progress: " + state["progress"])
            elif state and state.get("error"):
                st.warning(state["error"])
            elif state:
                st.success("Audit finished. Refresh history to view its reports.")
        progress()
    elif jobs().busy():
        st.info("An audit is running; another launch is unavailable.")
    if st.button("Refresh history") and key and key[0] == str(store.root) and key[1] == sid:
        finished = jobs().snapshot(key)
        if finished and finished.get("audit_id"):
            st.session_state[sid + ":audit_choice"] = finished["audit_id"]
    audit = choose_audit(store, sid)
    if not audit:
        return
    aid = audit["id"]
    saved_config = SiteConfig.model_validate_json(audit["config"])
    manifest = json.loads(audit["manifest"])
    st.write("Source status:")
    if manifest.get("stages"):
        table(pd.DataFrame([{"source": name, "status": value["status"], "note": value.get("observation", value.get("message", ""))} for name, value in manifest["stages"].items()]), hide_index=True)
        window = manifest["windows"]
        st.caption(f'Final web data · Pacific dates · current {window["current"]["start"]} to {window["current"]["end"]} · previous {window["previous"]["start"]} to {window["previous"]["end"]}')
    else:
        st.info("Historical source status: " + audit["status"] + "; original collection/rule completeness may be unknown.")
    with st.expander("Audit manifest details"):
        st.json(manifest)
    if manifest.get("synthetic") or DEMO:
        st.warning("Synthetic evidence — all metrics/findings shown are fixtures.")
    st.caption(LIMITATIONS)
    def frame(name):
        return read_csv(store.audit_file(sid, aid, "data", name + ".csv"))
    success = manifest.get("legacy") or manifest.get("stages", {}).get("gsc_current", {}).get("status") == "complete"
    property_metrics = totals(frame("gsc_totals")) if success else totals(pd.DataFrame())
    columns = st.columns(4)
    for column, label, field in zip(columns, ["Property clicks", "Property impressions", "Property CTR", "Property weighted position"], ["clicks", "impressions", "ctr", "position"]):
        value = property_metrics[field]
        column.metric(label, "Unavailable" if value is None else f"{value:.2%}" if field == "ctr" else f"{value:,.2f}")
    st.caption("Property totals use byProperty aggregation. Query and page totals are separate datasets; do not add them together.")
    daily = frame("gsc_daily") if success else pd.DataFrame()
    from seo_agent.trends import markers as trend_markers
    changes = [{"date": m["date"], "action": m["label"], "verification": m["type"]} for m in trend_markers(store, sid)]
    if not daily.empty:
        dates = manifest.get("windows", {}).get("current", {})
        if dates and not daily["date"].duplicated().any():
            labels = pd.date_range(dates["start"], dates["end"]).strftime("%Y-%m-%d")
            daily = daily.set_index("date").reindex(labels).rename_axis("date").reset_index()
        daily["segment"] = daily["impressions"].isna().cumsum()
        # GSC's ISO dates are calendar labels in Pacific time, not instants.
        # Keep their date components with a UTC scale; browser-local formatting
        # would shift midnight ISO input into the prior day in US time zones.
        reporting_date = alt.X("date:T", title="Pacific reporting date", scale=alt.Scale(type="utc"), axis=alt.Axis(format="%Y-%m-%d"))
        date_tooltip = alt.Tooltip("date:N", title="Pacific reporting date")
        line = alt.Chart(daily).mark_line(point=True).encode(x=reporting_date, y="impressions:Q", detail="segment:N", tooltip=[date_tooltip, "clicks:Q", "impressions:Q"])
        if changes:
            markers = alt.Chart(pd.DataFrame(changes)).mark_rule(color="orange").encode(x=reporting_date, tooltip=[date_tooltip, "action:N", "verification:N"])
            st.altair_chart(line + markers, width="stretch")
        else:
            st.altair_chart(line, width="stretch")
    st.caption("Change dates are observations alongside performance; they do not establish causality.")
    if st.button("Explore persistent trends and exact change details", key=sid + ":open_trends"):
        st.session_state["pending_view"] = "Changes & results"
        st.rerun()
    st.write("Visible query groups (query-only byProperty data)")
    table(query_groups(frame("gsc_queries") if success else pd.DataFrame(), saved_config), hide_index=True)
    st.write("Exact target phrases (missing visible rows are unknown)")
    table(exact_queries(frame("gsc_queries") if success else pd.DataFrame(), saved_config), hide_index=True)
    st.write("Actual landing pages (query/page byPage data)")
    table(frame("gsc_query_page") if success else pd.DataFrame(), hide_index=True)
    st.write("Intended landing pages saved with this audit")
    table(pd.DataFrame([{"phrase": p.phrase, "intended_page": p.landing_page} for p in saved_config.phrases]), hide_index=True)
    st.write("Priority-page indexing evidence")
    table(frame("url_inspection"), hide_index=True)
    # Comparison subtree uses checked audit root; no user-supplied path component.
    comparison = store.audit_file(sid, aid, "data", "gsc_totals.csv", period="previous")
    if manifest.get("stages", {}).get("gsc_previous", {}).get("status") == "complete":
        st.write("Previous equal complete window: property metrics")
        st.json(totals(read_csv(comparison)))
    with st.expander("Saved effective profile (immutable audit snapshot)"):
        st.json(json.loads(audit["resolved"]))
    reviewed = [name for name in ("reviewed-executive-summary.md", "reviewed-recommendations.md", "reviewed-proposed-edits.md") if store.audit_file(sid, aid, "reports", name).is_file()]
    report = st.selectbox("View report", reviewed + ["executive-summary.md", "recommendations.md", "proposed-edits.md", "snapshot.md"], key=sid + ":report")
    path = store.audit_file(sid, aid, "reports", report)
    if path.exists() and path.stat().st_size <= 2 * 1024 * 1024:
        content = path.read_text(encoding="utf-8")
        formatted_report(content)
        st.download_button("Download selected Markdown report", content, report, "text/markdown")
    try:
        st.download_button("Export this audit's evidence/report packet", report_packet(store, sid, aid), "audit-packet.zip", "application/zip")
    except (ValueError, pd.errors.EmptyDataError):
        st.warning("Packet export unavailable; evidence remains local.")


def recommendations(store, sid, config):
    audit = choose_audit(store, sid)
    st.caption("Review state never grants publication permission. Agents may revise verified isolated staging and report changes; live changes need exact approval. The app has no CMS write integration.")
    if audit:
        aid = audit["id"]
        tracking_ui.proposals(store, sid, aid)
        documents = {label: name for label, name in (
            ("Summary", "reviewed-executive-summary.md"),
            ("Recommendations", "reviewed-recommendations.md"),
            ("Proposed edits", "reviewed-proposed-edits.md"),
        ) if store.audit_file(sid, aid, "reports", name).is_file()}
        if documents:
            st.subheader("Review together")
            st.caption("Start with the summary, then compare the recommendations and proposed edits. These saved documents belong to the selected audit.")
            if audit["status"] == "partial":
                st.warning("This audit is incomplete. Read its collection limits before deciding on changes; missing evidence does not prove the website is healthy.")
            label = st.radio("Review document", list(documents), horizontal=True, key=sid + ":review:" + aid)
            if label == "Proposed edits":
                page_previews(store, sid, aid)
            path = store.audit_file(sid, aid, "reports", documents[label])
            if path.stat().st_size <= 2 * 1024 * 1024:
                content = path.read_text(encoding="utf-8")
                formatted_report(content)
                st.download_button("Download this review document", content, documents[label], "text/markdown")
            else:
                st.warning("This review document exceeds the display limit.")
            st.info("Reading a report or saving a local draft does not approve a published change. Staging recommendations may be revised on a verified separate copy. Confirm the facts and approve exact live actions separately.")
        else:
            page_previews(store, sid, aid)
        findings = store.findings(sid, aid)
        st.subheader("Automated findings")
        if not findings:
            st.info("No automated findings were generated for this audit. Check its source limitations and reviewed reports; this does not prove there are no issues.")
        for number, row in enumerate(findings, start=1):
            f = row["payload"]
            with st.expander(f'{f["priority"]} {f["category"]} — finding {number}'):
                st.text("Page: " + f.get("url", "") + "\nSearch: " + f.get("query", ""))
                st.markdown("**Why it is recommended**")
                st.text(f.get("detail", "Evidence detail unavailable."))
                st.markdown("**Suggested change**")
                st.text(f.get("proposed_action", "Proposed action unavailable."))
                expected = {
                    "indexing": "Make an intended page eligible to appear in search; eligibility does not guarantee visibility.",
                    "canonical": "Help Google consolidate signals on the intended URL. Google's selected canonical must be checked separately.",
                    "broken_link": "Help visitors reach the intended destination and repair the observed navigation path.",
                    "alignment": "Help relevant searches lead to the intended service page. Query/page data must show whether alignment improves.",
                    "relevance": "Make the confirmed offering and location clearer. Better relevant visibility remains a hypothesis.",
                    "ctr": "Test whether clearer search-result wording attracts more relevant clicks. Position and demand can also affect CTR.",
                    "clinical_review": "Improve factual accuracy after clinician confirmation. A ranking benefit is not established."}.get(f.get("rule"), "A later evidence review is required to establish whether this helps.")
                st.markdown("**What we expect**")
                st.text(expected)
                st.markdown("**How we will check**")
                st.text(f.get("measurement", "Measurement plan unavailable."))
                st.text("Facts to confirm: " + "; ".join(f.get("confirmations", [])))
                st.text("Evidence: " + "; ".join(f"{ref['file']} row {ref['row']}" for ref in f.get("evidence", [])))
                if st.button("Prepare a tracking plan", key=sid + ":plan_finding:" + row["id"]):
                    st.session_state[sid + ":plan_seed"] = {"audit_id": aid, "title": f.get("category", "Recommendation"), "url": f.get("url", ""),
                        "why": f.get("detail", ""), "expected_effect": expected, "measurement": f.get("measurement", ""),
                        "metric": "Indexing / correct landing page" if f.get("rule") in ("indexing", "canonical", "alignment") else "Content accuracy / user experience" if f.get("rule") == "clinical_review" else "Page CTR" if f.get("rule") == "ctr" else "Page impressions"}
                    st.session_state[sid + ":plan_baseline"] = aid
                    st.session_state["pending_view"] = "Changes & results"
                    st.rerun()
                state = st.selectbox("Local recommendation state", ["proposed", "reviewed", "implemented", "verified", "dismissed"], index=["proposed", "reviewed", "implemented", "verified", "dismissed"].index(row["state"]), key=sid + ":state:" + row["id"])
                if st.button("Save state", key=sid + ":save:" + row["id"]):
                    try:
                        store.set_finding_state(sid, aid, row["id"], state)
                        st.rerun()
                    except ValueError:
                        error()
        if not audit["legacy"]:
            draft_path = store.audit_file(sid, aid, "reports", "local-draft.md")
            with st.form("draft_" + sid + aid):
                draft = st.text_area("Local proposed copy/approval packet", value=draft_path.read_text(encoding="utf-8") if draft_path.exists() else "", height=200, max_chars=50000)
                st.caption("Include current/proposed values, confirmations, validation, rollback and exact affected URLs before requesting approval outside this app.")
                if st.form_submit_button("Save local draft"):
                    try:
                        store.require_private_write()
                        draft_path.write_text(draft, encoding="utf-8")
                        st.success("Local draft saved.")
                    except ValueError:
                        error()
    with st.form("change_" + sid):
        changed = st.date_input("Change/observation date", value=date.today())
        url = st.text_input("Affected URL (optional)")
        action = st.text_area("Exact action or observation", max_chars=4000)
        prior = st.text_area("Prior value (if known)", max_chars=4000)
        proposed = st.text_area("Proposed/implemented value (if known)", max_chars=4000)
        approval = st.text_input("Independent exact-action approval reference (if supplied)", max_chars=4000)
        evidence = st.text_area("Implementation/verification evidence", max_chars=4000)
        verification = st.selectbox("Verification status", ["user-reported; unverified", "implementation evidence supplied", "independently verified"])
        if st.form_submit_button("Record local change/observation"):
            try:
                store.add_change(sid, date=changed.isoformat(), action=action, url=url, prior_value=prior, proposed_value=proposed, approval_reference=approval, evidence=evidence, verification=verification)
                st.rerun()
            except ValueError:
                error()
    table(pd.DataFrame(store.changes(sid)), hide_index=True)


def change_results(store, sid, config):
    st.subheader("Changes & results")
    tracking_ui.settings_ui(store, sid)
    tracking_ui.charts(store, sid, demo=DEMO)
    st.info("A saved plan is a hypothesis. It does not approve or publish a website change. Record what was actually published, then compare later evidence. This journal preserves lessons for you and future audits; it does not automatically change audit rules.")
    audits = store.audits(sid)
    if not audits:
        st.info("Collect or import an audit before creating a baseline plan.")
        return
    labels = {a["id"]: f'{a["created"]} — {a["status"]}' for a in audits}
    seed = st.session_state.get(sid + ":plan_seed", {})
    seed_aid = seed.get("audit_id")
    baseline = st.selectbox("Baseline audit", list(labels), index=list(labels).index(seed_aid) if seed_aid in labels else 0, format_func=labels.get, key=sid + ":plan_baseline", help="The saved audit from before this change. Its site profile and evidence stay unchanged.")
    with st.form("plan_" + sid):
        title = st.text_input("Change name", seed.get("title", ""), max_chars=200)
        url = st.text_input("Page affected", seed.get("url", ""), help="Use the exact public page address. Page metrics require it.")
        current = st.text_area("Current value", seed.get("current", ""), max_chars=8000)
        proposed = st.text_area("Proposed value", seed.get("proposed", ""), max_chars=8000)
        why = st.text_area("Why we recommend it", seed.get("why", ""), max_chars=4000)
        expected = st.text_area("Expected effect — a hypothesis", seed.get("expected_effect", ""), max_chars=4000, help="Describe the mechanism and intended benefit. Do not enter a promised ranking or traffic gain.")
        metric = st.selectbox("Primary measure", METRICS, index=METRICS.index(seed.get("metric", METRICS[0])), help="Pick the main outcome. Page CTR is clicks divided by impressions. A lower average position is generally better. Content accuracy needs factual review.")
        measurement = st.text_area("How we will check", seed.get("measurement", ""), max_chars=4000, help="Include the intended page/searches, factual checks and possible other explanations. Automatic comparisons require equal complete reporting periods before and after publication.")
        if st.form_submit_button("Save tracking plan"):
            try:
                create_plan(store, sid, baseline, {"title": title, "url": url, "current": current, "proposed": proposed, "why": why, "expected_effect": expected, "metric": metric, "measurement": measurement})
                st.session_state.pop(sid + ":plan_seed", None)
                st.success("Tracking plan saved locally. No website change was made.")
            except (ValueError, TypeError) as exc:
                st.error("Plan not saved.")
                st.text(str(exc)[:1200])
    records = plans(store, sid)
    st.markdown("**Saved plans and evidence reviews**")
    if not records:
        st.caption("No plans saved yet. A recommendation's Prepare a tracking plan button fills in the explanation for you.")
    changes = store.changes(sid)
    for record in records:
        pid, p = record["id"], record["payload"]
        with st.expander(p["title"], expanded=len(records) == 1):
            st.text("Page: " + p["url"] + "\nWhy: " + p["why"] + "\nExpected: " + p["expected_effect"] + "\nCheck: " + p["measurement"])
            st.caption("Baseline: " + labels.get(record["audit_id"], record["audit_id"]) + " · Main measure: " + p["metric"])
            if not record["change_id"]:
                st.caption("Planned. No published implementation is attached.")
                with st.form("published_" + pid):
                    published = st.date_input("Date published (Pacific reporting date)", value=date.today(), key=pid + ":date", help="Only record a change that was actually published. Local or staging edits do not produce public SEO outcomes.")
                    evidence = st.text_area("What was published and how it was checked", key=pid + ":evidence", max_chars=4000)
                    approval = st.text_input("Exact-action approval reference", key=pid + ":approval", help="A reference to the separate permission and factual review. Entering it here does not grant publication permission.")
                    if st.form_submit_button("Record published implementation"):
                        try:
                            if not evidence.strip():
                                raise ValueError("Describe the actual implementation and verification. This record remains user-reported.")
                            cid = store.add_change(sid, date=published.isoformat(), action=p["title"], url=p["url"], prior_value=p["current"], proposed_value=p["proposed"], evidence=evidence, approval_reference=approval, verification="user-reported; unverified")
                            link_change(store, sid, pid, cid)
                            st.rerun()
                        except (ValueError, TypeError) as exc:
                            st.error("Implementation not attached.")
                            st.text(str(exc)[:1000])
                if changes:
                    change_labels = {c["id"]: c["date"] + " — " + c["action"] for c in changes}
                    existing = st.selectbox("Or choose an existing published change record", [None, *change_labels], format_func=lambda c: "Select a record" if c is None else change_labels[c], key=pid + ":existing")
                    if st.button("Attach this existing record", key=pid + ":attach", disabled=existing is None):
                        link_change(store, sid, pid, existing)
                        st.rerun()
            else:
                attached = next(c for c in changes if c["id"] == record["change_id"])
                st.caption("Publication recorded: " + attached["date"] + " · " + attached["verification"])
            after = st.selectbox("Follow-up audit", list(labels), format_func=labels.get, key=pid + ":after")
            result = compare(store, sid, pid, after)
            if result["status"] == "comparable":
                st.caption("Comparable final web-search periods in Pacific dates. Missing query rows and off-site factors limit conclusions.")
                for label, side in (("Before", result["baseline"]), ("After", result["followup"])):
                    st.text(f"{label}: {side['window']['start']} to {side['window']['end']} · {side['value']:.2%}" if p["metric"] == "Page CTR" else f"{label}: {side['window']['start']} to {side['window']['end']} · {side['value']:,.2f}")
                    st.caption("Source: " + side["file"] + " · " + side["aggregation"])
                st.text("Difference: " + (f"{result['difference'] * 100:+.2f} percentage points" if p["metric"] == "Page CTR" else f"{result['difference']:+,.2f}"))
                if result["baseline"]["window"]["synthetic"]:
                    st.warning("Synthetic demonstration data; these are not live results.")
                if result["other_changes"]:
                    st.caption("Other recorded changes may affect the comparison:")
                    table(pd.DataFrame(result["other_changes"]), hide_index=True)
            st.info(result["status"].capitalize() + ": " + result["reason"])
            with st.form("review_" + pid):
                lesson = st.text_area("What we learned / what remains uncertain", key=pid + ":lesson", max_chars=4000, help="Separate observations from explanations. Note other edits, changing demand, small samples or incomplete evidence.")
                if st.form_submit_button("Save evidence review"):
                    try:
                        save_review(store, sid, pid, after, lesson)
                        st.rerun()
                    except (ValueError, TypeError) as exc:
                        st.error("Review not saved.")
                        st.text(str(exc)[:1000])
            for review in reviews(store, sid, pid):
                st.caption("Saved review: " + review["created"] + " · " + review["payload"]["comparison"]["status"])
                st.text(review["payload"]["notes"])
    if records:
        st.download_button("Download this site's learning journal", safe_csv(pd.DataFrame([
            {"site_id": sid, "plan_id": r["id"], "baseline_audit": r["audit_id"], "created": r["created"], **r["payload"],
             "reviews": json.dumps([v["payload"] for v in reviews(store, sid, r["id"])], ensure_ascii=False)} for r in records])), "learning-journal.csv", "text/csv")


MAX_PHRASE_TEXT = 250000


def main():
    st.set_page_config(page_title="Local SEO workspace", layout="wide")
    # Editable cells stay literal. Use our formula-safe CSV download controls
    # instead of Streamlit's unsanitized editor export.
    st.set_option("client.disableDataExport", True)
    st.html(app_css())
    st.title("Local SEO workspace")
    st.caption("One user · read-only collection · site-scoped evidence · local proposed edits")
    try:
        store = Store(WORKSPACE, enforce_protection=not DEMO)
    except ProtectionError as exc:
        st.warning(str(exc))
        st.info("Live setup and collection are disabled. Restrict access to the private app folders, then restart the app. Disk encryption is optional for local use. Existing evidence and credentials remain in place.")
        st.code(f'python -m seo_agent --workspace "{WORKSPACE}" storage-check', language="powershell")
        st.caption("See docs/setup-and-migration.md. Use python -m seo_agent app --demo for synthetic validation.")
        return
    if DEMO:
        seed_demo(store)
        st.warning("DEMO: three synthetic sites. No client credentials or live website requests are used.")
    sites = store.sites()
    labels = {None: "Add a site", **{s["id"]: s["name"] for s in sites}}
    if "pending_site" in st.session_state:
        st.session_state["selected_site"] = st.session_state.pop("pending_site")
    if "selected_site" not in st.session_state and len(sites) == 1:
        st.session_state["selected_site"] = sites[0]["id"]
    sid = st.sidebar.selectbox("Site", list(labels), format_func=labels.get, key="selected_site")
    if st.session_state.get("previous_site") != sid:
        previous = st.session_state.get("previous_site")
        if previous:
            for key in list(st.session_state):
                if isinstance(key, str) and key.startswith(previous + ":"):
                    del st.session_state[key]
        st.session_state["previous_site"] = sid
    if "pending_view" in st.session_state:
        st.session_state["view"] = st.session_state.pop("pending_view")
    if "view" not in st.session_state:
        st.session_state["view"] = "Recommendations & changes" if sid and store.audits(sid) else "Setup"
    view = st.sidebar.radio("View", ["Setup", "Target phrases", "Overview & audits", "Recommendations & changes", "Changes & results"], key="view")
    if not sid:
        setup(store, None, None)
        return
    config = store.site(sid)
    tracking_ui.controls(store, sid, jobs(), demo=DEMO)
    try:
        st.html(app_css(load_appearance(store, sid)))
    except (ValueError, KeyError, TypeError):
        st.sidebar.caption("Site appearance unavailable; readable default in use.")
    st.subheader("Selected site")
    st.text(labels[sid])
    if view == "Setup":
        setup(store, sid, config)
    elif view == "Target phrases":
        phrases(store, sid, config)
    elif view == "Overview & audits":
        audit_view(store, sid, config)
    elif view == "Recommendations & changes":
        recommendations(store, sid, config)
    else:
        change_results(store, sid, config)


if __name__ == "__main__":
    main()
