"""Local evidence journal for a guarded save and readback; no production integration."""
import json
import os
from pathlib import Path
import re

from .storage import utc_now


def _record(path, value):
    # A pending attempt must survive a lost response or process interruption.
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump({'observed_utc': utc_now(), **value}, stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())


def transition(backend, directory, name, *, expected, replacement):
    """Attempt once, always reconcile by reading, never infer success from a reply.

    A second call with the same name is refused even after a crash. A later
    restoration uses a distinct name and checks its own exact expected title.
    The backend must independently enforce local isolation and expected state.
    """
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,50}', name):
        raise ValueError('Use a simple local attempt name')
    if (not isinstance(expected, str) or not isinstance(replacement, str) or
            expected == replacement or len(expected) > 500 or len(replacement) > 500):
        raise ValueError('Supply distinct bounded raw title strings')
    directory = Path(directory)
    attempt = directory / (name + '-attempt.json')
    result_path = directory / (name + '-result.json')
    if attempt.exists() or result_path.exists():
        raise ValueError('Attempt already recorded; reconcile actual state without retrying')
    observed = backend.read()
    if observed != expected:
        _record(result_path, {'outcome': 'conflict', 'expected': expected, 'actual': observed,
                              'write_attempted': False})
        return {'outcome': 'conflict', 'actual': observed, 'write_attempted': False}
    _record(attempt, {'expected': expected, 'replacement': replacement, 'outcome': 'attempted'})
    response = None
    error = None
    try:
        response = backend.save(expected=expected, replacement=replacement)
        if not isinstance(response, dict):
            response = None
            error = 'InvalidSaveResponse'
    except Exception as exc:
        # Never include raw exception messages (which can contain private output).
        error = type(exc).__name__
    try:
        actual = backend.read()
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
        # Even unchanged state after a lost response is uncertain: no blind retry.
        outcome = 'uncertain'
    result = {'outcome': outcome, 'actual': actual, 'response': response,
              'error_type': error, 'write_attempted': True}
    _record(result_path, result)
    return result
