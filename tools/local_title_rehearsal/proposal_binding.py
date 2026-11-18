"""The sole saved-proposal route into the disposable Title rehearsal."""
import re

from seo_agent import proposal_review, tracking
from seo_agent.storage import checked_id
from seo_agent.tracking import digest

from .runtime import PROJECT, need
from .scope import CURRENT, HOME, PATHS, validate_replacement


SOURCE_HOME = 'https://psychology-a.example/'
MAPPING = {
    'source_url': SOURCE_HOME.rstrip('/') + PATHS[0],
    'source_kind': 'text',
    'project': PROJECT,
    'destination_url': HOME + PATHS[0],
    'page_id': 716,
    'field': 'post_title',
    'widget_id': '022c973',
}


def mapped_site(store, sid):
    config = store.site(sid)
    return (config.name == 'Demo psychology A' and config.url == config.gsc_property == SOURCE_HOME and
            all(site['id'] == sid or store.site(site['id']).url != SOURCE_HOME for site in store.sites()))


def saved_source(store, sid, selection):
    """Resolve the selected revision from storage, never the proposal form."""
    need(mapped_site(store, sid), 'This site has no validated local Title mapping.')
    aid, identity, revision = selection
    record = tracking.action(store, sid, identity, revision)
    latest = next(row for row in tracking.actions(store, sid) if row['action_id'] == identity)
    need(record['audit_id'] == aid and latest['revision'] == revision,
         'Select the current saved proposal revision in its original audit.')
    value = record['payload']
    heading = value.get('manual_post_title') or {}
    need((value['url'], value['action_kind']) == (MAPPING['source_url'], MAPPING['source_kind']) and
         (heading.get('page_id'), heading.get('widget_id')) == (MAPPING['page_id'], MAPPING['widget_id']),
         'This proposal requires the explicit Post Title mapping for page 716 and Elementor widget 022c973 on the mapped page.')
    need(value['current'] == CURRENT, 'The saved proposal baseline differs from the supported local Title.')
    validate_replacement(value['proposed'])
    tracking.validate_action(store, sid, aid, value)
    confirmed = {c['item'] for c in value['confirmations'] if c['status'] == 'confirmed' and c['source']}
    return {
        'site_id': sid, 'audit_id': aid, 'action_id': identity, 'revision': revision,
        'proposal_sha256': digest(value), 'mapping': dict(MAPPING),
        'baseline': value['current'], 'replacement': value['proposed'],
        'pending_confirmations': sorted(set(proposal_review.required_questions(store, sid, record)) - confirmed),
    }


def validate_binding(binding):
    """Validate frozen evidence without consulting a potentially newer proposal."""
    need(set(binding) == {
        'site_id', 'audit_id', 'action_id', 'revision', 'proposal_sha256', 'mapping', 'baseline',
        'replacement', 'pending_confirmations', 'destination_sha256', 'writer_epoch', 'scope_sha256',
        'baseline_captures_sha256',
    }, 'Invalid rehearsal proposal binding')
    for key in ('site_id', 'audit_id', 'action_id'):
        checked_id(binding[key])
    for key in ('proposal_sha256', 'destination_sha256', 'writer_epoch', 'scope_sha256', 'baseline_captures_sha256'):
        need(isinstance(binding[key], str) and re.fullmatch(r'[a-f0-9]{64}', binding[key]),
             'Invalid rehearsal proposal digest')
    need(digest(binding['mapping']) == digest(MAPPING) and binding['baseline'] == CURRENT and
         type(binding['revision']) is int and 1 <= binding['revision'] <= 100 and
         isinstance(binding['pending_confirmations'], list) and
         all(isinstance(question, str) for question in binding['pending_confirmations']),
         'Invalid rehearsal proposal mapping or baseline')
    validate_replacement(binding['replacement'])
    return binding
