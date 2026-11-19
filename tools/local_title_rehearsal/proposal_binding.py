"""The sole saved-proposal route into the disposable Title rehearsal."""
import os
from pathlib import Path
import re

from seo_agent import proposal_review, tracking
from seo_agent.config import SiteConfig
from seo_agent.storage import checked_id
from seo_agent.tracking import digest

from .locator import STABLE_ROOT
from .runtime import PROJECT, need
from .scope import CURRENT, HOME, PATHS, validate_replacement


SOURCE_HOME = 'https://psychology-a.example/'
PRIVATE_HOME = 'https://meadowandmindpsychology.com/'
PRIVATE_SITE = '5368d3688f6c423d8dc14b121e54b092'
PRIVATE_ACTION = '2dc230f4589047b2a1055267662650dd'
PRIVATE_WORKSPACE = STABLE_ROOT.parents[1]
DEMO_WORKSPACE = Path(__file__).resolve().parents[2]/'workspace'/'demo'
REGISTERED_DEMO_WORKSPACE = STABLE_ROOT/'validation'/'demo'
PRIVATE_PROFILE = ('psychology', '1.0')
MAPPING = {
    'source_url': SOURCE_HOME.rstrip('/') + PATHS[0],
    'source_kind': 'text',
    'project': PROJECT,
    'destination_url': HOME + PATHS[0],
    'page_id': 716,
    'field': 'post_title',
    'widget_id': '022c973',
}
PRIVATE_MAPPING = {**MAPPING, 'source_url': PRIVATE_HOME.rstrip('/') + PATHS[0]}


def workspace_digest(path):
    return digest(os.path.normcase(str(path)))


def source_scope(store, sid):
    """Identify a journal owner before consulting the mutable proposal/profile."""
    if os.environ.get('SEO_DEMO') == '0':
        if (sid == PRIVATE_SITE and store.root == PRIVATE_WORKSPACE and store.enforce_protection and
                (store.initial_protection or {}).get('verified') is True):
            config = store.site(sid)
            if config.url == config.gsc_property == PRIVATE_HOME:
                return {'mode': 'private', 'workspace_sha256': workspace_digest(store.root)}
        return None
    if (os.environ.get('SEO_DEMO') != '1' or store.enforce_protection or
            store.root not in (DEMO_WORKSPACE, REGISTERED_DEMO_WORKSPACE)):
        return None
    config = store.site(sid)
    if (config.name == 'Demo psychology A' and config.url == config.gsc_property == SOURCE_HOME and
            all(site['id'] == sid or store.site(site['id']).url != SOURCE_HOME for site in store.sites())):
        return {'mode': 'demo', 'workspace_sha256': workspace_digest(store.root)}
    return None


def owns_binding(binding, sid, scope):
    if binding is None:
        return scope['mode'] == 'demo'
    # Journals written before private support used the demo-only mapping.
    owner = binding.get('source')
    return binding['site_id'] == sid and (owner == scope or (owner is None and scope['mode'] == 'demo'))


def saved_source(store, sid, selection):
    """Resolve the selected revision from storage, never the proposal form."""
    scope = source_scope(store, sid)
    need(scope, 'This site has no validated local Title mapping.')
    aid, identity, revision = selection
    config = store.site(sid)
    mapping = MAPPING
    if scope['mode'] == 'private':
        need(identity == PRIVATE_ACTION, 'This proposal is outside the private local Title binding.')
        audit_config = SiteConfig.model_validate_json(store.audit(sid, aid)['config'])
        need(all((profile.url, profile.gsc_property, profile.industry, profile.profile_version) ==
                 (PRIVATE_HOME, PRIVATE_HOME, *PRIVATE_PROFILE) for profile in (config, audit_config)),
             'The selected site or audit profile differs from the private local Title binding.')
        mapping = PRIVATE_MAPPING
    record = tracking.action(store, sid, identity, revision)
    latest = next(row for row in tracking.actions(store, sid) if row['action_id'] == identity)
    need(record['audit_id'] == aid and latest['revision'] == revision,
         'Select the current saved proposal revision in its original audit.')
    value = record['payload']
    heading = value.get('manual_post_title') or {}
    need((value['url'], value['action_kind']) == (mapping['source_url'], mapping['source_kind']) and
         (heading.get('page_id'), heading.get('widget_id')) == (mapping['page_id'], mapping['widget_id']),
         'This proposal requires the explicit Post Title mapping for page 716 and Elementor widget 022c973 on the mapped page.')
    need(value['current'] == CURRENT, 'The saved proposal baseline differs from the supported local Title.')
    validate_replacement(value['proposed'])
    tracking.validate_action(store, sid, aid, value)
    confirmed = {c['item'] for c in value['confirmations'] if c['status'] == 'confirmed' and c['source']}
    return {
        'site_id': sid, 'audit_id': aid, 'action_id': identity, 'revision': revision,
        'proposal_sha256': digest(value), 'mapping': dict(mapping), 'source': scope,
        'profile_sha256': digest(proposal_review.profile(config)),
        'baseline': value['current'], 'replacement': value['proposed'],
        'pending_confirmations': sorted(set(proposal_review.required_questions(store, sid, record)) - confirmed),
    }


def validate_binding(binding):
    """Validate frozen evidence without consulting a potentially newer proposal."""
    legacy_fields = {
        'site_id', 'audit_id', 'action_id', 'revision', 'proposal_sha256', 'mapping', 'baseline',
        'replacement', 'pending_confirmations', 'destination_sha256', 'writer_epoch', 'scope_sha256',
        'baseline_captures_sha256',
    }
    fields = set(binding)
    need(fields in (legacy_fields, legacy_fields | {'source', 'profile_sha256'}),
         'Invalid rehearsal proposal binding')
    mapping = MAPPING
    if 'source' in binding:
        source = binding['source']
        need(isinstance(source, dict) and set(source) == {'mode', 'workspace_sha256'} and
             source['mode'] in ('demo', 'private') and _is_digest(source['workspace_sha256']) and
             _is_digest(binding['profile_sha256']), 'Invalid rehearsal source binding')
        if source['mode'] == 'private':
            need(binding['site_id'] == PRIVATE_SITE and binding['action_id'] == PRIVATE_ACTION and
                 source['workspace_sha256'] == workspace_digest(PRIVATE_WORKSPACE),
                 'Invalid private rehearsal source binding')
            mapping = PRIVATE_MAPPING
    for key in ('site_id', 'audit_id', 'action_id'):
        checked_id(binding[key])
    for key in ('proposal_sha256', 'destination_sha256', 'writer_epoch', 'scope_sha256', 'baseline_captures_sha256'):
        need(_is_digest(binding[key]), 'Invalid rehearsal proposal digest')
    need(digest(binding['mapping']) == digest(mapping) and binding['baseline'] == CURRENT and
         type(binding['revision']) is int and 1 <= binding['revision'] <= 100 and
         isinstance(binding['pending_confirmations'], list) and
         all(isinstance(question, str) for question in binding['pending_confirmations']),
         'Invalid rehearsal proposal mapping or baseline')
    validate_replacement(binding['replacement'])
    return binding


def _is_digest(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value)
