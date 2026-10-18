"""App-managed discovery and inert evidence review; no publication controls."""
from pathlib import Path
import streamlit as st

from . import discovery as d


def _error():
    st.error("Operation unavailable or rejected. Check protected storage, exact site/environment, the documented evidence format and current access. Earlier evidence is preserved.")


def summary(store, sid):
    """Advisory integration at publication setup; never supplies publisher authority."""
    with st.expander("Saved hosting/CMS discovery compatibility"):
        found = d.connections(store, sid)
        if not found:
            st.info("Configure access and gather compatibility evidence in Hosting & CMS. Publication credentials and approvals remain separate.")
        for c in found:
            st.text(f"{c['label']} · {c['environment']} · {c['url']}")
            report = d.compatibility(store, sid, c["id"])
            for blocker in report["blockers"]:
                st.caption(blocker)
            st.caption(f"Staging: {report['staging']['status']}. Missing evidence: {len(report['missing'])}.")


def render(store, sid, *, demo=False):
    st.subheader("Hosting & CMS connections")
    st.caption("Save discovery access once per site and environment. Discovery cannot enable publishing or create approval. Credentials stay in Windows Credential Manager.")
    st.info("Application passwords inherit the account's permissions. This reader only uses fixed GET routes. Authentication can update host access logs and application-password last-used/IP bookkeeping; it does not invoke editor/save, autosave, setup or cache-flush routines.")
    found = d.connections(store, sid)
    from .publisher_setup import readiness
    ready = readiness(store, sid)
    st.info("Readiness: " + ready["level"] + ". " + ready["next_action"])
    labels = {None: "Add a discovery environment", **{c["id"]: c["label"] + " · " + c["environment"] for c in found}}
    prefix = sid + ":discovery:"
    if prefix + "pending" in st.session_state:
        st.session_state[prefix + "selection"] = st.session_state.pop(prefix + "pending")
    cid = st.selectbox("Discovery environment", list(labels), format_func=labels.get, key=prefix + "selection")
    c = d.connection(store, sid, cid) if cid else None
    formkey = prefix + (cid or "new") + ":"
    defaults = c or {"label": "Production", "provider": "Unknown", "environment": "production", "url": store.site(sid).url,
                     "method": "public", "installation_id": ""}
    with st.form(formkey + "setup", clear_on_submit=True):
        label = st.text_input("Connection name", defaults["label"], max_chars=100, key=formkey + "label")
        provider = st.text_input("Hosting provider (Unknown is allowed)", defaults["provider"], max_chars=100, key=formkey + "provider")
        envs = ["production", "staging", "local"]
        environment = st.selectbox("Environment", envs, index=envs.index(defaults["environment"]), key=formkey + "environment")
        url = st.text_input("Canonical CMS home URL (ending in /)", defaults["url"], key=formkey + "url")
        methods = ["public", "wordpress_rest", "administrator_export"]
        method = st.selectbox("Read access method", methods, index=methods.index(defaults["method"]), key=formkey + "method")
        instance = st.text_input("Installation identity from host evidence (leave blank if unknown)", defaults["installation_id"], max_chars=100, key=formkey + "instance")
        st.caption("An app connection ID is not a CMS installation ID. Enter a stable, independently obtained host/CMS identity before importing metadata. Imported identity assertions remain unverified by the app.")
        username = st.text_input("Discovery account username (WordPress REST only)", key=formkey + "username")
        password = st.text_input("Discovery application password (WordPress REST only)", type="password", key=formkey + "password")
        st.caption("Leave both credential fields empty to retain existing access to the same destination. A different URL/identity or restored connection requires reconnection. No host account or plugin is created.")
        save = st.form_submit_button("Save discovery connection", disabled=demo)
        if save:
            try:
                new = d.configure(store, sid, dict(label=label, provider=provider, environment=environment, url=url,
                                  method=method, installation_id=instance), cid=cid, username=username, password=password)
                st.session_state[prefix + "pending"] = new
            except ValueError:
                _error()
    if prefix + "pending" in st.session_state:
        # Widget selection is changed before its next construction, not after it.
        st.rerun()
    if not c:
        st.caption("After saving, select the environment to collect and review evidence. See docs/cms-discovery.md for the protected administrator export format.")
        return
    st.text(f"Access: {'connected' if c['enabled'] else 'reconnection required'} · installation: {c['installation_id'] or 'unknown'} ({c['installation_certainty']})")
    if st.button("Disconnect discovery access", key=formkey + "disconnect", disabled=demo):
        try:
            d.disconnect(store, sid, cid)
            st.rerun()
        except ValueError:
            _error()
    with st.form(formkey + "refresh"):
        pages = st.text_input("Published page IDs to inspect (comma separated, up to 10)", key=formkey + "pages",
                              help="Leave blank to list the first 20 public REST page identities. Choose exact IDs for raw metadata cross-checks and rendered captures.")
        clicked = st.form_submit_button("Refresh read-only discovery", disabled=demo or not c["enabled"])
        if clicked:
            try:
                ids = [int(n.strip()) for n in pages.split(",") if n.strip()]
                with st.spinner("Reading bounded CMS evidence…"):
                    d.refresh(store, sid, cid, ids)
                st.success("Read-only discovery saved. Missing/private host facts still require administrator evidence.")
            except ValueError:
                _error()
    with st.expander("Protected administrator evidence import / export"):
        st.caption("Use an owner-protected local JSON file. Only the allowlisted evidence schema is accepted; exclude options, users, submissions and credentials. An import records assertions, never independently verified facts or publishing authority.")
        st.json(d.export_template(store, sid, cid))
        with st.form(formkey + "import"):
            path = st.text_input("Protected administrator JSON path", key=formkey + "import_path")
            if st.form_submit_button("Import selected environment evidence", disabled=demo or not c["enabled"]):
                try:
                    d.import_evidence(store, sid, cid, Path(path))
                    st.success("Saved versioned administrator assertions with source hash and collection time.")
                except (ValueError, OSError):
                    _error()
        with st.form(formkey + "export"):
            path = st.text_input("New protected output JSON path", key=formkey + "export_path")
            template = st.checkbox("Write an empty scoped administrator template", value=True, key=formkey + "template")
            if st.form_submit_button("Write protected evidence file", disabled=demo):
                try:
                    d.export_file(store, sid, cid, Path(path), template=template)
                    st.success("Protected local file created. History exports are inert and cannot be imported as authority.")
                except (ValueError, OSError):
                    _error()
    report = d.compatibility(store, sid, cid)
    from .publisher_setup import HOST_CONDITIONS, review_host, setup_packet
    with st.expander("Pinned publisher host effects and separate setup packet"):
        st.caption("Administrator imports remain assertions. Independently inspect provider/CMS records before confirming these exact conditions. This review cannot authorize setup or publication.")
        admin = d.latest(store, sid, cid, "administrator_export")
        if admin:
            st.json(admin["payload"]["body"]["data"]["host"])
        st.json(setup_packet(store, sid, cid))
        with st.form(formkey + "publisher_host"):
            checks = [st.checkbox(condition, key=formkey + "host_condition:" + str(i)) for i, condition in enumerate(HOST_CONDITIONS)]
            source = st.text_input("Independent provider/CMS review source", max_chars=300, key=formkey + "host_source")
            confirmed = st.checkbox("I am the human who independently checked these host records", key=formkey + "host_human")
            if st.form_submit_button("Record exact host effects review", disabled=demo or not c["enabled"]):
                try:
                    review_host(store, sid, cid, human_clicked=confirmed, source=source,
                                conditions=[condition for condition, checked in zip(HOST_CONDITIONS, checks) if checked])
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    st.markdown("**Compatibility and evidence**")
    for blocker in report["blockers"]:
        st.warning(blocker)
    with st.expander("Supported adapter combinations and restrictions"):
        st.json(report["supported_combinations"])
    for key, title in (("confirmed", "Confirmed by current reads"), ("inferred", "Inferred public clues"),
                       ("administrator_asserted", "Administrator assertions"), ("missing", "Missing evidence")):
        with st.expander(title, expanded=key == "missing"):
            for value in report[key]:
                st.text(value)
            if not report[key]:
                st.caption("None recorded.")
    with st.expander("Staging isolation evidence"):
        st.json(report["staging"])
        admin = d.latest(store, sid, cid, "administrator_export")
        if admin:
            st.json(admin["payload"]["body"]["data"]["host"])
        with st.form(formkey + "isolation"):
            source = st.text_input("Independent human host review reference", max_chars=300, key=formkey + "review_source")
            reviewed = st.checkbox("I independently reviewed the concrete resources and all isolation conditions against host evidence", key=formkey + "reviewed")
            if st.form_submit_button("Record host isolation review", disabled=demo or not c["enabled"] or c["environment"] == "production"):
                try:
                    d.review_isolation(store, sid, cid, human_clicked=reviewed, source=source)
                    st.rerun()
                except ValueError:
                    _error()
    with st.expander("Offline Elementor heading preparation"):
        st.caption("Requires current independently collected REST page/rendered evidence and a matching administrator metadata row. A successful mapping remains unsupported for publication.")
        with st.form(formkey + "mapping"):
            pid = st.number_input("CMS page ID", min_value=1, step=1, key=formkey + "map_page")
            widget = st.text_input("CMS-derived heading widget ID", key=formkey + "widget")
            proposed = st.text_input("Proposed heading for local JSON preview", max_chars=500, key=formkey + "proposed")
            if st.form_submit_button("Cross-check and save local mapping", disabled=demo or not c["enabled"]):
                try:
                    d.prepare_mapping(store, sid, cid, int(pid), widget, proposed)
                    st.success("Saved local candidate with exact metadata row, widget path and provenance. Publishing remains unsupported.")
                except ValueError:
                    _error()
    with st.expander("Prepare an exact saved Elementor action"):
        from . import elementor_candidates as candidates, tracking
        st.caption("Choose an existing action and its latest revision. This creates an offline candidate or a precise blocked result; it grants no setup, staging or production authority. The strict publishing adapters remain unchanged.")
        actions = tracking.actions(store, sid)
        choices = {a["action_id"]: a for a in actions}
        if choices:
            with st.form(formkey + "action_candidate"):
                selected = st.selectbox("Saved action revision", list(choices),
                    format_func=lambda key: f"{choices[key]['audit_id']} · {key} · revision {choices[key]['revision']} · {choices[key]['payload']['current']}",
                    key=formkey + "candidate_action")
                action = choices[selected]
                st.text("Proposed: " + action["payload"]["proposed"])
                pid = st.number_input("Candidate CMS page ID", min_value=1, step=1, key=formkey + "candidate_page")
                widget = st.text_input("Candidate heading widget ID", key=formkey + "candidate_widget")
                if st.form_submit_button("Inspect saved action and prepare offline candidate", disabled=demo or not c["enabled"]):
                    try:
                        candidates.prepare(store, sid, cid, selected, action["revision"], int(pid), widget)
                        st.rerun()
                    except ValueError:
                        _error()
            seen = set()
            for row in d.records(store, sid, cid):
                if row["kind"] != candidates.KIND:
                    continue
                data = row["payload"]["body"]["data"]
                if data["action_id"] in seen:
                    continue
                seen.add(data["action_id"])
                st.text(f"{data['action_id']} · revision {data['revision']} · {data['level']} · {d.status(store, sid, cid, row)}")
                for reason in data["preparation_blockers"] + data["publication_blockers"]:
                    st.warning(reason)
                st.json(data)
        else:
            st.info("Save an exact action under Recommendations & changes first.")
    with st.expander("Version history, freshness and attempts"):
        for a in d.attempts(store, sid, cid):
            st.text(f"{a['kind']} · {a['started']} · {a['status']}" + (" (interrupted or still in progress)" if not a["finished"] else ""))
        for r in d.records(store, sid, cid):
            b = r["payload"]["body"]
            st.text(f"Version {r['version']} · {r['kind']} · {b['observed_utc']} · {d.status(store, sid, cid, r)} · {b['certainty']}")
            with st.expander("Evidence " + r["id"]):
                st.json(r["payload"])
