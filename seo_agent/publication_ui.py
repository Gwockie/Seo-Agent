"""Explicit human controls only; no worker, model or import invokes these handlers."""
import streamlit as st
from . import publishing as p
from . import publisher_setup as ps, discovery as discovery


def setup(store, sid):
    from .discovery_ui import summary
    summary(store, sid)
    ready = ps.readiness(store, sid)
    st.info("Publication readiness: " + ready["level"] + ". " + ready["next_action"])
    for blocker in ready["blockers"]:
        st.warning(blocker)
    with st.expander("Separate server setup packet (no deployment)"):
        st.caption("Installing or activating a server adapter requires approval of this separate exact setup. Content approval cannot authorize installation, host settings or whole-site deployment.")
        st.json(ps.setup_packet(store, sid))
        st.download_button("Download exact companion package (installation needs separate approval)", ps.package_bytes(),
                           file_name="local-seo-publisher-0.2.0.zip", mime="application/zip", key=sid + ":companion_package")
    with st.expander("WordPress publication destination (disabled until configured)"):
        d = p.destination(store, sid)
        st.caption("Choose the separately certified core or Elementor heading adapter. Fresh exact CMS and hosting evidence is required; other themes/plugins/templates remain blocked. See docs/wordpress-publishing.md and docs/elementor-publishing.md.")
        if d:
            st.text(f"{d['environment']} · {d['url']} · " + ("enabled" if d.get("enabled") else "disabled"))
            if st.button("Disable CMS publishing", key=sid + ":cms_disable"):
                p.disable(store, sid)
                st.rerun()
        with st.form(sid + ":cms_setup", clear_on_submit=True):
            adapter = st.selectbox("Publishing adapter", ["core-heading/1", "elementor-heading/1"])
            connections = discovery.connections(store, sid)
            labels = {None: "Select reviewed Hosting & CMS environment", **{c["id"]: c["label"] + " · " + c["environment"] for c in connections}}
            cid = st.selectbox("Bound discovery environment", list(labels), format_func=labels.get)
            environment = st.selectbox("Destination environment", ["production", "staging", "local"])
            url = st.text_input("Exact WordPress home URL", value=store.site(sid).url)
            instance = st.text_input("Independently verified LSEO_INSTANCE identifier")
            isolation = st.text_area("Staging isolation evidence: editor, database, uploads, destination, no live sync/jobs/customer messages, access restriction and noindex")
            isolation_verified = st.checkbox("For staging/local: I verified every listed isolation condition against host/CMS evidence; saving cannot affect production")
            username = st.text_input("Dedicated minimal-permission WordPress username")
            password = st.text_input("Separate WordPress application password", type="password")
            confirmed = st.checkbox("I am the human configuring this exact destination and protected credentials")
            if st.form_submit_button("Configure CMS destination"):
                try:
                    p.configure_from_human_ui(store, sid, url=url, instance=instance, environment=environment,
                        isolation=isolation, isolation_verified=isolation_verified, username=username, password=password, human_clicked=confirmed,
                        adapter=adapter, discovery_id=cid)
                    st.success("Configured. Every publication still requires an exact CMS review, human approval and Apply instruction.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


def batch(store, sid, bid):
    d = p.destination(store, sid)
    if not d or not d.get("enabled"):
        st.info("Publishing remains unavailable until a human configures a separate CMS destination and credentials.")
        return
    st.markdown("**Application-controlled WordPress publication**")
    frozen = p.t.batch(store, sid, bid)
    with st.form(sid + ":cms_map:" + bid):
        mappings = {}
        for f in frozen["payload"]["actions"]:
            st.text(f"{f['action_id']} r{f['revision']} · {f['action']['url']} · {f['action']['action_kind']}")
            page = st.number_input("WordPress page ID", min_value=1, step=1, key=bid + f["action_id"] + ":page")
            if d.get("adapter") == "elementor-heading/1":
                widget = st.text_input("Elementor heading widget ID from CMS evidence", key=bid + f["action_id"] + ":widget")
                row = st.number_input("Exact _elementor_data metadata row ID", min_value=1, step=1, key=bid + f["action_id"] + ":metadata_row")
                mappings[f["action_id"]] = {"object_id": int(page), "element_id": widget, "metadata_row_id": int(row)}
            else:
                anchor = st.text_input("Core heading anchor (CMS block attribute)", key=bid + f["action_id"] + ":anchor")
                mappings[f["action_id"]] = {"object_id": int(page), "anchor": anchor}
        if st.form_submit_button("Read CMS and prepare exact publication review"):
            try:
                p.prepare(store, sid, bid, mappings)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    for r in p.rows(store, sid, "cms_reviews"):
        if r["payload"]["batch_id"] != bid:
            continue
        rid, packet = r["id"], r["payload"]
        with st.expander("CMS publication review " + rid):
            st.download_button("Download CMS review and receipts (history only)", p.t.canonical(p.export_review(store, sid, rid)),
                               file_name="cms-publication-" + rid + ".json", mime="application/json", key=rid + ":download")
            st.text("Destination: " + packet["destination"]["url"] + " · " + packet["destination"]["instance"])
            st.text("Exact write scope: " + packet["write_scope"])
            st.text("CMS review captured: " + packet["reviewed_utc"])
            st.caption("Every write rechecks the exact revision, fresh public evidence and fresh CMS/public values. Changed scope requires renewed human approval.")
            for a in packet["actions"]:
                mapping = (f"metadata row {a['metadata_row_id']} · widget {a['element_id']} · path {a['mapping']['path']}"
                           if a.get("adapter") == "elementor-heading/1" else f"block {a['block_index']} · #{a['anchor']}")
                st.text(f"{a['url']} · page {a['object_id']} · {a['field']} · {mapping}\nCurrent: {a['current']}\nProposed: {a['proposed']}")
                st.json({k: a[k] for k in ("confirmations", "validation", "rollback")})
                if a.get("adapter") == "elementor-heading/1":
                    st.caption("Exact built candidate; only the title token and corresponding mirror text change. This local candidate has not been published.")
                    with st.expander("Raw Elementor before / built candidate"):
                        st.code(a["before"]["elementor_data"], language="json")
                        st.code(a["candidate_data"], language="json")
                        st.code(a["candidate_content"], language="html")
                        st.json({"staging_validation": a["staging_validation"], "hosting_evidence": packet["destination"].get("discovery_binding")})
            with st.expander("Frozen CMS evidence, baseline and inventory"):
                st.json(packet)
            auth = next((a for a in p.rows(store, sid, "cms_authorizations") if a["review_id"] == rid), None)
            if not auth:
                with st.form(rid + ":cms_authorize"):
                    confirmed = st.checkbox("I reviewed these exact CMS fields, factual confirmations, validation, write scope and rollback")
                    source = st.text_input("Responsible human and factual confirmation date/source")
                    rollback = st.checkbox("I also authorize the enumerated rollback values, only while no subsequent CMS edits exist")
                    statement = st.text_input('Type "' + p.STATEMENT + '"')
                    if st.form_submit_button("Approve exact CMS publication review"):
                        try:
                            p.authorize_from_human_ui(store, sid, rid, human_clicked=confirmed, statement=statement, confirmation_source=source, rollback=rollback)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            else:
                st.text("CMS human authorization: " + auth["id"])
                for direction, label in (("apply", "Apply these approved CMS actions"), ("rollback", "Apply explicitly authorized rollback")):
                    if direction == "rollback" and not auth["payload"].get("rollback"):
                        st.caption("Rollback is not authorized. Prepare a new inverse proposal and exact human-approved batch if needed.")
                        continue
                    if st.button(label, key=rid + ":" + direction, disabled=bool(auth["payload"].get("history_only"))):
                        try:
                            p.execute(store, sid, rid, human_clicked=True, direction=direction)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            for attempt in p.rows(store, sid, "cms_attempts"):
                if attempt["review_id"] != rid:
                    continue
                result = p.latest_event(store, sid, attempt["id"])
                st.text(f"{attempt['action_id']} · {attempt['direction']} · attempt {attempt['id']}\nWrite: {result.get('write')} · Verification: {result.get('verification')}")
                st.json(result)
                if st.button("Reconcile destination (read only)", key=attempt["id"] + ":reconcile"):
                    try:
                        p.reconcile(store, sid, attempt["id"])
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                if result.get("write") == "uncertain" and st.button("Reconcile then resume the same approved request", key=attempt["id"] + ":resume"):
                    try:
                        p.resume(store, sid, attempt["id"], human_clicked=True)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
