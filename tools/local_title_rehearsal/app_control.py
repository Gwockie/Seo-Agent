"""Explicit Hosting & CMS actions for the existing fixed disposable rehearsal."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from sqlite3 import OperationalError
from subprocess import SubprocessError

from seo_agent.coordination import BusyError, run_lock
from seo_agent.local_title_rehearsal import forward_binding, inspect_attempt, require_observed_replacement
from seo_agent.protection import ProtectionError, require_protected
from . import proposal_binding as proposals, run
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
    proposal: dict | None = None
    proposal_blocker: str = ''
    binding: dict | None = None
    pending_binding: dict | None = None
    history: list = field(default_factory=list)


def _root():
    return run.RUNTIME_PRIVATE/'app-rehearsals'


def _read(path):
    return json.loads(path.read_bytes())


def _attempt(directory, name, proposed=PROPOSED):
    expected, replacement = (CURRENT, proposed) if name == 'forward' else (proposed, CURRENT)
    return inspect_attempt(directory, name, expected=expected, replacement=replacement)


def _restored(directory, runtime, binding=None):
    path = directory/'restoration-verified.json'
    if not path.is_file():
        return False
    try:
        value = _read(path)
        return (value['runtime'] == runtime and value['raw_title_exact'] is True and
                value.get('proposal_binding_sha256') == run.binding_reference(binding).get('proposal_binding_sha256') and
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


def _rendered(path, binding=None):
    if not path.is_file():
        return None
    try:
        result = []
        value = _read(path)
        need(isinstance(value, dict) and
             value.get('proposal_binding_sha256') == run.binding_reference(binding).get('proposal_binding_sha256'),
             'Rendered report differs from the saved proposal binding')
        for index, page in enumerate(value['pages']):
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
    status.binding = forward_binding(directory)
    replacement = PROPOSED
    if status.binding is not None:
        replacement = proposals.validate_binding(status.binding)['replacement']
    status.forward = _attempt(directory, 'forward', replacement)
    status.restore = _attempt(directory, 'restore', replacement)
    need(not status.restore or (status.forward and status.forward['replacement_observed']),
         'Restoration history lacks an observed forward Title')
    reports = ('before-to-after-verification.json', 'after-to-restored-verification.json')
    status.rendered.extend({'capture': 'Forward and restoration captures', **report} for name in reports
                           if (report := _rendered(directory/name, status.binding)) is not None)
    for verification in sorted(p for p in directory.glob('verification-*') if p.is_dir()):
        paired = [_rendered(verification/name, status.binding) for name in reports]
        # The backend writes the final raw and baseline evidence after both comparisons.
        complete = _restored(verification, runtime, status.binding) and all(
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
        replacement = status.binding['replacement'] if status.binding is not None else PROPOSED
        if status.title == replacement:
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


def _same_proposal(binding, sid, selection):
    return (binding is not None and (binding['site_id'], binding['audit_id'], binding['action_id']) ==
            (sid, selection[0], selection[1]))


def _selected_proposal(status, store, sid, selection):
    if selection is not None:
        try:
            status.proposal = proposals.saved_source(store, sid, selection)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            status.proposal_blocker = _safe_blocker(exc)


def _inspect(status, backend, *, sid, selection):
    runtime = _read(run.RUNTIME_PRIVATE/'running-isolation.json')
    status.containers = {role: runtime[role]['id'] for role in ('app', 'db')}
    journals = _journals(_root())
    latest = Status()
    for directory in journals:
        latest = Status()
        _journal_status(directory, runtime, latest)
        if selection is not None and _same_proposal(latest.binding, sid, selection):
            status.history.append(latest)
        need(directory == journals[-1] or latest.verified, 'An earlier app rehearsal is unresolved')
    owns_run = latest.binding is None or latest.binding['site_id'] == sid
    shown = (owns_run if selection is None else _same_proposal(latest.binding, sid, selection))
    if shown:
        status.journal, status.binding = latest.journal, latest.binding
        status.forward, status.restore = latest.forward, latest.restore
        status.verified, status.rendered = latest.verified, latest.rendered
    if selection is not None and status.proposal is None and not shown:
        return None
    epoch = _probe(backend, status)
    _prior_rehearsals_settled(backend, runtime)
    # Reuse the same destination and historical observation guard that gates
    # verification before enabling a subsequent run.
    if latest.verified:
        replacement = latest.binding['replacement'] if latest.binding is not None else PROPOSED
        require_observed_replacement(backend, journals[-1], 'restore', expected=replacement, replacement=CURRENT)
    latest.title = status.title
    target = _available(latest, epoch, f'run-{len(journals) + 1:06d}')
    status.action, status.blocker = latest.action, latest.blocker
    if status.action == ('forward',):
        if status.proposal is None:
            status.action = ()
        else:
            binding = {**status.proposal, 'destination_sha256': backend.bound_destination, 'writer_epoch': epoch,
                       'baseline_captures_sha256': run.baseline_capture_digest(),
                       'scope_sha256': proposals.digest(run.proposal_scope(status.proposal['replacement']))}
            try:
                run.check_literal_replacement(binding)
            except ValueError as exc:
                status.action = ()
                status.proposal_blocker = _safe_blocker(exc)
            else:
                status.pending_binding = binding
    elif latest.journal and not latest.verified and not shown:
        status.action = ()
        status.blocker = 'Another rehearsal needs reconciliation before a new run. Open Hosting & CMS for its source site.'
    if status.action:
        # Include the original displayed target and app generation. Durable
        # attempt files also stop duplicates whose events arrive during a rerun.
        ledger = [(p.name, sha256(p.read_bytes()).hexdigest())
                  for p in sorted((_root()/target).glob('*.json'))
                  if p.name.startswith(('forward-', 'restore-'))]
        verifications = sorted(p.name for p in (_root()/target).glob('verification-*'))
        status.revision = proposals.digest([target, status.action, epoch, ledger, verifications, status.pending_binding])
    return _root()/target


def inspect(*, store, sid, selection=None):
    status = Status()
    try:
        need(proposals.mapped_site(store, sid), 'This site has no validated local Title mapping.')
        _selected_proposal(status, store, sid, selection)
        require_protected(run.RUNTIME_PRIVATE)
        with run_lock(run.RUNTIME_PRIVATE/'.title-operation.lock', create=False):
            _inspect(status, run.Backend(), sid=sid, selection=selection)
    except BusyError:
        status.blocker = 'Another local title controller is active.'
    except ProtectionError as exc:
        status.blocker = str(exc)
    except (ValueError, RuntimeError) as exc:
        # ValueError may carry raw JSON/Pydantic data. Only known operator
        # messages from the fixed checks may cross the app boundary.
        status.blocker = _safe_blocker(exc)
    except (OSError, SubprocessError, OperationalError, KeyError, TypeError):
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
            r'Local WordPress title command returned|The rehearsal changed|'
            r'This (site has no validated local Title mapping|proposal requires the explicit Post Title mapping)|'
            r'Select the current saved proposal revision|Action/revision does not belong to this site|'
            r'The saved proposal baseline differs|Unsupported local Title text)', message)):
        return message
    return 'Local rehearsal validation failed. Inspect the retained runtime, scope and journal evidence.'


def execute(action, revision, *, store, sid, selection=None):
    """Recalculate the action under the shared lock before calling the CLI phase."""
    try:
        need(proposals.mapped_site(store, sid), 'This site has no validated local Title mapping.')
        require_protected(run.RUNTIME_PRIVATE)
        with run_lock(run.RUNTIME_PRIVATE/'.title-operation.lock', create=False):
            status = Status()
            backend = run.Backend()
            _selected_proposal(status, store, sid, selection)
            journal = _inspect(status, backend, sid=sid, selection=selection)
            need(status.action and (action, revision) == (status.action, status.revision),
                 'The rehearsal changed or is blocked. Review the current state before acting.')
            if action == ('forward',):
                # Serialize the final source check and dispatch with saved revisions.
                store.require_private_write()
                with store.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    fresh = Status()
                    _selected_proposal(fresh, store, sid, selection)
                    need(fresh.proposal == status.proposal,
                         'The rehearsal changed before Apply. Review the saved revision and mapping.')
                    journal.mkdir(parents=True, exist_ok=True)
                    require_protected(journal)
                    run.run_phase(action, backend, journal, binding=status.pending_binding)
            else:
                run.run_phase(action, backend, journal)
    except BusyError:
        raise ValueError('Another local title controller is active.') from None
    except ProtectionError:
        raise
    except OperationalError:
        raise ValueError('The proposal workspace is busy or unavailable. Review the current rehearsal state.') from None
    except (ValueError, RuntimeError) as exc:
        raise ValueError(_safe_blocker(exc)) from None
    except (OSError, SubprocessError, KeyError, TypeError):
        raise ValueError('Retained rehearsal files or Docker evidence are unavailable.') from None
