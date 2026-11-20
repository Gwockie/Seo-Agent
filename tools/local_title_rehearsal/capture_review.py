"""Read-only resolution of saved proposal rehearsal captures."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re

from seo_agent import publication_verification as verification
from seo_agent import tracking
from seo_agent.local_title_rehearsal import inspect_attempt
from seo_agent.page_tracking import extract
from seo_agent.post_title_effects import MAX_CAPTURE_BYTES, TitleEffect, verify_title_effects
from seo_agent.protection import ProtectionError, require_protected
from . import app_control, proposal_binding, run
from .locator import ACTIVE_JOURNALS, BASELINE_DIR, RuntimeRegistrationError, _record_fields, checked_path, read_registration
from .scope import HOME, PATHS, expected_scope


PHASES = ('Before', 'Staged', 'Restored')
_RUN = re.compile(r'run-[0-9]{6}')
_PROPOSED = re.compile(r'proposed-capture-[a-f0-9]{32}')
# Mount digests in the registered app-then-db order used by verify_runtime_mounts.
_MOUNTS = ('save-title.php', 'wp-config.php', 'isolation.php', 'secrets/db-user',
           'secrets/wp-salts', 'secrets/db-root', 'secrets/db-user')


class CaptureUnavailable(ValueError):
    """A safe explanation for evidence that cannot be shown."""


@dataclass(frozen=True)
class SavedRun:
    name: str
    revision: int
    historical: bool


@dataclass(frozen=True)
class Capture:
    source: str
    checked: str
    verification: str


def _read(path, limit=MAX_CAPTURE_BYTES):
    with checked_path(path).open('rb') as stream:
        value = stream.read(limit + 1)
    if not 0 < len(value) <= limit:
        raise CaptureUnavailable('A retained evidence file is empty or exceeds the display limit.')
    return value


def _json(path):
    return json.loads(_read(path), object_pairs_hook=_record_fields)


def _utc(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() != timedelta(0):
        raise CaptureUnavailable('A retained evidence timestamp is missing its UTC offset.')
    return stamp


def _context(store, sid, selection):
    source = app_control._source_scope(store, sid)
    aid, action_id, revision = selection
    revisions = {row['revision']: row['payload'] for row in tracking.actions(store, sid, latest=False)
                 if (row['audit_id'], row['action_id']) == (aid, action_id)}
    if revision not in revisions or (source['mode'] == 'private' and action_id != proposal_binding.PRIVATE_ACTION):
        raise CaptureUnavailable('Select a saved proposal from this site and audit.')
    root = run.RUNTIME_PRIVATE
    checked_path(root, directory=True)
    require_protected(root)
    registration = read_registration(root)
    return source, revisions, root, registration


def _binding(directory, sid, selection, source, revisions, registration):
    checked_path(directory, directory=True)
    binding = _json(directory / 'forward-attempt.json').get('binding')
    # The pre-workspace-binding demo journal cannot establish workspace ownership.
    if not isinstance(binding, dict) or binding.get('source') != source or binding.get('site_id') != sid:
        return None
    if (binding.get('audit_id'), binding.get('action_id')) != selection[:2]:
        return None
    proposal_binding.validate_binding(binding)
    payload = revisions.get(binding['revision'])
    destination = run.destination_digest(registration['replacement_runtime'],
                                         [registration['active_sha256'][name] for name in _MOUNTS])
    if (not payload or tracking.digest(payload) != binding['proposal_sha256'] or
            (payload['current'], payload['proposed'], payload['url'], payload['action_kind']) !=
            (binding['baseline'], binding['replacement'], binding['mapping']['source_url'], 'text') or
            binding['destination_sha256'] != destination or
            binding['baseline_captures_sha256'] != registration['active_sha256'][f'{BASELINE_DIR}/before-captures.json']):
        raise CaptureUnavailable('The run differs from its saved proposal revision or registered destination.')
    return binding


def _attempt(directory, phase, binding):
    path = directory / f'{phase}-attempt.json'
    record = _json(path)
    if record['destination'] != binding['destination_sha256']:
        raise CaptureUnavailable('The attempted Title change refers to a different destination.')
    result = directory / f'{phase}-result.json'
    if result.exists() or result.is_symlink():
        checked_path(result)
    for recovery in directory.glob(f'{phase}-recovery-*.json'):
        if not re.fullmatch(rf'{phase}-recovery-[a-f0-9]{{32}}\.json', recovery.name):
            raise CaptureUnavailable('Unexpected recovery record location.')
        checked_path(recovery)
    expected, replacement = binding['baseline'], binding['replacement']
    if phase == 'restore':
        expected, replacement = replacement, expected
    status = inspect_attempt(directory, phase, expected=expected, replacement=replacement)
    started = _utc(record['observed_utc'])
    result = status['result']
    settled = ([result] if result and result['outcome'] == 'applied' else [])
    if phase == 'forward':
        settled += [row for row in status['observations'] if row['observation'] == 'proposed_value_observed']
    times = [_utc(row['observed_utc']) for row in settled]
    if any(stamp < started for stamp in times):
        raise CaptureUnavailable('The recorded Title observation predates its attempt.')
    observed = min(times, default=None) if status['replacement_observed'] else None
    return started, observed


def available_runs(store, sid, selection):
    """List only direct, explicitly workspace-bound runs of this proposal."""
    try:
        source, revisions, root, registration = _context(store, sid, selection)
        history = []
        for directory in sorted((root / ACTIVE_JOURNALS).iterdir()):
            if not _RUN.fullmatch(directory.name):
                continue
            try:
                binding = _binding(directory, sid, selection, source, revisions, registration)
            except (ValueError, OSError, KeyError, TypeError, AttributeError, RecursionError):
                continue
            if binding:
                revision = binding['revision']
                history.append(SavedRun(directory.name, revision, revision != max(revisions)))
        return history
    except (ValueError, OSError, ProtectionError, KeyError, TypeError):
        raise CaptureUnavailable('Registered rehearsal history or the selected proposal is unavailable.') from None


def _staged_directory(journal):
    legacy_manifest = journal / 'after-captures.json'
    if legacy_manifest.exists() or legacy_manifest.is_symlink():
        raise CaptureUnavailable('A workspace-bound staged capture must be in its marked capture directory.')
    candidates = []
    for directory in journal.glob('proposed-capture-*'):
        if not _PROPOSED.fullmatch(directory.name):
            raise CaptureUnavailable('Unexpected staged capture location.')
        checked_path(directory, directory=True)
        marker = directory / 'capture-complete'
        if marker.exists() or marker.is_symlink():
            checked_path(marker)
            candidates.append(directory)
    if len(candidates) != 1:
        raise CaptureUnavailable('A single completed staged capture was not recorded for this run.')
    return candidates[0]


def _page(record, index):
    pages = record['pages']
    if not isinstance(pages, list) or [page['url'] for page in pages] != [HOME + path for path in PATHS]:
        raise CaptureUnavailable('The retained record does not identify both declared local pages in order.')
    return pages[index]


def _declaration(root, baseline, binding, index):
    name = f'{BASELINE_DIR}/scope.json'
    data = _read(root / name)
    if sha256(data).hexdigest() != baseline[name]:
        raise CaptureUnavailable('The registered page scope differs from its recorded digest.')
    scope = json.loads(data, object_pairs_hook=_record_fields)
    titles = [next(effect['before'] for effect in page['publication_effects'] if effect['kind'] == 'document_title')
              for page in scope['pages']]
    declared = expected_scope(titles, replacement=binding['replacement'])
    if tracking.digest(declared) != binding['scope_sha256']:
        raise CaptureUnavailable('The page scope differs from the saved proposal binding.')
    return declared['pages'][index]


def _report(journal, name, binding, index, effects, substitutions):
    report = _json(journal / name)
    if report.get('proposal_binding_sha256') != tracking.digest(binding):
        raise CaptureUnavailable('The verification record belongs to a different proposal binding.')
    page = _page(report, index)
    literal = page['literal_title_effects']
    checks = page['publication_effects']
    if literal['status'] != 'matches_expectation':
        raise CaptureUnavailable('The recorded literal check did not establish the exact capture digest.')
    if (set(literal) != {'status', 'before_sha256', 'after_sha256', 'substitutions'} or
            type(literal['substitutions']) is not int or literal['substitutions'] != substitutions):
        raise CaptureUnavailable('The recorded literal check is incomplete.')
    if not isinstance(checks, list) or [check.get('expectation') for check in checks] != effects:
        raise CaptureUnavailable('The recorded verification checks are incomplete.')
    return literal, checks


def _check_raw(raw, row, label, checks):
    html = raw.decode('utf-8')
    url, headers = row['url'], row['headers']
    payload = {'html': html, 'headers': headers, 'values': extract(html, url, headers),
               'http_status': row['http_status'], 'final_url': url, 'synthetic': True}
    snapshot = {'url': url, 'checked': row['checked'], 'status': 'complete', 'payload': json.dumps(payload)}
    _, source, reason = verification._capture(snapshot, label, url)
    if source is None:
        raise CaptureUnavailable('The retained raw capture is incomplete or ambiguous.')
    matched = 0
    for check in checks:
        effect = verification.Effect.model_validate(check['expectation'])
        observed = verification._observe(source, reason, effect)
        if (check['after'] != observed or
                verification._compare(effect, check['before'], observed, None) != check):
            raise CaptureUnavailable('The raw capture or status differs from the recorded checks.')
        matched += check['status'] == 'matches_expectation'
    return f'Literal check passed · {matched}/{len(checks)} recorded raw checks matched'


def _capture(directory, label, index, expected_sha, *, manifest_sha=None, checks=None,
             earliest=None, latest=None):
    manifest = _read(directory / f'{label}-captures.json')
    if manifest_sha and sha256(manifest).hexdigest() != manifest_sha:
        raise CaptureUnavailable('The baseline capture record differs from the registered digest.')
    row = _page(json.loads(manifest, object_pairs_hook=_record_fields), index)
    if row['http_status'] != 200:
        raise CaptureUnavailable('The captured response status is incomplete.')
    captured = _utc(row['checked'])
    if (earliest and captured < earliest) or (latest and captured > latest) or captured > datetime.now(timezone.utc):
        raise CaptureUnavailable('The capture timestamp is outside this run’s recorded phase.')
    if expected_sha != row['sanitized_sha256']:
        raise CaptureUnavailable('The capture reference differs from the independently recorded digest.')
    raw = _read(directory / f'{label}-{index}-raw.html')
    if sha256(raw).hexdigest() != row['raw_sha256']:
        raise CaptureUnavailable('The raw capture differs from its recorded digest.')
    sanitized = _read(directory / f'{label}-{index}-sanitized.html')
    if sha256(sanitized).hexdigest() != expected_sha:
        raise CaptureUnavailable('The sanitized capture differs from its recorded digest.')
    status = 'Registered baseline digest matched' if checks is None else _check_raw(raw, row, label, checks)
    return Capture(sanitized.decode('utf-8'), row['checked'], status)


def _phase(root, journal, registration, binding, index, phase):
    baseline = registration['active_sha256']
    before_digest = baseline[f'{BASELINE_DIR}/before-{index}-sanitized.html']
    started, forward_observed = _attempt(journal, 'forward', binding)
    if phase == 'Before':
        manifest_digest = baseline[f'{BASELINE_DIR}/before-captures.json']
        return _capture(root / BASELINE_DIR, 'before', index, before_digest,
                        manifest_sha=manifest_digest, latest=started)
    if not forward_observed:
        raise CaptureUnavailable('The run does not record an observed staged Title.')
    declaration = _declaration(root, baseline, binding, index)
    effects = declaration['publication_effects']
    literal_effects = [TitleEffect(**effect) for effect in declaration['title_effects']]
    substitutions = sum(effect.count for effect in literal_effects)
    forward, checks = _report(journal, 'before-to-after-verification.json', binding, index, effects, substitutions)
    if forward['before_sha256'] != before_digest:
        raise CaptureUnavailable('The staged capture record refers to a different baseline.')
    if phase == 'Staged':
        restore_path = journal / 'restore-attempt.json'
        ended = _utc(_json(restore_path)['observed_utc']) if restore_path.exists() else None
        capture = _capture(_staged_directory(journal), 'after', index, forward['after_sha256'],
                           checks=checks, earliest=forward_observed, latest=ended)
        before = _read(root / BASELINE_DIR / f'before-{index}-sanitized.html')
        if sha256(before).hexdigest() != before_digest:
            raise CaptureUnavailable('The retained baseline differs from the registered digest.')
        # Recheck the existing declaration against saved bytes. Only the recorded
        # staged HTML is returned to the renderer.
        try:
            verify_title_effects(before, capture.source.encode('utf-8'), current=binding['baseline'],
                                 proposed=binding['replacement'], effects=literal_effects)
        except ValueError:
            raise CaptureUnavailable('The staged capture differs from the recorded literal change.') from None
        return capture
    restored, restore_observed = _attempt(journal, 'restore', binding)
    if not restore_observed or restored < forward_observed:
        raise CaptureUnavailable('A confirmed Restore result is required for this direct capture.')
    reversed_effects = [{**effect, 'before': effect['after'], 'after': effect['before']} for effect in effects]
    reverse, reverse_checks = _report(journal, 'after-to-restored-verification.json',
                                      binding, index, reversed_effects, substitutions)
    if reverse['before_sha256'] != forward['after_sha256']:
        raise CaptureUnavailable('The restoration record refers to a different staged capture.')
    if reverse['after_sha256'] != before_digest:
        raise CaptureUnavailable('The passing restoration record differs from the registered baseline digest.')
    if any(left['after'] != right['before'] for left, right in zip(checks, reverse_checks)):
        raise CaptureUnavailable('The restoration checks refer to different staged observations.')
    return _capture(journal, 'restored', index, before_digest, checks=reverse_checks, earliest=restore_observed)


def load_comparison(store, sid, selection, run_name, page):
    """Reauthorize the selected run, then resolve each phase independently."""
    if not isinstance(run_name, str) or not _RUN.fullmatch(run_name) or page not in PATHS:
        raise CaptureUnavailable('Select a recorded run and one of its two declared pages.')
    try:
        source, revisions, root, registration = _context(store, sid, selection)
        journal = root / ACTIVE_JOURNALS / run_name
        binding = _binding(journal, sid, selection, source, revisions, registration)
    except (ValueError, OSError, ProtectionError, KeyError, TypeError, AttributeError, RecursionError):
        binding = None
    if binding is None:
        raise CaptureUnavailable('The run is unavailable for this site, workspace or saved proposal.')
    result = {}
    for phase in PHASES:
        try:
            result[phase] = _phase(root, journal, registration, binding, PATHS.index(page), phase)
        except (CaptureUnavailable, RuntimeRegistrationError) as exc:
            result[phase] = str(exc)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError, StopIteration):
            result[phase] = 'The capture or its verification record is missing or incomplete.'
    return result
