"""Explicit Hosting & CMS actions for the existing fixed disposable rehearsal."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from subprocess import SubprocessError

from seo_agent.coordination import BusyError, run_lock
from seo_agent.local_title_rehearsal import inspect_attempt, require_observed_replacement
from seo_agent.protection import ProtectionError, require_protected
from . import run
from .runtime import need
from .scope import CURRENT, HOME, PATHS, PROPOSED


@dataclass
class Status:
    containers: dict = field(default_factory=dict)
    journal: str = ''
    forward: dict | None = None
    restore: dict | None = None
    rendered: list = field(default_factory=list)
    verified: bool = False
    title: str | None = None
    isolation: bool = False
    preflight: bool = False
    action: tuple = ()
    revision: str = ''
    blocker: str = ''


def _root():
    return run.RUNTIME_PRIVATE/'app-rehearsals'


def _read(path):
    return json.loads(path.read_bytes())


def _attempt(directory, name):
    expected, replacement = (CURRENT, PROPOSED) if name == 'forward' else (PROPOSED, CURRENT)
    return inspect_attempt(directory, name, expected=expected, replacement=replacement)


def _restored(directory, runtime):
    path = directory/'restoration-verified.json'
    if not path.is_file():
        return False
    try:
        value = _read(path)
        return (value['runtime'] == runtime and value['raw_title_exact'] is True and
                value['baseline_volume_manifests_unchanged'] is True and
                value['baseline_containers_unchanged'] is True and
                value['pages'] == [{'path': path, 'exact_restoration': True} for path in PATHS])
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _prior_rehearsals_settled(backend, runtime):
    # PR #28's completed rehearsal, PR #29's restored interruption, and its
    # fenced interruption before dispatch all share this exact destination.
    # The first completed run predates writer provenance, so it contributes
    # its final baseline verification, never authority to recover or restore.
    require_observed_replacement(backend, run.JOURNAL, 'restore', expected=PROPOSED, replacement=CURRENT)
    need(all(_restored(directory, runtime) for directory in (run.PRIVATE, run.JOURNAL)),
         'Earlier restoration evidence is incomplete')
    before_save = run.RUNTIME_PRIVATE/'interruption-evidence'/'before-save-journal'
    pending = _attempt(before_save, 'forward')
    observations = {obs['observation'] for obs in pending['observations'] if obs['actual'] is not None}
    need(pending['outcome'] == 'interrupted' and observations == {'original_value_observed'} and
         all(obs['destination'] == backend.bound_destination for obs in pending['observations']) and
         _attempt(before_save, 'restore') is None and _restored(before_save, runtime),
         'Earlier interruption evidence is incomplete')


def _journals(root):
    if not root.exists():
        return []
    journals = sorted(root.iterdir())
    need(all(path.is_dir() and path.name == f'run-{index:06d}'
             for index, path in enumerate(journals, 1)),
         'Unexpected app rehearsal history; preserve it and inspect the journal')
    return journals


def _rendered(path):
    if not path.is_file():
        return None
    try:
        result = []
        for index, page in enumerate(_read(path)['pages']):
            checks = page['publication_effects']
            literal = page['literal_title_effects']['status']
            need(index < len(PATHS) and page['url'] == HOME + PATHS[index] and
                 len(checks) == (8, 7)[index] and literal in ('matches_expectation', 'failed'),
                 'Incomplete rendered report')
            result.append({
                'page': PATHS[index], 'literal': literal,
                'raw_checks': sum(check['status'] == 'matches_expectation' for check in checks),
                'declared_raw_checks': len(checks),
            })
        need(len(result) == len(PATHS), 'Incomplete rendered report')
        return {'report': path.name, 'pages': result}
    except (OSError, ValueError, KeyError, TypeError):
        # An interrupted comparison must not hide or gate raw-state actions.
        return {'report': path.name, 'pages': []}


def _journal_status(directory, runtime, status):
    status.journal = directory.name
    status.forward = _attempt(directory, 'forward')
    status.restore = _attempt(directory, 'restore')
    need(not status.restore or (status.forward and status.forward['replacement_observed']),
         'Restoration history lacks an observed forward Title')
    reports = ('before-to-after-verification.json', 'after-to-restored-verification.json')
    status.rendered.extend({'capture': 'Forward and restoration captures', **report} for name in reports
                           if (report := _rendered(directory/name)) is not None)
    for verification in sorted(p for p in directory.glob('verification-*') if p.is_dir()):
        paired = [_rendered(verification/name) for name in reports]
        # The backend writes the final raw and baseline evidence after both comparisons.
        complete = _restored(verification, runtime) and all(
            report and report['pages'] and all(
                page['literal'] == 'matches_expectation' and page['raw_checks'] == page['declared_raw_checks']
                for page in report['pages']) for report in paired)
        status.verified |= complete
        label = 'Restoration verification ' + verification.name
        status.rendered.extend({'capture': label, **report} for report in paired if report is not None)
        if not complete:
            status.rendered.append({'capture': label, 'report': 'Completion evidence', 'pages': []})
    need(not status.verified or (status.restore and status.restore['replacement_observed']),
         'Restoration verification lacks an observed restoration')


def _probe(backend, status):
    # Bind and verify the mounted app before booting WordPress for probes.
    backend.destination()
    run.verify_historical_config()
    for filename in ('wp-config.php', 'isolation.php'):
        expected = (run.OLD/filename).read_text().replace('18717', '18718').replace(
            'meadow-representative-20261021-d0f5a2ec', 'title-rehearsal-20261117')
        need((run.RUNTIME_PRIVATE/filename).read_text() == expected, 'Local isolation source differs from the reviewed copy')
    need(run.WRITER.read_text() == (run.HERE/'save-title.php').read_text(), 'Mounted title writer differs from this app revision')
    status.isolation = True
    run.retained_baseline()
    run.load_scope()
    captures = _read(run.PRIVATE/'before-captures.json')['pages']
    need([page['url'] for page in captures] == [HOME + path for path in PATHS], 'Fixed baseline capture URLs differ')
    for index, capture in enumerate(captures):
        for kind in ('raw', 'sanitized'):
            raw = (run.PRIVATE/f'before-{index}-{kind}.html').read_bytes()
            need(sha256(raw).hexdigest() == capture[f'{kind}_sha256'], 'Retained baseline capture digest differs')
    run.check_preflight()
    status.preflight = True
    status.title, epoch = backend.read_state()
    return epoch


def _available(status, epoch, next_run):
    forward, restore = status.forward, status.restore
    if forward is None or status.verified:
        if status.title == CURRENT:
            status.action = ('forward',)
            return next_run if status.verified or not status.journal else status.journal
        status.blocker = 'A new rehearsal requires the exact original raw Title.'
    elif restore is None and forward['replacement_observed']:
        if status.title == PROPOSED:
            status.action = ('restore',)
        else:
            status.blocker = 'An intervening raw Title blocks restoration.'
    elif restore and restore['replacement_observed']:
        if status.title == CURRENT:
            status.action = ('verify',)
        else:
            status.blocker = 'An intervening raw Title blocks restoration verification.'
    else:
        attempt = restore if restore else forward
        if not attempt['recoverable']:
            status.blocker = 'Recorded state cannot establish a verified restoration. Preserve this journal for review.'
        elif any(obs['app_epoch'] == epoch for obs in attempt['observations']):
            status.blocker = 'The writer generation is still running. Recovery requires a fenced disposable app generation.'
        else:
            status.action = ('recover', 'restore' if restore else 'forward')
            if attempt['writer_epoch'] == epoch:
                status.blocker = 'Recovery can record an unresolved observation. It requires a different writer generation to confirm raw state.'
    return status.journal


def _inspect(status, backend):
    runtime = _read(run.RUNTIME_PRIVATE/'running-isolation.json')
    status.containers = {role: runtime[role]['id'] for role in ('app', 'db')}
    journals = _journals(_root())
    if journals:
        for earlier in journals[:-1]:
            previous = Status()
            _journal_status(earlier, runtime, previous)
            need(previous.verified, 'An earlier app rehearsal is unresolved')
        _journal_status(journals[-1], runtime, status)
    epoch = _probe(backend, status)
    _prior_rehearsals_settled(backend, runtime)
    # Reuse the same destination and historical observation guard that gates
    # verification before enabling a subsequent run.
    if status.verified:
        require_observed_replacement(backend, journals[-1], 'restore', expected=PROPOSED, replacement=CURRENT)
    target = _available(status, epoch, f'run-{len(journals) + 1:06d}')
    if status.action:
        # Include the original displayed target and app generation. Durable
        # attempt files also stop duplicates whose events arrive during a rerun.
        ledger = [(p.name, sha256(p.read_bytes()).hexdigest())
                  for p in sorted((_root()/target).glob('*.json'))
                  if p.name.startswith(('forward-', 'restore-'))]
        verifications = sorted(p.name for p in (_root()/target).glob('verification-*'))
        status.revision = sha256(repr((target, status.action, epoch, ledger, verifications)).encode()).hexdigest()
    return _root()/target


def inspect():
    status = Status()
    try:
        require_protected(run.RUNTIME_PRIVATE)
        with run_lock(run.RUNTIME_PRIVATE/'.title-operation.lock', create=False):
            _inspect(status, run.Backend())
    except BusyError:
        status.blocker = 'Another local title controller is active.'
    except ProtectionError as exc:
        status.blocker = str(exc)
    except (ValueError, RuntimeError) as exc:
        # ValueError may carry raw JSON/Pydantic data. Only known operator
        # messages from the fixed checks may cross the app boundary.
        status.blocker = _safe_blocker(exc)
    except (OSError, SubprocessError, KeyError, TypeError):
        status.blocker = 'Retained rehearsal files or Docker evidence are unavailable.'
    if not status.revision:
        status.action = ()
    return status


def _safe_blocker(exc):
    message = str(exc)
    if ('\n' not in message and re.match(
            r'^(Docker inspection unavailable|Disposable Docker service (app|db) |'
            r'Another local title controller|Wrong image or runtime user$|Network exposure$|'
            r'Unsafe capabilities$|Host namespace$|Unexpected mounts$|Shared or wrong volume$|Unexpected bind$|'
            r'Disposable runtime identity differs|Mounted (source differs|title writer differs)|'
            r'Current runtime differs|Local isolation source differs|Historical reviewed configuration drift|'
            r'Local service preflight command failed|Historical options screen rejected|'
            r'Passing retained preflight required|Historical baseline differs|Baseline must remain stopped|'
            r'Expected an existing empty signing option|Unexpected (rewrite rule destination|time format)|'
            r'Invalid representative heading data|Ambiguous representative heading source|Heading does not use expected|'
            r'Earlier (restoration|interruption) evidence is incomplete|'
            r'An earlier app rehearsal is unresolved|An intervening Title|'
            r'Declared rendered effect failed|Restoration verification (failed|incomplete)|'
            r'Title state unresolved|Forward save not confirmed|Restoration not confirmed|Raw Title restored|'
            r'Local WordPress title command returned|The rehearsal changed)', message)):
        return message
    return 'Local rehearsal validation failed. Inspect the retained runtime, scope and journal evidence.'


def execute(action, revision):
    """Recalculate the action under the shared lock before calling the CLI phase."""
    try:
        require_protected(run.RUNTIME_PRIVATE)
        with run_lock(run.RUNTIME_PRIVATE/'.title-operation.lock', create=False):
            status = Status()
            backend = run.Backend()
            journal = _inspect(status, backend)
            need(status.action and (action, revision) == (status.action, status.revision),
                 'The rehearsal changed or is blocked. Review the current state before acting.')
            if action == ('forward',):
                journal.mkdir(parents=True, exist_ok=True)
                require_protected(journal)
            run.run_phase(action, backend, journal)
    except BusyError:
        raise ValueError('Another local title controller is active.') from None
    except ProtectionError:
        raise
    except (ValueError, RuntimeError) as exc:
        raise ValueError(_safe_blocker(exc)) from None
    except (OSError, SubprocessError, KeyError, TypeError):
        raise ValueError('Retained rehearsal files or Docker evidence are unavailable.') from None
