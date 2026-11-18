"""Explicit registration for the one supported disposable Title runtime."""
from hashlib import sha256
import json
from pathlib import Path
import re
import stat

from seo_agent.protection import require_protected
from seo_agent.storage import private_location


STABLE_ROOT = Path('C:/Personal Projects/seo-agent/local-seo-agent/workspace/private/local-staging/title-rehearsal')
REGISTRATION = 'migration-manifest.json'
OPERATION_LOCK = '.title-operation.lock'
BASELINE_DIR = 'baseline'
REVIEWED_TOOLS = 'reviewed-tools'
SUPPORTED_SOURCE = {
    'save-title.php': '33715681a9d4e8622221b5757fe2738b602545ed8ac2045c694fec7655b4101f',
    'preflight.php': '5a114294d65829c287871a3948940ee941a615671f9da508534c665903d7e8c1',
    'clone-volumes.py': '280451785dcbca7b4657f0573bc8b6aa61aff38023b5a5f33801e59a1495c2ec',
}
REVIEWED_FILES = ('preview_proxy.py', 'screen.py', 'inert_serialized.py')
CLONE_RECORD = 'history/old/clone.json'
SECRETS = ('db-root', 'db-user', 'wp-salts')
BASELINE_FILES = (
    'baseline-title.json', 'preflight.json', 'scope.json', 'before-captures.json',
    'before-0-raw.html', 'before-0-sanitized.html', 'before-1-raw.html', 'before-1-sanitized.html',
)
ACTIVE_FILES = frozenset((
    'wp-config.php', 'isolation.php', CLONE_RECORD, *SUPPORTED_SOURCE,
    *(f'secrets/{name}' for name in SECRETS),
    *(f'{REVIEWED_TOOLS}/{name}' for name in REVIEWED_FILES),
    *(f'{BASELINE_DIR}/{name}' for name in BASELINE_FILES),
))


class RuntimeRegistrationError(ValueError):
    """Validation failure with a safe operator-facing explanation."""


def checked_path(path, *, directory=False):
    """Reject aliases before resolving or reading the protected path."""
    if not path.is_absolute() or '..' in path.parts:
        raise RuntimeRegistrationError('Local rehearsal path must be absolute and direct.')
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            raise RuntimeRegistrationError(f'Local rehearsal file or directory is missing: {component.name}.') from None
        is_directory = component != path or directory
        valid_type = (stat.S_ISDIR if is_directory else stat.S_ISREG)(info.st_mode)
        if (not valid_type or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                or (not is_directory and info.st_nlink != 1)):
            raise RuntimeRegistrationError(f'Local rehearsal path is unsafe: {component.name}.')
    return path


def file_digest(path):
    return sha256(checked_path(path).read_bytes()).hexdigest()


def validate_supported_source(name, path):
    content = checked_path(path).read_bytes().replace(b'\r\n', b'\n')
    if sha256(content).hexdigest() != SUPPORTED_SOURCE[name]:
        raise RuntimeRegistrationError(f'Local rehearsal source is incompatible: {name}.')


def _record_fields(pairs):
    value = dict(pairs)
    if len(pairs) != len(value):
        raise ValueError('Duplicate registration field')
    return value


def load_registration(root):
    """Read the activation record and verify every active file. No discovery or writes."""
    checked_path(root, directory=True)
    if private_location(root) != root:
        raise RuntimeRegistrationError('Local rehearsal runtime path is not direct.')
    path = root / REGISTRATION
    if not path.exists():
        raise RuntimeRegistrationError('Local rehearsal runtime is unregistered or migration is incomplete.')
    checked_path(root / OPERATION_LOCK)
    try:
        data = json.loads(checked_path(path).read_bytes(), object_pairs_hook=_record_fields)
        files = data['active_sha256']
        runtime = data['replacement_runtime']
        replaced = data['retired_runtime']
        valid = (
            type(data['version']) is int and data['version'] == 1 and Path(data['root']) == root
            and set(files) == ACTIVE_FILES and set(runtime) == {'app', 'db'}
            and all(re.fullmatch(r'[0-9a-f]{64}', runtime[role]['id']) for role in ('app', 'db'))
            and set(replaced) == {'app', 'db'}
            and all(re.fullmatch(r'[0-9a-f]{64}', replaced[role]['id']) for role in ('app', 'db'))
            and len({item['id'] for pair in (runtime, replaced) for item in pair.values()}) == 4
            and data['validation']['original_title_restored'] is True
            and data['validation']['historical_evidence_preserved'] is True
            and data['validation']['private_storage_verified'] is True
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise RuntimeRegistrationError('Local rehearsal registration is invalid or incompatible.')
    for name, expected in sorted(files.items()):
        if file_digest(root / name) != expected:
            raise RuntimeRegistrationError(f'Local rehearsal file changed since registration: {name}.')
    for name in SUPPORTED_SOURCE:
        validate_supported_source(name, root / name)
    return data


def require_registered(root):
    checked_path(root, directory=True)
    if not (root / REGISTRATION).exists():
        raise RuntimeRegistrationError('Local rehearsal runtime is unregistered or migration is incomplete.')
    require_protected(root)
    return load_registration(root)
