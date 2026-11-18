"""One-time operator command for the recovered November 17 Title rehearsal."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
from types import SimpleNamespace

from seo_agent.coordination import BusyError, run_lock
from seo_agent.local_title_rehearsal import forward_binding, require_observed_replacement
from seo_agent.protection import ProtectionError, require_protected
from seo_agent.storage import private_location, utc_now

from . import app_control, run, runtime
from .locator import (
    ACTIVE_FILES, ACTIVE_JOURNALS, OPERATION_LOCK, REGISTRATION, REVIEWED_FILES, REVIEWED_TOOLS, SECRETS, STABLE_ROOT,
    SUPPORTED_SOURCE, RuntimeRegistrationError, checked_path, file_digest, validate_supported_source,
)
from .proposal_binding import digest, validate_binding
from .scope import CURRENT, PROPOSED, expected_scope


RECOVERED = Path.home()/'.codex/worktrees/e369/local-seo-agent'
RECOVERED_EVIDENCE = RECOVERED/'.tmp/title-rehearsal-20261117'
RECOVERED_WRITER = RECOVERED/'tools/local_title_rehearsal/save-title.php'
PROPOSAL_EVIDENCE = runtime.HISTORICAL/'.tmp/proposal-rehearsal-397b86a-evidence'
REVIEWED_HEAD = '397b86af42f889087174a1c3a15dbae24273df83'


def read(path):
    return json.loads(checked_path(path).read_bytes())


def inventory(root, *, omit_operation_lock=False):
    result = {}
    pending = [checked_path(root, directory=True)]
    while pending:
        for path in sorted(pending.pop().iterdir()):
            if omit_operation_lock and path == root/OPERATION_LOCK:
                continue
            if path.is_symlink() or not path.is_dir():
                result[path.relative_to(root).as_posix()] = file_digest(path)
            else:
                pending.append(checked_path(path, directory=True))
    return result


def copy_verified(sources, root):
    """Exclusive copies into an already protected, inactive directory."""
    checked_path(root, directory=True)
    for name, (source, expected) in sorted(sources.items()):
        relative = Path(name)
        runtime.need(relative.as_posix() == name and not relative.is_absolute() and not relative.drive
                     and relative.parts and '..' not in relative.parts and ':' not in name,
                     'Unexpected migration path')
        target = root / relative
        checked_path(source)
        parent = root
        for component in relative.parts[:-1]:
            parent /= component
            parent.mkdir(exist_ok=True)
            checked_path(parent, directory=True)
        with source.open('rb') as original, target.open('xb') as copy:
            shutil.copyfileobj(original, copy)
        runtime.need(file_digest(target) == file_digest(source) == expected, 'Migration copy digest mismatch')


def historical_runtime():
    return runtime.inspect_runtime(private=RECOVERED_EVIDENCE, writer=RECOVERED_WRITER, require_running=False)


def same_runtime(observed, recorded):
    # Docker mount order is immaterial to identity. The historical digest still
    # uses the exact saved order and serialization from the old controller.
    def sorted_mounts(pair):
        return {role: {**data, 'mounts': sorted(data['mounts'], key=lambda item: item['Destination'])}
                for role, data in pair.items()}
    return sorted_mounts(observed) == sorted_mounts(recorded)


def require_stopped(project, pair):
    for role in ('app', 'db'):
        item = runtime.inspect_docker('container', 'inspect', project+'-'+role)
        runtime.need(item['Id'] == pair[role]['id'] and item['State']['Status'] == 'exited',
                     'Expected rehearsal container is absent or unsettled')


def reconcile_archives(old):
    history = RECOVERED_EVIDENCE
    hashes = [file_digest(path) for path in (RECOVERED_WRITER, history/'wp-config.php', history/'isolation.php')]
    old_identity = run.destination_digest(old, hashes)
    old_destination = SimpleNamespace(destination=lambda: old_identity, bound_destination=old_identity)
    app_control._prior_rehearsals_settled(old_destination, old, history)

    # This run predates destination/epoch journaling. Its two final readbacks
    # and completed verification are historical evidence only.
    completed = history/'credential-screening-resume'
    sanitation = read(completed/'sanitization-reconciliation.json')
    runtime.need(all(sanitation.get(key) is True for key in ('row_present', 'empty', 'option_api_agrees')),
                 'Retained signing-option operation is unsettled')
    for name, start, end in (('forward', CURRENT, PROPOSED), ('restore', PROPOSED, CURRENT)):
        attempt = read(completed/f'{name}-attempt.json')
        result = read(completed/f'{name}-result.json')
        runtime.need((attempt['expected'], attempt['replacement'], attempt['outcome']) == (start, end, 'attempted')
                     and (result['outcome'], result['actual'], result['write_attempted']) == ('applied', end, True),
                     'Legacy rehearsal title write is unsettled')

    journals = app_control._journals(history/ACTIVE_JOURNALS)
    runtime.need([directory.name for directory in journals] == ['run-000001', 'run-000002'],
                 'Expected two retained app rehearsal journals')
    for directory in journals:
        status = app_control.Status()
        app_control._journal_status(directory, old, status)
        replacement = validate_binding(status.binding)['replacement'] if status.binding is not None else PROPOSED
        for name, start, end in (('forward', CURRENT, replacement), ('restore', replacement, CURRENT)):
            require_observed_replacement(old_destination, directory, name, expected=start, replacement=end)
        runtime.need(status.verified, 'Retained app rehearsal lacks verified restoration')

    summary = read(PROPOSAL_EVIDENCE/'summary.json')
    journal = journals[-1]
    binding = validate_binding(forward_binding(journal))
    runtime.need(summary['tested_commit'] == REVIEWED_HEAD and summary['journal'] == journal.name and
                 summary['restoration_verified'] is True and summary['wordpress_mutations'] == 2 and
                 summary['forward_actual'] == binding['replacement'] and summary['restore_actual'] == CURRENT and
                 summary['proposal_binding_sha256'] == digest(binding) and
                 summary['journal_sha256'] == inventory(journal) == inventory(PROPOSAL_EVIDENCE/journal.name),
                 'Saved-proposal evidence does not match the recovered journal')
    return old_identity


def inspect_inputs():
    root = STABLE_ROOT
    checked_path(root.parent, directory=True)
    runtime.need(root == private_location(root) and not os.path.lexists(root),
                 'Stable runtime destination already exists or is unsafe; preserve it for review')
    require_protected(root.parent)
    checked_path(RECOVERED_EVIDENCE, directory=True)
    require_protected(RECOVERED_EVIDENCE)
    checked_path(PROPOSAL_EVIDENCE, directory=True)
    require_protected(PROPOSAL_EVIDENCE)
    checked_path(runtime.SECRETS, directory=True)
    require_protected(runtime.SECRETS)
    validate_supported_source('save-title.php', RECOVERED_WRITER)
    reviewed = runtime.verify_historical_config()
    for name in ('wp-config.php', 'isolation.php'):
        old = checked_path(runtime.OLD/name).read_text()
        expected = old.replace('18717', '18718').replace(
            'meadow-representative-20261021-d0f5a2ec', 'title-rehearsal-20261117')
        runtime.need(checked_path(RECOVERED_EVIDENCE/name).read_text() == expected,
                     'Recovered isolation source differs from the reviewed copy')

    sources = {}
    for archive, source in (('old', RECOVERED_EVIDENCE), ('saved-proposal', PROPOSAL_EVIDENCE)):
        # The old lock is a synchronization primitive, not a journal. Windows
        # denies a second handle's read of its byte while this process holds it.
        for name, value in inventory(source, omit_operation_lock=(source == RECOVERED_EVIDENCE)).items():
            sources[f'history/{archive}/{name}'] = (source/name, value)
    for name in ('wp-config.php', 'isolation.php'):
        source = RECOVERED_EVIDENCE/name
        sources[name] = (source, file_digest(source))
    for name in SUPPORTED_SOURCE:
        source = RECOVERED_WRITER if name == 'save-title.php' else runtime.HERE/name
        validate_supported_source(name, source)
        sources[name] = (source, file_digest(source))
    for name in REVIEWED_FILES:
        source = runtime.OLD/name
        runtime.need(file_digest(source) == reviewed[name], 'Historical reviewed configuration drift')
        sources[f'{REVIEWED_TOOLS}/{name}'] = (source, reviewed[name])
    for name in SECRETS:
        source = runtime.SECRETS/name
        runtime.need(checked_path(source).stat().st_size > 0, 'Required local secret file is empty')
        sources[f'secrets/{name}'] = (source, file_digest(source))
    runtime.need(all(len(str(root/name).encode('utf-16-le')) // 2 < 260 for name in sources),
                 'Migration files exceed the Windows protected-storage path limit')

    # Container startup must not create a missing volume or attach to another writer.
    runtime.verify_disposable_volumes()
    runtime.require_exclusive_volumes()
    retained = read(RECOVERED_EVIDENCE/'running-isolation.json')
    runtime.need(same_runtime(historical_runtime(), retained), 'Recovered runtime differs from its recorded identity or binds')
    require_stopped(runtime.PROJECT, retained)
    names = runtime.docker('ps', '-a', '--filter', 'name=^/'+runtime.STABLE_PROJECT+'-', '--format', '{{.Names}}')
    runtime.need(not names.strip(), 'Replacement container name is already in use')
    old_destination = reconcile_archives(retained)
    baseline = runtime.inspect_baseline()
    clone_record = read(RECOVERED_EVIDENCE/'clone.json')
    runtime.need(baseline == clone_record['baseline'], 'Historical baseline differs from the retained clone record')
    return sources, retained, old_destination, baseline, clone_record


def start_pair(pair):
    app, db = pair['app']['id'], pair['db']['id']
    runtime.docker('start', db)
    until = time.monotonic() + 45
    while time.monotonic() < until:
        ready = runtime.local_docker('exec', db, 'mysqladmin', '--socket=/run/lseo-db/mysql.sock',
                                     'ping', '--silent', capture_output=True, timeout=10)
        if ready.returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeRegistrationError('Disposable database did not become ready.')
    runtime.docker('start', app)
    until = time.monotonic() + 20
    while time.monotonic() < until:
        ready = runtime.local_docker('exec', app, 'test', '-S', '/run/lseo-http/app.sock',
                                     capture_output=True, timeout=10)
        if ready.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeRegistrationError('Disposable renderer did not become ready.')


def stop_pair(pair):
    for role in ('app', 'db'):
        container_id = pair[role]['id']
        item = runtime.inspect_docker('container', 'inspect', container_id)
        if item['State']['Running']:
            runtime.docker('stop', container_id)


def observe_original(pair):
    response = run.title_command(pair['app']['id'], {'operation': 'read'})
    runtime.need(response['status'] == 'read' and response['write_attempted'] is False and response['title'] == CURRENT,
                 'The original raw Title is not restored; preserve the current runtime for reconciliation')
    return {'observed_utc': utc_now(), 'title': response['title'], 'writer_epoch': response['epoch']}


def observe_recovered(pair, old_destination):
    try:
        start_pair(pair)
        runtime.need(same_runtime(historical_runtime(), pair), 'Historical runtime changed during reconciliation')
        runtime.require_exclusive_volumes(*(item['id'] for item in pair.values()))
        hashes = run.verify_runtime_mounts(pair, RECOVERED_EVIDENCE, RECOVERED_WRITER, runtime.SECRETS, historical=True)
        runtime.need(run.destination_digest(pair, hashes) == old_destination, 'Recovered destination changed')
        return observe_original(pair)
    finally:
        stop_pair(pair)


def register(data):
    # A failed or interrupted registration never leaves a usable marker.
    pending = STABLE_ROOT/(REGISTRATION+'.pending')
    with pending.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    pending.rename(STABLE_ROOT/REGISTRATION)  # Windows rename refuses an existing destination.


def migrate():
    root = STABLE_ROOT
    checked_path(RECOVERED_EVIDENCE/OPERATION_LOCK)
    with run_lock(RECOVERED_EVIDENCE/OPERATION_LOCK, create=False):
        # Hold the old controller lock through reconciliation and activation;
        # the old app must be stopped before starting the replacement pair.
        sources, old, old_destination, baseline, clone_record = inspect_inputs()
        old_observation = observe_recovered(old, old_destination)
        require_stopped(runtime.PROJECT, old)
        runtime.require_exclusive_volumes()

        root.mkdir(exist_ok=False)
        require_protected(root)
        copy_verified(sources, root)
        run.PRIVATE.mkdir()
        (root/ACTIVE_JOURNALS).mkdir()
        with (root/OPERATION_LOCK).open('xb') as lock:
            lock.write(b'0')
        require_protected(root)
        runtime.create_services(runtime.STABLE_PROJECT, root, root/'save-title.php', root/'secrets')
        replacement = runtime.inspect_runtime(private=root, writer=root/'save-title.php', secrets=root/'secrets',
                                              project=runtime.STABLE_PROJECT, require_running=False)
        run.record('replacement-created', {'observed_utc': utc_now(), 'runtime': replacement}, directory=root)
        runtime.need(not {item['id'] for item in old.values()} & {item['id'] for item in replacement.values()},
                     'Replacement must use new container identities')
        try:
            require_stopped(runtime.PROJECT, old)
            runtime.require_exclusive_volumes()
            start_pair(replacement)
            run.inspect_replacement(replacement, old)
            run.verify_runtime_mounts(replacement, root, root/'save-title.php', root/'secrets')
            fresh = observe_original(replacement)
            preflight = run.check_preflight(replacement)
            runtime.need(preflight['local_instance'] == 'title-rehearsal-20261117' and
                         str(preflight['blog_public']) == '0' and all(preflight.get(key) is True for key in (
                             'http_intercepted', 'mail_intercepted', 'jobs_intercepted',
                             'signing_option_empty', 'post_title_binding_verified')),
                         'Fresh local preflight did not pass')
            run.record('preflight', preflight)
            run.record('baseline-title', {**fresh, 'proposed': PROPOSED, 'runtime': replacement, 'baseline': baseline})
            run.capture('before', runtime=replacement)
            run.record('scope', expected_scope(run.baseline_document_titles()))
            for index in range(2):
                name = f'before-{index}-sanitized.html'
                runtime.need(file_digest(run.PRIVATE/name) ==
                             file_digest(root/'history/old/credential-screening-resume'/name),
                             'Fresh rendered baseline differs from the restored historical baseline')
            runtime.need(observe_original(replacement)['title'] == CURRENT, 'Fresh baseline raw Title changed')
        finally:
            stop_pair(replacement)
        require_stopped(runtime.STABLE_PROJECT, replacement)
        require_stopped(runtime.PROJECT, old)
        runtime.require_exclusive_volumes()
        runtime.need(runtime.inspect_baseline() == baseline and
                     runtime.clone('manifest', diagnostic_dir=root, tool=root/'clone-volumes.py') ==
                     clone_record['source_manifest'], 'Stopped historical baseline changed')

        history = {name: value for name, (_, value) in sources.items() if name.startswith('history/')}
        runtime.need(all(file_digest(root/name) == file_digest(source) == value
                         for name, (source, value) in sources.items()), 'Migration evidence changed during verification')
        require_protected(root)
        register({
            'version': 1, 'root': str(root), 'observed_utc': utc_now(), 'prior_tested_head': REVIEWED_HEAD,
            'migration_code_sha256': {name: file_digest(runtime.HERE/name) for name in
                                      ('migrate.py', 'locator.py', 'runtime.py', 'run.py', 'app_control.py')},
            'retired_runtime': old, 'replacement_runtime': replacement, 'historical_baseline': baseline,
            'old_destination_sha256': old_destination, 'old_raw_observation': old_observation,
            'active_sha256': {name: file_digest(root/name) for name in sorted(ACTIVE_FILES)},
            'history_sha256': history,
            'provenance': {name: str(source) for name, (source, _) in sources.items()},
            'validation': {
                'original_title_restored': True, 'historical_evidence_preserved': True, 'private_storage_verified': True,
                'fresh_preflight_and_two_rendered_baselines_passed': True,
                'old_and_replacement_stopped_at_registration': True, 'historical_volume_manifests_unchanged': True,
            },
        })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'migrate'))
    args = parser.parse_args()
    try:
        if args.action == 'check':
            inspect_inputs()
            print('Recovered journals, local Docker resources and migration inputs checked. No services started.')
        else:
            migrate()
            print('Stable Title rehearsal registered. Both disposable pairs are stopped.')
    except (RuntimeRegistrationError, ProtectionError, BusyError) as exc:
        parser.exit(1, str(exc) + '\n')
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(1, f'Migration stopped at {type(exc).__name__}. Inspect existing resources and private evidence.\n')
