"""Hosting & CMS controls for the explicitly enabled synthetic rehearsal."""
import streamlit as st

from tools.local_title_rehearsal import app_control
from tools.local_title_rehearsal.runtime import PROJECT
from tools.local_title_rehearsal.scope import CURRENT, HOME, PATHS, PROPOSED


ACTIONS = (
    ('forward', 'Apply fixed synthetic Title'),
    ('recover', 'Recover interrupted attempt'),
    ('restore', 'Restore original Title'),
    ('verify', 'Verify restoration'),
)


def _title(value):
    if value is None:
        return 'Unavailable'
    return value if value in (CURRENT, PROPOSED) else 'Unexpected raw Title'


def render(sid):
    prefix = sid + ':local-title-rehearsal:'
    st.subheader('Disposable local WordPress rehearsal')
    st.caption('One fixed page and synthetic Title in isolated Docker. Live publication is unavailable here.')
    st.text(f'{PROJECT} · page 716\n{HOME + PATHS[0]}')
    st.text(f'Original Title: {CURRENT}\nFixed synthetic Title: {PROPOSED}')
    with st.expander('Declared effects on two pages'):
        st.text(f'{PATHS[0]}\nChange dynamic H1, breadcrumb, document title and four navigation labels.')
        st.text(f'{PATHS[1]}\nChange four shared navigation labels. Preserve H1 and document title.')
        st.caption('The four labels are header item 771 and footer item 801 in their main and dropdown menus. '
                   'Raw publication checks bind visible navigation destinations. Canonical, robots metadata and '
                   'X-Robots-Tag must match the baseline on both pages.')

    status = app_control.inspect()
    for role, identity in status.containers.items():
        st.text(f'Retained {role} container: {identity}')
    st.caption(f'Isolation: {"verified" if status.isolation else "unavailable"} · '
               f'Preflight: {"passed" if status.preflight else "unavailable"}')
    if status.blocker:
        st.warning(status.blocker)
    if message := st.session_state.pop(prefix + 'error', None):
        st.error(message)

    st.markdown('**Durable attempt status**')
    st.text(f'Journal: {status.journal or "No app attempt"}')
    for label, attempt in (('Apply', status.forward), ('Restore', status.restore)):
        st.text(f'{label}: {attempt["outcome"] if attempt else "Not attempted"}')
    st.markdown('**Raw-state observations**')
    st.text('Current stored Title: ' + _title(status.title))
    for label, attempt in (('Apply', status.forward), ('Restore', status.restore)):
        if not attempt:
            continue
        if result := attempt['result']:
            st.text(f'{label} readback: {_title(result["actual"])}')
        for obs in sorted(attempt['observations'], key=lambda value: value['observed_utc']):
            description = obs['observation'].replace('_', ' ')
            st.text(f'{label} recovery: {description} · {_title(obs["actual"])}'
                    + (f' · {obs["reason"].replace("_", " ")}' if obs['reason'] else ''))
    st.markdown('**Rendered verification**')
    if not status.rendered:
        st.caption('No rendered comparison recorded.')
    for report in status.rendered:
        with st.expander(report['capture'] + ' · ' + report['report']):
            for page in report['pages']:
                st.text(f'{page["page"]} · Literal: {page["literal"].replace("_", " ")} · '
                        f'Raw checks: {page["raw_checks"]}/{page["declared_raw_checks"]} matched')
    if status.verified:
        st.success('Restoration verified against both rendered pages and the original raw Title.')

    for phase, label in ACTIONS:
        active = status.action[:1] == (phase,)
        if st.button(label, key=prefix + phase + ':' + status.revision, disabled=not active):
            try:
                app_control.execute(status.action, status.revision)
            except ValueError as exc:
                st.session_state[prefix + 'error'] = str(exc)
            st.rerun()
