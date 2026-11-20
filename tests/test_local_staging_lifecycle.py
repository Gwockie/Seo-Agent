from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from seo_agent.coordination import run_lock
from tools.local_title_rehearsal import lifecycle


FENCE_WRITER = lifecycle._fence_writer


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.lock = self.root / lifecycle.OPERATION_LOCK
        self.lock.write_bytes(b'0')
        self.journal = self.root / 'pending.json'
        self.journal.write_bytes(b'original pending outcome')
        self.store = Mock()
        self.sid = 'eligible-site'
        self.pair = lifecycle.Pair(
            app=lifecycle.Service('a' * 64, 'exited', 'prior-app-generation'),
            db=lifecycle.Service('b' * 64, 'exited', 'prior-db-generation'),
        )
        self.registration = {
            'replacement_runtime': {role: {'id': getattr(self.pair, role).identity} for role in ('app', 'db')},
            'retired_runtime': {'app': {'id': 'c' * 64}, 'db': {'id': 'd' * 64}},
        }
        self.events = []
        self.patch(lifecycle.run, 'RUNTIME_PRIVATE', self.root)
        self.scope = self.patch(lifecycle.app_control, '_source_scope', Mock())
        self.registration_check = self.patch(lifecycle, 'require_registered', Mock(return_value=self.registration))
        self.replacement_check = self.patch(lifecycle.run, 'inspect_replacement',
                                            Mock(return_value=self.registration['replacement_runtime']))
        self.volume_check = self.patch(lifecycle.runtime, 'verify_disposable_volumes', Mock())
        self.patch(lifecycle.runtime, 'inspect_docker', self.inspect_container)
        self.command = self.patch(lifecycle.runtime, 'docker', Mock(side_effect=self.docker))
        self.readiness = self.patch(lifecycle.runtime, 'local_docker', Mock(side_effect=self.probe))
        self.fence_state = self.patch(lifecycle, '_fence_state', Mock(return_value=(False, 'f' * 64)))
        self.writer = self.patch(lifecycle, '_fence_writer', Mock(side_effect=self.fence_writer))

    def patch(self, obj, name, value):
        patcher = patch.object(obj, name, value)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def inspect_container(self, kind, action, identity):
        self.assertEqual((kind, action), ('container', 'inspect'))
        service = next(service for service in (self.pair.app, self.pair.db) if service.identity == identity)
        return {'Id': identity, 'State': {
            'Status': service.state, 'Running': service.state == 'running', 'StartedAt': service.started_at,
            'Paused': False, 'Restarting': False, 'Dead': False,
        }}

    def docker(self, action, *args, timeout):
        identity = args[-1]
        role = next(role for role in ('app', 'db') if getattr(self.pair, role).identity == identity)
        self.events.append((action, role))
        self.assertEqual(args[:-1], ('--timeout', '-1') if action == 'stop' else ())
        if action == 'start':
            self.pair = replace(self.pair, **{role: lifecycle.Service(identity, 'running', f'new-{role}-epoch')})
        else:
            self.pair = replace(self.pair, **{role: replace(getattr(self.pair, role), state='exited')})

    def probe(self, action, identity, *_args, **_kwargs):
        self.assertEqual(action, 'exec')
        role = 'app' if identity == self.pair.app.identity else 'db'
        self.events.append(('ready', role))
        return Mock(returncode=0)

    def fence_writer(self, identity):
        self.assertEqual(identity, self.pair.app.identity)
        self.events.append(('guard', 'app'))

    def inspect(self):
        return lifecycle.inspect(store=self.store, sid=self.sid)

    def execute(self, action, shown=None):
        lifecycle.execute(action, shown or self.inspect(), store=self.store, sid=self.sid)

    def test_inspection_and_explicit_ordered_lifecycle(self):
        self.assertTrue(self.inspect().can_start)
        self.assertFalse(self.inspect().can_stop)
        self.assertEqual(self.events, [])
        self.execute('start')
        self.assertEqual(self.events, [('start', 'db'), ('ready', 'db'), ('start', 'app'), ('ready', 'app')])
        running = self.inspect()
        self.assertTrue(running.can_stop)
        self.assertFalse(running.can_start)
        self.events.clear()
        self.execute('stop', running)
        self.assertEqual(self.events, [('guard', 'app'), ('stop', 'app'), ('stop', 'db')])
        self.assertFalse(self.inspect().can_stop)
        self.assertEqual(self.journal.read_bytes(), b'original pending outcome')
        self.replacement_check.assert_called_with(self.registration['replacement_runtime'],
                                                  self.registration['retired_runtime'], require_running=False)
        self.volume_check.assert_called()

    def test_stale_generation_and_unauthorized_action_do_not_change_runtime(self):
        stale = self.inspect()
        self.pair = replace(self.pair, app=replace(self.pair.app, started_at='changed-generation'))
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'state changed'):
            self.execute('start', stale)
        self.scope.side_effect = ValueError('This site has no validated local Title mapping.')
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'no validated local Title mapping'):
            self.execute('start', self.pair)
        self.command.assert_not_called()

    def test_registration_and_storage_protection_are_required(self):
        self.registration_check.side_effect = lifecycle.RuntimeRegistrationError('Runtime registration unavailable.')
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'registration unavailable'):
            self.execute('start', self.pair)
        self.registration_check.side_effect = None
        self.store.require_private_write.side_effect = lifecycle.ProtectionError('Workspace protection unavailable.')
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'protection unavailable'):
            self.execute('start', self.pair)
        self.command.assert_not_called()

    def test_shared_lock_and_container_writer_both_block_stop(self):
        self.execute('start')
        self.command.reset_mock()
        running = self.inspect()
        with run_lock(self.lock, create=False):
            with self.assertRaisesRegex(lifecycle.LifecycleError, 'Another local Title operation'):
                self.execute('stop', running)
        self.writer.assert_not_called()
        self.writer.side_effect = lifecycle.LifecycleError('Title writer is active')
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'writer is active'):
            self.execute('stop', running)
        self.command.assert_not_called()

    def test_failed_start_leaves_an_observable_partial_state(self):
        def fail_app(action, *args, **kwargs):
            if args[-1] == self.pair.app.identity:
                raise RuntimeError('private Docker stderr')
            return self.docker(action, *args, **kwargs)

        self.command.side_effect = fail_app
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'could not confirm start for the local app'):
            self.execute('start')
        partial = self.inspect()
        self.assertEqual((partial.db.state, partial.app.state), ('running', 'exited'))
        self.assertTrue(partial.can_start)
        self.assertTrue(partial.can_stop)
        self.execute('stop', partial)
        self.assertEqual(self.events, [('start', 'db'), ('ready', 'db'), ('ready', 'db'), ('stop', 'db')])

    def test_database_readiness_failure_never_starts_app(self):
        with patch.object(lifecycle, '_wait', side_effect=lifecycle.LifecycleError('database did not become ready')):
            with self.assertRaisesRegex(lifecycle.LifecycleError, 'did not become ready'):
                self.execute('start')
        self.assertEqual(self.events, [('start', 'db')])

    def test_failed_app_stop_withholds_database_stop(self):
        self.execute('start')
        self.command.reset_mock(side_effect=True)
        self.command.side_effect = RuntimeError('lost Docker response')
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'could not confirm stop for the local app'):
            self.execute('stop')
        self.command.assert_called_once_with('stop', '--timeout', '-1', self.pair.app.identity, timeout=55)

    def test_uncertain_stop_keeps_the_fence_and_reuses_it_on_retry(self):
        self.execute('start')
        self.writer.side_effect = FENCE_WRITER
        app_id = self.pair.app.identity
        epoch = 'f' * 64
        fence_dispatches = []
        stop_calls = []

        def command(action, *args, **kwargs):
            if action == 'exec':
                fence_dispatches.append(args)
                self.fence_state.return_value = (True, epoch)
            else:
                stop_calls.append(args[-1])
                if len(stop_calls) == 1:
                    raise RuntimeError('lost Docker response')
                return self.docker(action, *args, **kwargs)

        self.command.side_effect = command
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'could not confirm stop'):
            self.execute('stop')
        self.assertEqual(stop_calls, [app_id])
        fenced = self.inspect()
        self.assertTrue(fenced.shutdown_fenced)
        self.assertEqual(fenced.app.state, 'running')
        self.execute('stop', fenced)
        self.assertEqual(stop_calls, [app_id, app_id, self.pair.db.identity])
        self.assertEqual(fence_dispatches, [('-d', app_id, *lifecycle.PHP, lifecycle.SHUTDOWN_FENCE, '--', epoch)])

    def test_running_renderer_readiness_is_rechecked_on_inspection(self):
        self.execute('start')
        self.readiness.side_effect = lambda _action, identity, *args, **kw: Mock(returncode=int(identity == self.pair.app.identity))
        observed = self.inspect()
        self.assertEqual(observed.unready, ('app',))
        self.assertFalse(observed.can_start)
        self.assertTrue(observed.can_stop)
        self.assertEqual(self.inspect().unready, ('app',))

    def test_no_lifecycle_command_with_bad_docker_or_competing_containers(self):
        for problem in (
            RuntimeError('Docker inspection unavailable. Check Docker Desktop and the retained containers.'),
            ValueError('Retired rehearsal container identity differs or it is running'),
            ValueError('Another Docker container is using the rehearsal volumes'),
        ):
            with self.subTest(problem=problem):
                self.replacement_check.side_effect = problem
                with self.assertRaisesRegex(lifecycle.LifecycleError, str(problem).rstrip('.')):
                    self.execute('start', self.pair)
        self.command.assert_not_called()


class LifecycleUITests(unittest.TestCase):
    def test_explicit_buttons_and_read_only_reopen(self):
        pair = lifecycle.Pair(lifecycle.Service('app', 'exited', 'one'), lifecycle.Service('db', 'exited', 'one'))

        def script():
            from seo_agent.local_title_rehearsal_ui import _lifecycle
            _lifecycle(None, 'selected-site')

        def open_view():
            return AppTest.from_function(script).run()

        with patch.object(lifecycle, 'inspect', return_value=pair) as inspect, patch.object(lifecycle, 'execute') as execute:
            app = open_view()
            self.assertEqual([button.label for button in app.button], ['Start local staging', 'Stop local staging'])
            self.assertTrue(app.button[1].disabled)
            app.run()
            app = open_view()
            execute.assert_not_called()
            app.button[0].click().run()
            execute.assert_called_once_with('start', pair, store=None, sid='selected-site')
            running = replace(pair, app=replace(pair.app, state='running'), db=replace(pair.db, state='running'))
            inspect.return_value = running
            app = open_view()
            self.assertTrue(app.button[0].disabled)
            app.button[1].click().run()
            execute.assert_called_with('stop', running, store=None, sid='selected-site')
            self.assertEqual(execute.call_count, 2)
            execute.side_effect = lifecycle.LifecycleError('Stop could not be confirmed.')
            app.button[1].click().run()
            self.assertEqual([message.value for message in app.error], ['Stop could not be confirmed.'])
            app.run()
            self.assertEqual(execute.call_count, 3)
            inspect.return_value = replace(running, unready=('app',))
            app = open_view()
            self.assertTrue(any('socket did not respond' in msg.value for msg in app.warning))
            app.run()
            self.assertTrue(any('socket did not respond' in msg.value for msg in app.warning))
            self.assertEqual(execute.call_count, 3)
