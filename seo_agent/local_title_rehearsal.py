"""Local evidence journal for guarded title transitions and read-only recovery."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from .storage import new_id, utc_now


class DestinationMismatch(ValueError):
    """The runtime was reachable but failed the retained destination check."""


def _record(path, value):
    # Exclusive creation preserves history. A partial record blocks later use.
    with path.open('x', encoding='utf-8') as stream:
        json.dump({'observed_utc': utc_now(), **value}, stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())


def _unique_fields(items):
    value = dict(items)
    if len(value) != len(items):
        raise ValueError('Duplicate journal field')
    return value


def _load(path, fields):
    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=_unique_fields)
        if (not isinstance(value, dict) or set(value) != set(fields.split()) | {'observed_utc'} or
                datetime.fromisoformat(value['observed_utc']).utcoffset() != timedelta(0)):
            raise ValueError('Malformed record')
    except (OSError, ValueError, TypeError):
        raise ValueError(f'Invalid or missing {path.name}; preserve it and inspect the local journal') from None
    return value, sha256(raw).hexdigest()


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _title_pair(expected, replacement):
    if (not isinstance(expected, str) or not isinstance(replacement, str) or
            expected == replacement or len(expected) > 500 or len(replacement) > 500):
        raise ValueError('Supply distinct bounded raw title strings')


def _paths(directory, name):
    if name not in ('forward', 'restore'):
        raise ValueError('Choose the forward or restore attempt')
    directory = Path(directory)
    return directory / (name + '-attempt.json'), directory / (name + '-result.json')


def _state(backend):
    title, epoch = backend.read_state()
    if not isinstance(title, str) or not _digest(epoch):
        raise ValueError('Unusable raw title or app generation')
    return title, epoch


def transition(backend, directory, name, *, expected, replacement):
    """Attempt once and reconcile by reading. The CLI coordinates the caller lock."""
    attempt, result_path = _paths(directory, name)
    _title_pair(expected, replacement)
    if attempt.exists() or result_path.exists() or any(attempt.parent.glob(f'{name}-recovery-*.json')):
        raise ValueError('Attempt already recorded; reconcile actual state without retrying')
    if name == 'restore':
        require_observed_replacement(backend, directory, 'forward', expected=replacement, replacement=expected)
    elif any(attempt.parent.glob('restore-*.json')):
        raise ValueError('Restoration history exists; inspect the local journal before any forward operation')
    destination = backend.destination()
    if not _digest(destination):
        raise ValueError('Invalid local destination evidence')
    observed, writer_epoch = _state(backend)
    if observed != expected:
        result = {'outcome': 'conflict', 'expected': expected, 'actual': observed, 'write_attempted': False}
        _record(result_path, result)
        return result
    _record(attempt, {'expected': expected, 'replacement': replacement, 'outcome': 'attempted',
                      'destination': destination, 'writer_epoch': writer_epoch})
    attempt_digest = sha256(attempt.read_bytes()).hexdigest()
    response = None
    error = None
    try:
        response = backend.save(expected=expected, replacement=replacement, writer_epoch=writer_epoch)
        if not isinstance(response, dict):
            response = None
            error = 'InvalidSaveResponse'
    except Exception as exc:
        # Never include raw exception messages (which can contain private output).
        error = type(exc).__name__
    try:
        actual, _ = _state(backend)
    except Exception as exc:
        actual = None
        error = error or type(exc).__name__
    if actual == replacement:
        outcome = 'applied'
    elif response and response.get('status') == 'conflict':
        outcome = 'conflict'
    elif actual == expected and response and response.get('status') == 'failed':
        outcome = 'failed'
    else:
        outcome = 'uncertain'
    result = {'outcome': outcome, 'actual': actual, 'response': response, 'error_type': error,
              'write_attempted': True, 'attempt_sha256': attempt_digest}
    _record(result_path, result)
    return result


def _observation(actual, expected, replacement):
    if actual is None:
        return 'unavailable_or_unresolved'
    if actual == expected:
        return 'original_value_observed'
    if actual == replacement:
        return 'proposed_value_observed'
    return 'different_value_observed'


def _history(directory, name, expected, replacement):
    attempt_path, result_path = _paths(directory, name)
    _title_pair(expected, replacement)
    attempt, digest = _load(attempt_path, 'expected replacement outcome destination writer_epoch')
    if (attempt['outcome'] != 'attempted' or attempt['expected'] != expected or
            attempt['replacement'] != replacement or not _digest(attempt['destination']) or
            not _digest(attempt['writer_epoch'])):
        raise ValueError(f'{attempt_path.name} differs from the exact transition or lacks writer provenance')
    result = None
    if result_path.exists():
        result, _ = _load(result_path, 'outcome actual response error_type write_attempted attempt_sha256')
        if (result['attempt_sha256'] != digest or result['write_attempted'] is not True or
                result['outcome'] not in ('applied', 'conflict', 'failed', 'uncertain') or
                (result['actual'] is not None and not isinstance(result['actual'], str)) or
                (result['response'] is not None and (not isinstance(result['response'], dict) or
                 result['response'].get('status') not in ('returned', 'conflict', 'failed'))) or
                (result['error_type'] is not None and (not isinstance(result['error_type'], str) or
                 not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]{0,100}', result['error_type']))) or
                (result['response'] is None and result['error_type'] is None) or
                (result['outcome'] == 'applied') != (result['actual'] == replacement)):
            raise ValueError(f'{result_path.name} is inconsistent with the recorded attempt')
    observations = []
    for path in attempt_path.parent.glob(f'{name}-recovery-*.json'):
        obs, _ = _load(path, 'attempt_sha256 destination app_epoch observation actual reason')
        if (obs['attempt_sha256'] != digest or obs['destination'] != attempt['destination'] or
                (obs['actual'] is not None and not isinstance(obs['actual'], str)) or
                obs['observation'] != _observation(obs['actual'], expected, replacement) or
                (obs['actual'] is not None and
                 (not _digest(obs['app_epoch']) or obs['app_epoch'] == attempt['writer_epoch'] or
                  obs['reason'] is not None)) or
                (obs['actual'] is None and not (
                    (obs['app_epoch'] is None and obs['reason'] in ('destination_unavailable', 'read_unavailable')) or
                    (obs['app_epoch'] == attempt['writer_epoch'] and obs['reason'] == 'writer_generation_still_running')))):
            raise ValueError(f'{path.name} is inconsistent with the recorded attempt')
        observations.append(obs)
    return attempt, digest, result, observations


def recover(backend, directory, name, *, expected, replacement):
    """Observe raw state after the recorded writer generation is fenced off."""
    attempt, digest, _, _ = _history(directory, name, expected, replacement)
    destination = attempt['destination']
    title = epoch = reason = None
    try:
        current_destination = backend.destination()
    except DestinationMismatch:
        raise
    except (OSError, RuntimeError, ValueError):
        reason = 'destination_unavailable'
    else:
        if current_destination != destination:
            raise ValueError('Current runtime differs from the recorded destination; no title read performed')
        try:
            title, epoch = _state(backend)
        except DestinationMismatch:
            raise
        except (OSError, RuntimeError, ValueError):
            reason = 'read_unavailable'
        if epoch == attempt['writer_epoch']:
            # A locked read can still precede a delayed writer in this generation.
            title = None
            reason = 'writer_generation_still_running'
    value = {'attempt_sha256': digest, 'destination': destination, 'app_epoch': epoch,
             'observation': _observation(title, expected, replacement), 'actual': title, 'reason': reason}
    path = Path(directory) / f'{name}-recovery-{new_id()}.json'
    _record(path, value)
    return {**value, 'record': path.name}


def require_observed_replacement(backend, directory, name, *, expected, replacement):
    """Require exact destination and a confirmed or recovered replacement value."""
    attempt, _, result, observations = _history(directory, name, expected, replacement)
    if backend.destination() != attempt['destination']:
        raise ValueError(f'Current runtime differs from the recorded {name} destination')
    settled = {obs['observation'] for obs in observations if obs['actual'] is not None}
    eligible = (settled == {'proposed_value_observed'} if observations else
                result and result['outcome'] == 'applied')
    if not eligible:
        raise ValueError(f'A confirmed or recovered proposed Title is required; inspect the {name} journal')
