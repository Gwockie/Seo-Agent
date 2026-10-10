"""Explicit schedule controls; reruns never register tasks or repeat launches."""
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

from . import scheduling as weekly
from .storage import new_id


REASONS = {
    "access_reconnect": "Google access was revoked or the exact property is unavailable. Reconnect only this site's selected connection, then validate its property.",
    "connection_scope_size_or_vault_invalid": "Check this connection's exact scope, Windows Vault access and payload size. There is no plaintext fallback.",
    "temporary_google_network": "Google could not be reached. A bounded retry may be pending.",
    "temporary_source": "A source is temporarily unavailable. See source outcomes and the pending retry.",
    "public_destination_or_tls_invalid": "A public destination, TLS or request boundary was rejected. Review the saved URL and site security before saving the schedule again.",
    "vault_persistence_failed": "The refreshed connection could not be verified in Windows Vault. Review this connection's secure storage before enabling again.",
    "public_content_unavailable": "Website content is unavailable or challenged. Check robots/hosting access with the site owner; no security bypass is used.",
    "interrupted": "The worker stopped before completion. Prior evidence is preserved and a bounded retry may be pending.",
    "restored_review_required": "Restored history is preserved. Review this installation and reconnect before explicitly enabling.",
    "configuration_or_collection_failed": "Review the saved site, selected connection and protected storage. Save the schedule again after resolving setup.",
}


def controls(store, sid, jobs, *, demo=False):
    from .coordination import is_busy
    state = weekly.status(store, sid)
    history = weekly.attempts(store, sid)
    def local(value):
        return weekly.instant(value).astimezone(ZoneInfo(state["settings"]["timezone"])).strftime("%a %b %d, %Y at %I:%M %p %Z")
    with st.expander("Weekly read-only audits", expanded=False):
        st.write("Schedule: " + ("Enabled" if state["settings"]["enabled"] else "Disabled"))
        if is_busy(store.root):
            st.info("Another audit, page check, backup or migration is running. Weekly work is deferred and will retry after the workspace is free.")
        st.caption("Monday 09:00 America/New_York is an editable suggestion. Saving a schedule does not install a Windows task.")
        st.text("Next due: " + (local(state["next_due"]) if state["next_due"] else "Choose and save a schedule"))
        last_attempt = next((a for a in history if a["id"] == state["last_attempt"]), None)
        st.text("Last attempt: " + (local(last_attempt["started"]) + " — " + last_attempt["payload"]["status"] if last_attempt else "None"))
        last = state["last_complete"]
        st.text("Last complete collection: " + (local(last["finished"]) if last else "None"))
        st.caption("Complete means the required sources were collected; indexing and ranking health are shown in the audit.")
        if state["overdue"]:
            st.warning("Overdue: this computer must be signed in, awake and on AC power. Collection starts on the next available dispatcher check.")
        if state["retry_at"]:
            st.info("Retry after: " + local(state["retry_at"]))
        if state["failure"]:
            st.warning(REASONS.get(state["failure"], "Collection needs attention: " + state["failure"]))
        if state["stopped"]:
            st.info("Automatic retries stopped. Resolve the issue, then review and save the schedule again.")
        with st.form(sid + ":weekly_form"):
            s = state["settings"]
            day = st.selectbox("Weekly day", range(7), index=s["weekday"], format_func=lambda n: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][n])
            clock = st.time_input("Local collection time", datetime.strptime(s["local_time"], "%H:%M").time())
            zone = st.text_input("Time zone", s["timezone"], help="IANA name, for example America/New_York")
            enabled = st.checkbox("Enable this site's weekly schedule", value=s["enabled"])
            save = st.form_submit_button("Save weekly schedule", disabled=jobs.busy())
        if save:
            try:
                weekly.save_schedule(store, sid, {**s, "weekday": day, "local_time": clock.strftime("%H:%M"), "timezone": zone, "enabled": enabled})
                st.rerun()
            except Exception:
                st.error("Schedule unavailable. Check the time zone, storage and whether another operation is running.")
        if st.button("Disable weekly schedule", key=sid + ":weekly_disable", disabled=jobs.busy()):
            try:
                weekly.disable(store, sid)
                st.rerun()
            except ValueError:
                st.warning("Another operation is running; disable after it finishes.")
        path = store.root / "weekly-installation.json"
        ready = demo or path.is_file()
        if st.button("Run weekly audit now", key=sid + ":weekly_now", disabled=jobs.busy() or not ready):
            try:
                key = jobs.submit_weekly(store, sid, new_id(), demo=demo)
                st.session_state["weekly_job"] = key
            except ValueError:
                st.error("Another operation is running. Retry after it finishes.")
        key = st.session_state.get("weekly_job")
        if key and key[0] == str(store.root) and key[1] == sid:
            @st.fragment(run_every=2)
            def progress():
                result = jobs.snapshot(key)
                if result and not result["done"]:
                    st.info("Headless audit running. Refresh history when it finishes.")
                elif result:
                    st.info("Worker finished. Check attempt history for completeness or the exact failure category.")
            progress()
        if demo:
            st.caption("Synthetic only; no Windows task or Google connection is used.")
        elif not ready:
            st.info("Windows task is not configured for this workspace. Follow docs/weekly-audits.md from the primary installation after rollout review.")
        else:
            st.caption("Task registration is separate. Use the reviewed task preview/apply CLI in docs/weekly-audits.md to check, register, disable or remove only this app's task.")
            if st.button("Check Windows task status", key=sid + ":weekly_task_status"):
                try:
                    from .windows_tasks import preview
                    st.session_state[sid + ":weekly_task_result"] = preview(path)["current"]
                except Exception:
                    st.error("Task status unavailable. Check the primary installation, selected Windows user and reviewed task identity.")
            task = st.session_state.get(sid + ":weekly_task_result")
            if task is not None:
                st.write("Windows task: " + ("Registered" if task["registered"] else "Not registered"))
                if task["registered"]:
                    st.json({k: v for k, v in task.items() if k != "xml"})
                st.caption("Status from your last explicit check. The task's next dispatcher tick differs from the site's weekly due time.")
        if history:
            st.dataframe([{"Scheduled UTC": a["scheduled"], "Started UTC": a["started"], "Finished UTC": a["finished"],
                           "Status": a["payload"]["status"], "Reason": a["payload"].get("failure"), "Audit": a["audit_id"]} for a in reversed(history)], hide_index=True)
            with st.expander("Collection source outcomes"):
                st.json(history[-1]["payload"]["sources"])
