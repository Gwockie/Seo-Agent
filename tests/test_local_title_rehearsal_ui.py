import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent.coordination import run_lock
from seo_agent.demo import seed_demo
from seo_agent.local_title_rehearsal import DestinationMismatch
from seo_agent.storage import Store
from tests.test_local_title_rehearsal import Backend, Interrupted
from tools.local_title_rehearsal import app_control as control, run
from tools.local_title_rehearsal.scope import CURRENT, HOME, PATHS, PROPOSED, expected_scope


class RehearsalUITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.backend = Backend()
        self.backend.title = CURRENT
        self.runtime = {role: {'id': role + '-fixture'} for role in ('app', 'db')}
        self.lock = self.root/'.title-operation.lock'
        self.lock.write_bytes(b'0')
        self.record(self.root/'running-isolation.json', self.runtime)
        self.titles = [CURRENT + ' | Fixture', 'Contact Us | Fixture']
        self.scope = expected_scope(self.titles)
        self.failure = None
        self.workspace = self.root/'demo'
        store = Store(self.workspace)
        seed_demo(store)
        self.ids = {site['name']: site['id'] for site in store.sites()}
        self.use(patch.dict('os.environ', {'SEO_DEMO': '1', 'SEO_WORKSPACE': str(self.workspace),
                                          'SEO_LOCAL_TITLE_REHEARSAL': '1'}))
        self.use(patch.multiple(run, RUNTIME_PRIVATE=self.root, PRIVATE=self.root,
                                require_protected=lambda _: None, Backend=lambda: self.backend,
                                retained_baseline=lambda: {'title': CURRENT}, load_scope=lambda: self.scope,
                                baseline_document_titles=lambda: self.titles,
                                capture=self.capture, compare=self.compare, verify_restoration=self.verify))
        self.use(patch.multiple(control, require_protected=lambda _: None,
                                _prior_rehearsals_settled=lambda *_: None, _probe=self.probe))

    def use(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def probe(self, backend, status):
        if self.failure:
            raise self.failure
        status.isolation = status.preflight = True
        status.title, epoch = backend.read_state()
        return epoch

    def record(self, path, value):
        with path.open('x', encoding='utf-8') as stream:
            json.dump(value, stream)

    def capture(self, label, *, directory):
        self.record(directory/(label + '-captures.json'), {'title': self.backend.title})

    def compare(self, before, after, *, journal, verification=None, **_):
        self.record((verification or journal)/f'{before}-to-{after}-verification.json', {
            'pages': [{'url': HOME + path, 'literal_title_effects': {'status': 'matches_expectation'},
                       'publication_effects': [{'status': 'matches_expectation'}] * len(page['publication_effects'])}
                      for path, page in zip(PATHS, self.scope['pages'])],
        })

    def verify(self, backend, journal, baseline):
        self.record(journal/'restoration-verified.json', {
            'raw_title_exact': backend.read() == baseline['title'], 'runtime': self.runtime,
            'baseline_volume_manifests_unchanged': True, 'baseline_containers_unchanged': True,
            'pages': [{'path': path, 'exact_restoration': True} for path in PATHS],
        })

    def open(self, site='Demo psychology A'):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=25).run()
        app.sidebar.selectbox[0].select(self.ids[site]).run()
        app.sidebar.radio[0].set_value('Hosting & CMS').run()
        self.assertFalse(app.exception)
        return app

    @staticmethod
    def button(app, phase):
        from seo_agent.local_title_rehearsal_ui import ACTIONS
        return next(button for button in app.button if button.label == dict(ACTIONS)[phase])

    def test_open_rerender_site_switch_and_disabled_launch_have_no_dispatch(self):
        app = self.open()
        self.assertFalse(self.button(app, 'forward').disabled)
        app.run()
        app.sidebar.selectbox[0].select(self.ids['Demo psychology B']).run()
        self.assertFalse(any('synthetic Title' in button.label for button in app.button))
        app.sidebar.selectbox[0].select(self.ids['Demo psychology A']).run()
        self.assertFalse(self.button(app, 'forward').disabled)
        with patch.dict('os.environ', {'SEO_LOCAL_TITLE_REHEARSAL': '0'}):
            self.assertFalse(any('synthetic Title' in button.label for button in self.open().button))
        self.assertEqual(self.backend.saves, 0)
        self.assertFalse(control._root().exists())

    def test_exact_buttons_restore_and_verify_with_durable_restart_and_duplicate_rejection(self):
        app = self.open()
        stale = control.inspect()
        self.button(app, 'forward').click().run()
        self.assertFalse(app.exception)
        self.assertEqual((self.backend.title, self.backend.saves), (PROPOSED, 1))
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            control.execute(stale.action, stale.revision)
        reopened = self.open()
        self.assertIn('Apply: applied', [row.value for row in reopened.text])
        self.assertFalse(self.button(reopened, 'restore').disabled)
        self.assertEqual(self.backend.saves, 1)
        self.button(reopened, 'restore').click().run()
        self.assertEqual((self.backend.title, self.backend.saves), (CURRENT, 2))
        self.assertTrue(self.button(reopened, 'forward').disabled)
        self.button(reopened, 'verify').click().run()
        self.assertFalse(reopened.exception)
        self.assertTrue(reopened.success)
        self.assertFalse(self.button(reopened, 'forward').disabled)
        self.assertEqual(self.backend.saves, 2)
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            control.execute(stale.action, stale.revision)
        self.assertEqual([path.name for path in control._root().iterdir()], ['run-000001'])

    def test_busy_stopped_mismatch_and_failed_preflight_block_actions(self):
        stale = control.inspect()
        with run_lock(self.lock, create=False):
            self.assertIn('controller is active', control.inspect().blocker)
            with self.assertRaisesRegex(ValueError, 'controller is active'):
                control.execute(stale.action, stale.revision)
        for error in (ValueError('Disposable Docker service db is stopped or paused'),
                      DestinationMismatch('Disposable runtime identity differs from the retained rehearsal'),
                      ValueError('Local service preflight command failed without a usable response')):
            with self.subTest(error=error):
                self.failure = error
                status = control.inspect()
                self.assertEqual(status.blocker, str(error))
                self.assertFalse(status.action)
                with self.assertRaises(ValueError):
                    control.execute(stale.action, stale.revision)
        self.assertFalse(control._root().exists())
        self.assertEqual(self.backend.saves, 0)

    def test_recovery_requires_fencing_and_never_dispatches_a_save(self):
        self.backend.mode = 'crash-after'
        available = control.inspect()
        with self.assertRaises(Interrupted):
            control.execute(available.action, available.revision)
        pending = self.open()
        self.assertIn('Apply: interrupted', [row.value for row in pending.text])
        self.button(pending, 'recover').click().run()
        self.assertTrue(self.button(pending, 'recover').disabled)
        self.assertTrue(self.button(pending, 'restore').disabled)
        self.backend.epoch = 'c' * 64
        self.backend.mode = 'success'
        recovered = self.open()
        self.button(recovered, 'recover').click().run()
        self.assertFalse(self.button(recovered, 'restore').disabled)
        self.assertEqual(self.backend.saves, 1)
        self.assertEqual([path.name for path in control._root().iterdir()], ['run-000001'])

    def test_intervening_title_blocks_restore_even_with_stale_action(self):
        status = control.inspect()
        control.execute(status.action, status.revision)
        stale = control.inspect()
        self.backend.title = 'Intervening edit'
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            control.execute(stale.action, stale.revision)
        app = self.open()
        self.assertTrue(self.button(app, 'restore').disabled)
        self.assertTrue(any('intervening raw Title' in warning.value for warning in app.warning))
        self.assertEqual(self.backend.saves, 1)
        self.assertFalse((control._root()/'run-000001'/'restore-attempt.json').exists())
