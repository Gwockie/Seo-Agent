"""Proposal and Hosting & CMS controls for the opt-in disposable rehearsal."""
import os

import streamlit as st

from tools.local_title_rehearsal import app_control, proposal_binding
from tools.local_title_rehearsal.runtime import PROJECT
from tools.local_title_rehearsal.scope import CURRENT, HOME, PATHS, PROPOSED


ACTIONS = (
    ('forward', 'Apply saved Title'),
    ('recover', 'Recover interrupted attempt'),
    ('restore', 'Restore original Title'),
    ('verify', 'Verify restoration'),
)


def enabled():
    return (os.environ.get('SEO_DEMO') == '1' and os.environ.get('SEO_LOCAL_TITLE_REHEARSAL') == '1' and
            st.get_option('server.address') == '127.0.0.1')


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
    st.text(f"Source site: {binding['site_id']}\nAudit: {binding['audit_id']}\n"
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


def render(store, sid):
    st.subheader('Disposable local WordPress rehearsal')
    st.caption('Select a saved revision in Recommendations & changes to start a rehearsal. Use this view to recover or restore an existing run.')
    st.text(f'{PROJECT} · page 716 · Title · widget 022c973\n{HOME + PATHS[0]}')
    _effects()
    status = app_control.inspect(store=store, sid=sid)
    _runtime(status, status.binding['replacement'] if status.binding else PROPOSED)
    if status.binding:
        _binding(status.binding)
    _results(status)
    _actions(status, store, sid)


def render_proposal(store, sid, record):
    if not enabled():
        return
    selection = (record['audit_id'], record['action_id'], record['revision'])
    with st.expander('Rehearse this proposal on local staging'):
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
