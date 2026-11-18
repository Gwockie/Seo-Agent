import json
from hashlib import sha256
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from seo_agent import page_tracking, tracking
from seo_agent.coordination import run_lock
from seo_agent.demo import seed_demo
from seo_agent.local_title_rehearsal import DestinationMismatch
from seo_agent.storage import Store, new_id, utc_now
from tests.test_local_title_rehearsal import Backend, Interrupted
from tools.local_title_rehearsal import app_control as control, proposal_binding, run
from tools.local_title_rehearsal.scope import CURRENT, HOME, PATHS, PROPOSED, expected_scope

SAVED_TITLE = 'Synthetic Proposal Rehearsal Review'
READ_ONLY_PROBE = control._probe


class RehearsalUITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.cleanup_fixture, temporary)
        self.root = Path(temporary.name)
        (self.root/control.ACTIVE_JOURNALS).mkdir()
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
        self.store = Store(self.workspace)
        seed_demo(self.store)
        self.ids = {site['name']: site['id'] for site in self.store.sites()}
        for sid in self.ids.values():
            page_tracking.save_settings(self.store, sid, {'enabled': False})
        self.sid = self.ids['Demo psychology A']
        self.aid = self.store.create_audit(self.sid)
        self.source = self.save_proposal()
        self.selection = (self.aid, self.source['action_id'], 1)
        self.capture('before', directory=self.root)
        clone_record = self.root/run.CLONE_RECORD
        clone_record.parent.mkdir(parents=True)
        self.record(clone_record, {'source_manifest': 'fixture'})
        self.use(patch.dict('os.environ', {'SEO_DEMO': '1', 'SEO_WORKSPACE': str(self.workspace),
                                          'SEO_LOCAL_TITLE_REHEARSAL': '1'}))
        self.use(patch.multiple(run, RUNTIME_PRIVATE=self.root, PRIVATE=self.root,
                                Backend=lambda: self.backend,
                                retained_baseline=lambda: {'title': CURRENT, 'baseline': 'fixture'},
                                load_scope=lambda: self.scope, capture=self.capture,
                                clone=lambda *_, **__: 'fixture', inspect_baseline=lambda: 'fixture',
                                inspect_retained_runtime=lambda: self.runtime))
        self.use(patch.multiple(control, require_protected=lambda _: None, require_registered=lambda _: None,
                                check_preflight=lambda: None,
                                load_registration=lambda _: {'replacement_runtime': self.runtime}, _probe=self.probe))

    def use(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def cleanup_fixture(temporary):
        try:
            temporary.cleanup()
        except PermissionError as exc:
            if getattr(exc, 'winerror', None) != 32:
                raise
            # A short-lived Windows handle can outlast the Streamlit test run.
            time.sleep(0.25)
            temporary.cleanup()

    def probe(self, backend, status):
        if self.failure:
            raise self.failure
        status.isolation = status.preflight = True
        backend.bound_destination = backend.destination()
        status.title, epoch = backend.read_state()
        return epoch

    def record(self, path, value):
        with path.open('x', encoding='utf-8') as stream:
            json.dump(value, stream)

    def capture(self, label, *, directory):
        title = self.backend.title
        pages = []
        for index, path in enumerate(PATHS):
            url = HOME + path
            document = f'{title} | Fixture' if index == 0 else self.titles[1]
            heading = (f'<div data-id="022c973"><h1>{title}</h1></div>'
                       f'<div data-id="2be23dd"><ul><li></li><li><a>'
                       f'<span class="elementor-icon-list-text">{title}</span></a></li></ul></div>'
                       if index == 0 else '<div data-id="c2a3857"><h1>Contact Us</h1></div>')
            nav = ''.join(f'<ul id="menu-{n}-{widget}" {"hidden" if n == 2 else ""}>'
                          f'<li class="menu-item-{item}"><a href="{HOME + PATHS[0]}">{title}</a></li></ul>'
                          for widget, item in [('2527b27', 771), ('5e78af5', 801)] for n in (1, 2))
            raw = (f'<html><head><title>{document}</title><link rel="canonical" href="{url}">'
                   f'<meta name="robots" content="noindex, nofollow"></head><body>{heading}{nav}</body></html>').encode()
            for kind in ('raw', 'sanitized'):
                (directory/f'{label}-{index}-{kind}.html').write_bytes(raw)
            digest = sha256(raw).hexdigest()
            pages.append({'url': url, 'checked': utc_now(), 'http_status': 200,
                          'headers': {'X-Robots-Tag': 'noindex, nofollow, noarchive'},
                          'raw_sha256': digest, 'sanitized_sha256': digest})
        self.record(directory/(label + '-captures.json'), {'pages': pages})

    def save_proposal(self, **overrides):
        value = {
            'action_id': new_id(), 'url': proposal_binding.MAPPING['source_url'], 'action_kind': 'text',
            'current': CURRENT, 'proposed': SAVED_TITLE, 'current_source': 'Synthetic fixture baseline',
            'capture_time_utc': None, 'rationale': 'Synthetic wording', 'expected_effect': 'Local title change',
            'primary_measure': 'Page clicks', 'measurement': 'Compare the local rendered title',
            'validation': 'Verify two declared pages', 'rollback': 'Restore the original raw title', 'evidence': [],
            'manual_post_title': {'page_id': 716, 'widget_id': '022c973', 'source': 'Synthetic Post Title mapping',
                                  'shared_effects': 'The fixed two local pages'},
            'confirmations': [{'item': 'Synthetic pending question', 'status': 'pending', 'source': None}],
            **overrides,
        }
        identity = tracking.save_action(self.store, self.sid, self.aid, value)
        return tracking.action(self.store, self.sid, identity, 1)['payload']

    def revise(self, **changes):
        tracking.save_action(self.store, self.sid, self.aid, {**self.source, **changes}, revision=2)
        self.selection = (*self.selection[:2], 2)

    def status(self, *, selection=True):
        return control.inspect(store=self.store, sid=self.sid, selection=self.selection if selection else None)

    def execute(self, status, *, selection=True):
        return control.execute(status.action, status.revision, store=self.store, sid=self.sid,
                               selection=self.selection if selection else None)

    def open(self, site='Demo psychology A', view='Recommendations & changes'):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=25).run()
        app.sidebar.selectbox[0].select(self.ids[site]).run()
        app.sidebar.radio[0].set_value(view).run()
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
        self.assertFalse(any('Apply saved Title' == button.label for button in app.button))
        app.sidebar.selectbox[0].select(self.ids['Demo psychology A']).run()
        self.assertFalse(self.button(app, 'forward').disabled)
        with patch.dict('os.environ', {'SEO_LOCAL_TITLE_REHEARSAL': '0'}):
            self.assertFalse(any('Apply saved Title' == button.label for button in self.open().button))
        self.assertEqual(self.backend.saves, 0)
        self.assertEqual(list(control._root().iterdir()), [])

    def test_opening_checks_live_state_without_wordpress_bootstrap(self):
        self.backend.bound_destination = self.backend.identity
        with patch.object(control, '_probe', READ_ONLY_PROBE), patch.object(
            control, 'check_preflight', side_effect=AssertionError('WordPress bootstrap during app inspection'),
        ) as preflight:
            app = self.open()
            self.assertFalse(self.button(app, 'forward').disabled)
            preflight.assert_not_called()
        self.assertEqual(self.backend.saves, 0)
        self.assertEqual(list(control._root().iterdir()), [])

    def test_missing_active_journal_root_blocks_current_and_stale_apply(self):
        stale = self.status()
        control._root().rmdir()
        self.assertIn('missing: app-rehearsals', self.status().blocker)
        with self.assertRaisesRegex(ValueError, 'missing: app-rehearsals'):
            self.execute(stale)
        self.assertFalse(control._root().exists())
        self.assertEqual(self.backend.saves, 0)

    def test_exact_buttons_restore_and_verify_with_durable_restart_and_duplicate_rejection(self):
        app = self.open()
        stale = self.status()
        app.text_area(key=f"{self.sid}:{self.source['action_id']}:1:proposed").set_value('Unsaved Title')
        self.button(app, 'forward').click().run()
        self.assertFalse(app.exception)
        self.assertNotEqual(SAVED_TITLE, PROPOSED)
        self.assertEqual((self.backend.title, self.backend.saves), (SAVED_TITLE, 1))
        binding = self.status().binding
        self.assertEqual((binding['site_id'], binding['audit_id'], binding['action_id'], binding['revision']),
                         (self.sid, *self.selection))
        self.assertEqual(binding['proposal_sha256'], tracking.digest(self.source))
        self.assertEqual(binding['mapping'], proposal_binding.MAPPING)
        self.assertEqual((binding['baseline'], binding['replacement']), (CURRENT, SAVED_TITLE))
        self.assertEqual(binding['destination_sha256'], self.backend.identity)
        self.assertEqual(binding['scope_sha256'], tracking.digest(run.proposal_scope(SAVED_TITLE)))
        self.assertEqual(binding['baseline_captures_sha256'], run.baseline_capture_digest())
        self.assertEqual(binding['pending_confirmations'], ['Synthetic pending question'])
        journal = control._root()/'run-000001'
        self.assertEqual(json.loads((journal/'forward-attempt.json').read_bytes())['binding'], binding)
        comparison = json.loads((journal/'before-to-after-verification.json').read_bytes())
        self.assertEqual(comparison['proposal_binding_sha256'], tracking.digest(binding))
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            self.execute(stale)
        reopened = self.open()
        self.assertIn('Apply: applied', [row.value for row in reopened.text])
        self.assertTrue(any('Current saved revision 1' in expander.label for expander in reopened.expander))
        self.assertTrue(any('Raw checks: 8/8 matched' in row.value for row in reopened.text))
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
        restored = next(journal.glob('verification-*/restoration-verified.json'))
        self.assertTrue(json.loads(restored.read_bytes())['raw_title_exact'])
        self.assertEqual(json.loads(restored.read_bytes())['proposal_binding_sha256'], tracking.digest(binding))
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            self.execute(stale)
        self.assertEqual([path.name for path in control._root().iterdir()], ['run-000001'])
        for table in ('human_approvals', 'publication_batches', 'implementation_receipts'):
            self.assertEqual(tracking.rows(self.store, table, self.sid), [])

    def test_busy_stopped_mismatch_and_failed_preflight_block_actions(self):
        stale = self.status()
        with run_lock(self.lock, create=False):
            self.assertIn('controller is active', self.status().blocker)
            with self.assertRaisesRegex(ValueError, 'controller is active'):
                self.execute(stale)
        for error in (ValueError('Disposable Docker service db is stopped or paused'),
                      DestinationMismatch('Disposable runtime identity differs from the retained rehearsal'),
                      ValueError('Local service preflight command failed without a usable response')):
            with self.subTest(error=error):
                self.failure = error
                status = self.status()
                self.assertEqual(status.blocker, str(error))
                self.assertFalse(status.action)
                with self.assertRaises(ValueError):
                    self.execute(stale)
        self.assertEqual(list(control._root().iterdir()), [])
        self.assertEqual(self.backend.saves, 0)

    def test_recovery_requires_fencing_and_never_dispatches_a_save(self):
        self.backend.mode = 'crash-after'
        available = self.status()
        with self.assertRaises(Interrupted):
            self.execute(available)
        self.revise(proposed='Future Title', manual_post_title=None)
        pending = self.open()
        self.assertIn('Apply: interrupted', [row.value for row in pending.text])
        self.assertTrue(any('Historical revision 1' in expander.label for expander in pending.expander))
        self.assertFalse(any('Current saved revision 2' in expander.label for expander in pending.expander))
        self.assertTrue(self.button(pending, 'forward').disabled)
        self.button(pending, 'recover').click().run()
        self.assertTrue(self.button(pending, 'recover').disabled)
        self.assertTrue(self.button(pending, 'restore').disabled)
        self.backend.epoch = 'c' * 64
        self.backend.mode = 'success'
        recovered = self.open()
        self.button(recovered, 'recover').click().run()
        self.assertFalse(self.button(recovered, 'restore').disabled)
        self.assertEqual(self.backend.saves, 1)
        self.button(recovered, 'restore').click().run()
        self.assertEqual((self.backend.title, self.backend.saves), (CURRENT, 2))
        self.button(recovered, 'verify').click().run()
        self.assertTrue(recovered.success)
        self.assertEqual(self.status().binding['replacement'], SAVED_TITLE)
        self.assertEqual([path.name for path in control._root().iterdir()], ['run-000001'])

    def test_intervening_title_blocks_restore_even_with_stale_action(self):
        self.execute(self.status())
        stale = self.status()
        self.backend.title = 'Intervening edit'
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            self.execute(stale)
        app = self.open()
        self.assertTrue(self.button(app, 'restore').disabled)
        self.assertTrue(any('intervening raw Title' in warning.value for warning in app.warning))
        self.assertEqual(self.backend.saves, 1)
        self.assertFalse((control._root()/'run-000001'/'restore-attempt.json').exists())

    def test_changed_revision_mapping_and_baseline_invalidate_pending_apply(self):
        stale = self.status()
        self.assertEqual(stale.action, ('forward',))
        self.backend.title = 'Unexpected local baseline'
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            self.execute(stale)
        self.backend.title = CURRENT
        self.backend.identity = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            self.execute(stale)
        self.backend.identity = 'b' * 64
        self.revise(proposed='Different saved title')
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            self.execute(stale)
        stale = self.status()
        self.assertEqual(stale.action, ('forward',))
        changed = {**self.source, 'manual_post_title': {**self.source['manual_post_title'], 'widget_id': 'aaaaaaa'}}
        tracking.save_action(self.store, self.sid, self.aid, changed, revision=3)
        self.selection = (*self.selection[:2], 3)
        with self.assertRaisesRegex(ValueError, 'changed or is blocked'):
            self.execute(stale)
        self.assertIn('explicit Post Title mapping', self.status().proposal_blocker)
        self.assertEqual(list(control._root().iterdir()), [])
        self.assertEqual(self.backend.saves, 0)

    def test_unsupported_source_and_replacement_are_explained_without_a_save(self):
        other = control.inspect(store=self.store, sid=self.ids['Demo psychology B'], selection=self.selection)
        self.assertIn('no validated local Title mapping', other.blocker)
        self.assertFalse(other.action)
        for changes, reason in (
            ({'manual_post_title': None}, 'explicit Post Title mapping'),
            ({'proposed': 'Testing & Assessment'}, 'Unsupported local Title text'),
            ({'proposed': 'Synthetic Assessment - Paoli'}, 'Unsupported local Title text'),
            ({'proposed': 'Synthetic Review -'}, 'Unsupported local Title text'),
            ({'proposed': 'Synthetic ``Review'}, 'Unsupported local Title text'),
            ({'proposed': 'Synthetic Wordpress Review'}, 'Unsupported local Title text'),
            ({'proposed': 'Contact Us'}, 'retained literal verification'),
            ({'current': 'Unrelated baseline'}, 'saved proposal baseline differs'),
        ):
            with self.subTest(changes=changes):
                value = self.save_proposal(**changes)
                status = control.inspect(store=self.store, sid=self.sid, selection=(self.aid, value['action_id'], 1))
                self.assertIn(reason, status.proposal_blocker)
                self.assertFalse(status.action)
        self.assertEqual(list(control._root().iterdir()), [])
        self.assertEqual(self.backend.saves, 0)

    def test_other_proposal_cannot_bypass_or_take_over_pending_run(self):
        self.execute(self.status())
        value = self.save_proposal(proposed='A Second Saved Title')
        other = control.inspect(store=self.store, sid=self.sid, selection=(self.aid, value['action_id'], 1))
        self.assertFalse(other.action)
        self.assertFalse(other.history)
        self.assertIn('Another rehearsal needs reconciliation', other.blocker)
        self.assertEqual(self.status(selection=False).action, ('restore',))
        self.assertEqual(self.backend.saves, 1)

    def test_duplicate_url_cannot_see_existing_journal_or_offer_actions(self):
        self.execute(self.status())
        original = self.store.site(self.sid)
        duplicate = original.model_copy(update={'name': 'Duplicate', 'gsc_property': 'sc-domain:psychology-a.example'})
        self.ids['Duplicate'] = self.store.save_site(duplicate)
        page_tracking.save_settings(self.store, self.ids['Duplicate'], {'enabled': False})
        app = self.open('Duplicate', 'Hosting & CMS')
        self.assertFalse(any('Restore original Title' == button.label for button in app.button))
        self.assertFalse(any('run-000001' in row.value for row in app.text))
        app.sidebar.selectbox[0].select(self.ids['Demo psychology A']).run()
        self.assertFalse(any('Restore original Title' == button.label for button in app.button))
        self.assertEqual(self.backend.saves, 1)

    def test_partial_rendered_reports_preserve_guarded_restore_and_verification(self):
        self.execute(self.status())
        journal = control._root()/'run-000001'
        forward_report = journal/'before-to-after-verification.json'
        forward_report.write_text('null', encoding='utf-8')
        app = self.open()
        self.assertFalse(self.button(app, 'restore').disabled)
        self.assertTrue(any('Incomplete rendered evidence' in line.value for line in app.caption))
        self.button(app, 'restore').click().run()
        partial = journal/'verification-interrupted'
        partial.mkdir()
        (partial/'restoration-verified.json').write_text('{"raw_title_exact":', encoding='utf-8')
        app.run()
        self.assertTrue(self.button(app, 'forward').disabled)
        self.assertFalse(self.button(app, 'verify').disabled)
        self.button(app, 'verify').click().run()
        self.assertTrue(app.success)
        self.assertEqual(forward_report.read_text(encoding='utf-8'), 'null')
        self.assertTrue(partial.exists())
        self.assertEqual(self.backend.saves, 2)

    def test_malformed_elementor_data_displays_preflight_blocker(self):
        for document in ({}, [{'elements': [False]}],
                         [{'id': '022c973', 'settings': {'__dynamic__': []}}]):
            data = {'elementor_data': json.dumps(document)}
            with patch.object(run, 'preflight_command', return_value=data):
                with self.assertRaisesRegex(ValueError, 'Invalid representative heading data'):
                    run.check_preflight()
        with patch.object(run, 'preflight_command', return_value={'elementor_data': '{}'}), patch.object(
            control, '_probe', side_effect=lambda *_: run.check_preflight()
        ):
            app = self.open()
            self.assertTrue(any('Invalid representative heading data' in line.value for line in app.warning))
            self.assertTrue(self.button(app, 'forward').disabled)
            self.assertFalse(app.exception)
        self.assertEqual(self.backend.saves, 0)

    def test_local_mapping_requires_the_exact_dynamic_heading(self):
        title_tag = '[elementor-tag id="abc1234" name="post-title" settings="%7B%7D"]'
        widget = {'id': '022c973', 'elType': 'widget', 'widgetType': 'heading',
                  'settings': {'header_size': 'h1', '__dynamic__': {'title': title_tag}}}
        run.check_heading_binding(json.dumps([widget]))
        for altered in (
            {**widget, 'widgetType': 'text-editor'},
            {**widget, 'settings': {**widget['settings'], 'header_size': 'h2'}},
            {**widget, 'settings': {**widget['settings'], '__dynamic__': {'title': 'prefix ' + title_tag}}},
        ):
            with self.assertRaisesRegex(ValueError, 'does not use expected Post Title binding'):
                run.check_heading_binding(json.dumps([altered]))
