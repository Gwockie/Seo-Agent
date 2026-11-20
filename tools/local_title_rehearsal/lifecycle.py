"""Explicit app controls for the registered disposable WordPress pair."""
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import re
from sqlite3 import OperationalError
import subprocess
import time

from seo_agent.coordination import BusyError, run_lock
from seo_agent.protection import ProtectionError

from . import app_control, run, runtime
from .locator import OPERATION_LOCK, RuntimeRegistrationError, require_registered


class LifecycleError(ValueError):
    """Safe operator-facing lifecycle failure."""


@dataclass(frozen=True)
class Service:
    identity: str
    state: str
    started_at: str


@dataclass(frozen=True)
class Pair:
    app: Service
    db: Service
    unready: tuple[str, ...] = field(default=(), compare=False)
    shutdown_fenced: bool = field(default=False, compare=False)

    @property
    def can_start(self):
        return self.app.state == 'exited'

    @property
    def can_stop(self):
        return self.app.state == 'running' or self.db.state == 'running'


def _service(identity, role):
    item = runtime.inspect_docker('container', 'inspect', identity)
    state = item['State']
    if item['Id'] != identity or state['Status'] not in ('exited', 'running') or (
            state['Running'] != (state['Status'] == 'running') or
            any(state[flag] for flag in ('Paused', 'Restarting', 'Dead'))):
        raise LifecycleError(f'The registered {role} is in an unsupported Docker state. Check Docker Desktop.')
    return Service(identity, state['Status'], state['StartedAt'])


def _pair(registration):
    pair = run.inspect_replacement(registration['replacement_runtime'], registration['retired_runtime'],
                                   require_running=False)
    runtime.verify_disposable_volumes()
    return Pair(**{role: _service(pair[role]['id'], role) for role in ('app', 'db')})


def _checked():
    return require_registered(run.RUNTIME_PRIVATE)


def _lock():
    return run_lock(run.RUNTIME_PRIVATE / OPERATION_LOCK, create=False)


def inspect(*, store, sid):
    """Inspect without changing container state, loading WordPress or writing journals."""
    with _operator_errors():
        app_control._source_scope(store, sid)
        _checked()
        with _lock():
            pair = _pair(_checked())
            unready = tuple(
                role for role in ('db', 'app')
                if (service := getattr(pair, role)).state == 'running' and not _ready(service, role)
            )
            fenced = pair.app.state == 'running' and _fence_state(pair.app.identity)[0]
            return replace(pair, unready=unready, shutdown_fenced=fenced)


READY_COMMAND = {
    'db': ('mysqladmin', '--socket=/run/lseo-db/mysql.sock', 'ping', '--silent'),
    'app': ('python3', '-c',
            'import socket; s = socket.socket(socket.AF_UNIX); s.settimeout(2); s.connect("/run/lseo-http/app.sock")'),
}


def _ready(service, role, *, timeout=5):
    try:
        result = runtime.local_docker('exec', service.identity, *READY_COMMAND[role],
                                      capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _wait(service, role, seconds):
    deadline = time.monotonic() + seconds
    while (remaining := deadline - time.monotonic()) > 0:
        if _ready(service, role, timeout=min(remaining, 5)):
            return
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    name = 'database' if role == 'db' else 'app renderer'
    raise LifecycleError(f'The local {name} did not become ready. Check the observed container states before retrying.')


def _change(action, service, role):
    # Let both services finish graceful shutdown without Docker sending SIGKILL.
    args = ('--timeout', '-1') if action == 'stop' else ()
    try:
        runtime.docker(action, *args, service.identity, timeout=55)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        raise LifecycleError(
            f'Docker could not confirm {action} for the local {role}. Check the observed states before acting again.'
        ) from None


def _start(pair, registration):
    if pair.db.state == 'exited':
        _change('start', pair.db, 'database')
    _wait(pair.db, 'db', 45)
    ready = _pair(registration)
    db_restarted = ready.db.started_at != pair.db.started_at
    if (ready.db.state != 'running' or ready.app != pair.app or
            db_restarted != (pair.db.state == 'exited')):
        raise LifecycleError('The registered pair changed during database startup. Review its current state.')
    _change('start', ready.app, 'app')
    _wait(ready.app, 'app', 20)
    started = _pair(registration)
    if (started.app.state != 'running' or started.app.started_at == ready.app.started_at or
            started.db != ready.db):
        raise LifecycleError('The registered pair changed during app startup. Review its current state.')


# Acquire the same lock as the Title writer and read-only inspection first.
# The second flock identifies a shutdown fence as distinct from an active writer.
# A detached fence survives lost Docker replies until this container generation exits.
APP_GENERATION = """
$boot = trim(file_get_contents('/proc/sys/kernel/random/boot_id'));
$stat = file_get_contents('/proc/1/stat');
$fields = explode(' ', substr($stat, strrpos($stat, ') ') + 2));
$started = $fields[19] ?? '';
if (!preg_match('/^[0-9a-f-]{36}$/D', $boot) || !ctype_digit($started)) { exit(1); }
$epoch = hash('sha256', $boot . ':' . $started);
"""
SHUTDOWN_FENCE = APP_GENERATION + """
if (($argv[1] ?? null) !== $epoch) { exit(1); }
$writer = fopen('/tmp/lseo-title-rehearsal.lock', 'c');
if (!$writer || !flock($writer, LOCK_EX | LOCK_NB)) { exit(1); }
$fence = fopen('/tmp/lseo-title-shutdown.lock', 'c');
if (!$fence || !flock($fence, LOCK_EX | LOCK_NB)) { exit(1); }
while (true) { sleep(60); }
"""
CHECK_FENCE = APP_GENERATION + """
$fence = @fopen('/tmp/lseo-title-shutdown.lock', 'r');
if (!$fence || flock($fence, LOCK_SH | LOCK_NB, $busy)) {
    echo 'unfenced ', $epoch;
} elseif ($busy) {
    echo 'fenced ', $epoch;
}
"""
PHP = ('php', '-d', 'display_errors=0', '-d', 'log_errors=0', '-r')


def _fence_state(identity):
    result = runtime.local_docker('exec', identity, *PHP, CHECK_FENCE, capture_output=True, timeout=5)
    match = re.fullmatch(rb'(fenced|unfenced) ([a-f0-9]{64})', result.stdout)
    if result.returncode or not match:
        raise LifecycleError('The local app shutdown fence could not be checked.')
    return match[1] == b'fenced', match[2].decode('ascii')


def _fence_writer(identity):
    fenced, epoch = _fence_state(identity)
    if fenced:
        return
    try:
        runtime.docker('exec', '-d', identity, *PHP, SHUTDOWN_FENCE, '--', epoch, timeout=5)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        raise LifecycleError('Docker could not confirm the local app shutdown fence. Review the state before retrying.') from None
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        fenced, observed_epoch = _fence_state(identity)
        if observed_epoch != epoch:
            raise LifecycleError('The app generation changed while checking for an active writer.')
        if fenced:
            return
        time.sleep(0.2)
    raise LifecycleError('Stop refused because the Title writer is active or could not be ruled out.')


def _stop(pair, registration):
    if pair.app.state == 'running':
        _fence_writer(pair.app.identity)
        if _service(pair.app.identity, 'app') != pair.app:
            raise LifecycleError('The app generation changed while checking for an active writer.')
        _change('stop', pair.app, 'app')
    stopped = _pair(registration)
    if stopped.app != Service(pair.app.identity, 'exited', pair.app.started_at) or stopped.db != pair.db:
        raise LifecycleError('The app stop or database generation could not be confirmed. Database stop withheld.')
    if stopped.db.state == 'running':
        _change('stop', stopped.db, 'database')
    stopped = _pair(registration)
    if stopped.can_stop:
        raise LifecycleError('Docker did not confirm that both registered services are stopped.')


@contextmanager
def _operator_errors():
    try:
        yield
    except BusyError:
        raise LifecycleError('Another local Title operation is active. Start or Stop can be retried after it finishes.') from None
    except (LifecycleError, ProtectionError, RuntimeRegistrationError) as exc:
        raise LifecycleError(str(exc)) from None
    except OperationalError:
        raise LifecycleError('The proposal workspace is busy or unavailable. Review the current state and retry.') from None
    except (OSError, KeyError, TypeError, subprocess.SubprocessError):
        raise LifecycleError('Docker or the protected runtime state is unavailable. Check Docker Desktop and the registration.') from None
    except (ValueError, RuntimeError) as exc:
        raise LifecycleError(app_control._safe_blocker(exc)) from None


def execute(action, shown, *, store, sid):
    """Revalidate the displayed pair under the shared lock before acting."""
    with _operator_errors():
        app_control._source_scope(store, sid)
        _checked()
        with _lock():
            app_control._source_scope(store, sid)
            store.require_private_write()
            registration = _checked()
            current = _pair(registration)
            if current != shown:
                raise LifecycleError('The local staging state changed. Review it before selecting Start or Stop again.')
            if action == 'start' and current.can_start:
                _start(current, registration)
            elif action == 'stop' and current.can_stop:
                _stop(current, registration)
            else:
                raise LifecycleError('This lifecycle action is unavailable in the current state.')
