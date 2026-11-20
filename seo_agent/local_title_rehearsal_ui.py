"""Proposal and Hosting & CMS controls for the opt-in disposable rehearsal."""
import streamlit as st

from tools.local_title_rehearsal import app_control, capture_review, lifecycle, proposal_binding
from tools.local_title_rehearsal.runtime import PROJECT
from tools.local_title_rehearsal.scope import BREADCRUMB, CONTACT_HEADING, CURRENT, HEADING, HOME, LITERAL_NAVIGATION, PATHS, PROPOSED

from .previews import preview_frame, static_capture_document


ACTIONS = (
    ('forward', 'Apply saved Title'),
    ('recover', 'Recover interrupted attempt'),
    ('restore', 'Restore original Title'),
    ('verify', 'Verify restoration'),
)


CAPTURE_COMPARISON_STYLE = """
<style>
[class*="st-key-rehearsal-capture-layout-"] {
    container: rehearsal-capture-layout / inline-size;
}
@container rehearsal-capture-layout (max-width: 42rem) {
    [data-testid="stHorizontalBlock"] { flex-direction: column; }
    [data-testid="stColumn"] { flex: none; width: 100%; }
    [data-testid="stElementContainer"]:has(> [data-testid="stIFrame"]) { display: none; }
}
</style>
"""


def enabled(store, sid):
    return app_control.opted_in() and proposal_binding.source_scope(store, sid) is not None


def _title(value, replacement):
    if value is None:
        return 'Unavailable'
    return value if value in (CURRENT, replacement) else 'Unexpected raw Title'


def _effects():
    with st.expander('Declared effects on two pages'):
        st.text(f'{PATHS[0]}\nChange dynamic H1, breadcrumb, document title and four navigation labels.')
        st.text(f'{PATHS[1]}\nChange four shared navigation labels. Preserve H1 and document title.')
        st.caption('The four labels are header item 771 and footer item 801 in their main and dropdown menus. '
                   'Raw publication checks bind visible navigation destinations. Canonical, robots metadata and '
                   'X-Robots-Tag must match the baseline on both pages.')
        st.caption('The Docker copy uses its own historical configuration. These checks cover the two declared local pages.')

def _runtime(status, replacement):
    for role, identity in status.containers.items():
        st.text(f'Registered {role} container: {identity}')
    st.caption(f'Isolation: {"verified" if status.isolation else "unavailable"} · '
               f'Baseline preflight: {"passed" if status.preflight else "unavailable"}')
    if status.blocker:
        st.warning(status.blocker)
    label = 'Observed local baseline' if status.pending_binding else 'Current stored Title'
    st.text(label + ': ' + _title(status.title, replacement))


def _binding(binding):
    st.text(f"Source page: {binding['mapping']['source_url']}\n"
            f"Source site: {binding['site_id']}\nAudit: {binding['audit_id']}\n"
            f"Proposal: {binding['action_id']} · saved revision {binding['revision']}\n"
            f"Proposal SHA-256: {binding['proposal_sha256']}\n"
            f"Saved baseline: {binding['baseline']}\nProposed Title: {binding['replacement']}")
    if binding['pending_confirmations']:
        st.warning('Staging draft with pending factual confirmations.')
        for question in binding['pending_confirmations']:
            st.text(question)


def _results(status):
    replacement = status.binding['replacement'] if status.binding else PROPOSED
    st.markdown('**Durable attempt status**')
    st.text(f'Journal: {status.journal or "No app attempt"}')
    for label, attempt in (('Apply', status.forward), ('Restore', status.restore)):
        st.text(f'{label}: {attempt["outcome"] if attempt else "Not attempted"}')
    st.markdown('**Raw-state observations**')
    for label, attempt in (('Apply', status.forward), ('Restore', status.restore)):
        if not attempt:
            continue
        if result := attempt['result']:
            st.text(f'{label} readback: {_title(result["actual"], replacement)}')
        for obs in sorted(attempt['observations'], key=lambda value: value['observed_utc']):
            description = obs['observation'].replace('_', ' ')
            st.text(f'{label} recovery: {description} · {_title(obs["actual"], replacement)}'
                    + (f' · {obs["reason"].replace("_", " ")}' if obs['reason'] else ''))
    st.markdown('**Rendered verification**')
    if not status.rendered:
        st.caption('No rendered comparison recorded.')
    for report in status.rendered:
        with st.expander(report['capture'] + ' · ' + report['report']):
            if not report['pages']:
                st.caption('Incomplete rendered evidence is retained.')
            for page in report['pages']:
                st.text(f'{page["page"]} · Literal: {page["literal"].replace("_", " ")} · '
                        f'Raw checks: {page["raw_checks"]}/{page["declared_raw_checks"]} matched')
    st.markdown('**Restoration status**')
    if status.verified:
        st.success('Restoration verified against both rendered pages and the original raw Title.')
    else:
        st.caption('Restoration verification pending.' if status.restore else 'Restoration has not been attempted.')


def _actions(status, store, sid, *, selection=None):
    prefix = f'{sid}:local-title-rehearsal:{selection}:'
    if message := st.session_state.pop(prefix + 'error', None):
        st.error(message)

    for phase, label in ACTIONS:
        if phase == 'forward' and selection is None:
            continue
        active = status.action[:1] == (phase,)
        if st.button(label, key=prefix + phase + ':' + status.revision, disabled=not active):
            try:
                app_control.execute(status.action, status.revision, store=store, sid=sid, selection=selection)
            except ValueError as exc:
                st.session_state[prefix + 'error'] = str(exc)
            st.rerun()


def _change_lifecycle(action, pair, store, sid, message_key):
    if st.session_state.get('selected_site', sid) != sid:
        return
    try:
        lifecycle.execute(action, pair, store=store, sid=sid)
    except lifecycle.LifecycleError as exc:
        st.session_state[message_key] = str(exc)


def _lifecycle(store, sid):
    message_key = f'{sid}:local-title-rehearsal:lifecycle-message'
    if message := st.session_state.pop(message_key, None):
        st.error(message)
    try:
        pair = lifecycle.inspect(store=store, sid=sid)
    except lifecycle.LifecycleError as exc:
        st.warning(str(exc))
        return

    db = 'running' if pair.db.state == 'running' else 'stopped'
    app = 'running' if pair.app.state == 'running' else 'stopped'
    st.caption(f'Local database: {db} · Local app: {app}')
    if pair.db.state != pair.app.state:
        st.warning('Local staging is partially running. Review the database and app states before continuing.')
    if 'db' in pair.unready:
        st.warning('The local database is running but its socket did not respond.')
    if 'app' in pair.unready:
        st.warning('The local renderer is running but its socket did not respond. Stop local staging before starting it again.')
    if pair.shutdown_fenced:
        st.warning('The local app is fenced for shutdown. Select Stop local staging again to finish stopping the pair.')
    for action, label, available in (
        ('start', 'Start local staging', pair.can_start),
        ('stop', 'Stop local staging', pair.can_stop),
    ):
        st.button(label, key=f'{sid}:local-title-rehearsal:{action}', disabled=not available,
                  on_click=_change_lifecycle, args=(action, pair, store, sid, message_key))


def render(store, sid):
    st.subheader('Disposable local WordPress rehearsal')
    st.caption('Select a saved revision in Recommendations & changes to start a rehearsal. Use this view to recover or restore an existing run.')
    st.text(f'{PROJECT} · page 716 · Title · widget 022c973\n{HOME + PATHS[0]}')
    _lifecycle(store, sid)
    _effects()
    status = app_control.inspect(store=store, sid=sid)
    _runtime(status, status.binding['replacement'] if status.binding else PROPOSED)
    if status.binding:
        _binding(status.binding)
    _results(status)
    _actions(status, store, sid)


def _capture_panel(phase, capture, sections):
    st.markdown(f'**{phase}**')
    if isinstance(capture, str):
        st.warning('Unavailable. ' + capture)
        return
    try:
        title, observations, document = static_capture_document(capture.source, sections)
    except ValueError:
        st.warning('Unavailable. The captured HTML could not be rendered as a static page.')
        return
    st.caption('Captured ' + capture.checked + ' · ' + capture.verification)
    st.text('Document title\n' + (title or 'Unavailable'))
    for label, value in observations.items():
        st.text(label + '\n' + value)
    st.iframe(preview_frame(document), height=870, alt=f'{phase} static WordPress capture')


@st.fragment
def _capture_comparison(store, sid, selection):
    key = f'{sid}:local-title-captures:{selection[0]}:{selection[1]}:'
    panel = st.expander('Compare saved WordPress captures', key=key + 'open', on_change='rerun')
    if not panel.open:
        return
    with panel:
        try:
            runs = capture_review.available_runs(store, sid, selection)
            if not runs:
                st.info('No retained runs with a verified workspace and proposal binding.')
                return
            labels = {item.name: f'{item.name} · {"Historical" if item.historical else "Current"} revision {item.revision}'
                      for item in runs}
            run_name = st.selectbox('Rehearsal run', list(reversed(labels)), format_func=labels.get, key=key + 'run')
            page = st.selectbox('Captured local page', PATHS, key=key + 'page')
            view = st.radio('Capture view', ('Compare all', *capture_review.PHASES), horizontal=True, key=key + 'view')
            result = capture_review.load_comparison(store, sid, selection, run_name, page)
        except capture_review.CaptureUnavailable as exc:
            st.warning(str(exc))
            return
        st.text(HOME + page)
        st.caption('Static view of captured local content. Site styling, images and interactive behavior are omitted. '
                   'This view does not verify mobile behavior, the live site or production compatibility.')
        sections = {'Page heading': HEADING, 'Breadcrumb': BREADCRUMB} if page == PATHS[0] else {'Page heading': CONTACT_HEADING}
        sections.update({'Header navigation label': LITERAL_NAVIGATION[0], 'Footer navigation label': LITERAL_NAVIGATION[2]})
        if view in capture_review.PHASES:
            _capture_panel(view, result[view], sections)
            return
        st.caption('Select Before, Staged or Restored for a full-width page capture.')
        st.html(CAPTURE_COMPARISON_STYLE)
        with st.container(key=f'rehearsal-capture-layout-{selection[0]}-{selection[1]}'):
            for phase, column in zip(capture_review.PHASES, st.columns(3)):
                with column:
                    _capture_panel(phase, result[phase], sections)


def render_proposal(store, sid, record):
    if not enabled(store, sid):
        return
    if sid == proposal_binding.PRIVATE_SITE and record['action_id'] != proposal_binding.PRIVATE_ACTION:
        return
    selection = (record['audit_id'], record['action_id'], record['revision'])
    with st.expander('Rehearse this proposal on local staging'):
        _capture_comparison(store, sid, selection)
        status = app_control.inspect(store=store, sid=sid, selection=selection)
        st.caption('Apply uses the saved revision. Save form changes as a new revision first. Rehearsal evidence is for isolated Docker only.')
        if status.proposal_blocker:
            st.warning(status.proposal_blocker)
        replacement = status.binding['replacement'] if status.binding else CURRENT
        if status.proposal:
            _binding(status.proposal)
            mapping = status.proposal['mapping']
            st.text(f"{mapping['project']} · page {mapping['page_id']} · Title · widget {mapping['widget_id']}\n"
                    + mapping['destination_url'])
            _effects()
        _runtime(status, replacement)
        for previous in reversed(status.history):
            binding = previous.binding
            current = (binding['revision'] == record['revision'] and
                       binding['proposal_sha256'] == proposal_binding.digest(record['payload']))
            label = 'Current saved revision' if current else 'Historical revision'
            with st.expander(f"{label} {binding['revision']} · {previous.journal}", expanded=current):
                _binding(binding)
                _results(previous)
        _actions(status, store, sid, selection=selection)
