import json
import tempfile
import unittest
from pathlib import Path

from seo_agent.local_title_rehearsal import recover, transition


class Backend:
    title = "Original 'title' \\ literal"
    saves = 0
    mode = 'success'
    epoch = 'a' * 64
    identity = 'b' * 64
    reads = 0

    def destination(self):
        return self.identity

    def read_state(self):
        self.reads += 1
        if self.mode == 'unreadable' and self.saves:
            raise TimeoutError('private diagnostic')
        return self.title, self.epoch

    def save(self, *, expected, replacement, writer_epoch):
        if self.mode == 'crash-before':
            raise Interrupted
        self.saves += 1
        if self.mode == 'failed':
            return {'status': 'failed'}
        if self.mode == 'conflict':
            self.title = 'Intervening edit'
            return {'status': 'conflict'}
        if self.mode != 'lost-before':
            self.title = replacement
        if self.mode == 'crash-after':
            raise Interrupted
        if self.mode in {'lost-before', 'lost-after', 'unreadable'}:
            raise TimeoutError('private diagnostic')
        return {'status': 'returned'}


class Interrupted(BaseException):
    pass


class LocalTitleRehearsalTests(unittest.TestCase):
    def test_forward_and_exact_raw_restoration(self):
        backend = Backend()
        original = backend.title
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(transition(backend, directory, 'forward', expected=original,
                                       replacement='Synthetic test')['outcome'], 'applied')
            self.assertEqual(transition(backend, directory, 'restore', expected='Synthetic test',
                                       replacement=original)['outcome'], 'applied')
            self.assertEqual(backend.title, original)

    def test_intervening_title_blocks_restoration(self):
        backend = Backend()
        with tempfile.TemporaryDirectory() as directory:
            original = backend.title
            transition(backend, directory, 'forward', expected=original, replacement='Synthetic test')
            backend.title = 'Intervening edit'
            result = transition(backend, directory, 'restore', expected='Synthetic test', replacement=original)
            self.assertEqual(result['outcome'], 'conflict')
            self.assertEqual(backend.saves, 1)

    def test_lost_reply_reconciles_without_retry(self):
        for mode, outcome in [('lost-after', 'applied'), ('lost-before', 'uncertain'),
                              ('unreadable', 'uncertain'), ('conflict', 'conflict')]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                backend = Backend()
                backend.mode = mode
                result = transition(backend, directory, 'forward', expected=backend.title, replacement='Test')
                self.assertEqual(result['outcome'], outcome)
                with self.assertRaises(ValueError):
                    transition(backend, directory, 'forward', expected=backend.title, replacement='Other')
                self.assertEqual(backend.saves, 1)
                self.assertNotIn('private diagnostic', (Path(directory) / 'forward-result.json').read_text())

    def test_pending_attempt_is_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'forward-attempt.json').write_text('{}')
            backend = Backend()
            with self.assertRaises(ValueError):
                transition(backend, directory, 'forward', expected=backend.title, replacement='Test')
            self.assertEqual(backend.saves, 0)

    def test_failed_api_reply_is_distinct_from_unknown_outcome(self):
        backend = Backend()
        backend.mode = 'failed'
        with tempfile.TemporaryDirectory() as directory:
            result = transition(backend, directory, 'forward', expected=backend.title, replacement='Test')
            self.assertEqual(result['outcome'], 'failed')
            self.assertEqual(backend.saves, 1)

    def test_bad_names_and_equal_values_never_call_backend(self):
        backend = Backend()
        with tempfile.TemporaryDirectory() as directory:
            for name, replacement in [('../escape', 'Test'), ('forward', backend.title)]:
                with self.assertRaises(ValueError):
                    transition(backend, directory, name, expected=backend.title, replacement=replacement)
            self.assertEqual(backend.saves, 0)

    def interrupt(self, backend, directory, mode):
        original = backend.title
        backend.mode = mode
        with self.assertRaises(Interrupted):
            transition(backend, directory, 'forward', expected=original, replacement='Test')
        self.assertFalse((Path(directory) / 'forward-result.json').exists())
        backend.mode = 'success'
        return {'expected': original, 'replacement': 'Test'}

    def test_interruption_before_save_observes_original_without_authorizing_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Backend()
            titles = self.interrupt(backend, directory, 'crash-before')
            backend.epoch = 'c' * 64
            self.assertEqual(recover(backend, directory, 'forward', **titles)['observation'],
                             'original_value_observed')
            with self.assertRaisesRegex(ValueError, 'without retrying'):
                transition(backend, directory, 'forward', **titles)
            with self.assertRaisesRegex(ValueError, 'proposed Title'):
                transition(backend, directory, 'restore', expected='Test', replacement=titles['expected'])
            self.assertEqual(backend.saves, 0)

    def test_interruption_after_save_and_repeated_recovery_preserve_history(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Backend()
            titles = self.interrupt(backend, directory, 'crash-after')
            attempt = Path(directory) / 'forward-attempt.json'
            original_bytes = attempt.read_bytes()
            same_epoch = recover(backend, directory, 'forward', **titles)
            self.assertEqual(same_epoch['reason'], 'writer_generation_still_running')
            self.assertIsNone(same_epoch['actual'])
            backend.epoch = 'c' * 64
            first = recover(backend, directory, 'forward', **titles)
            self.assertEqual((first['observation'], first['actual']), ('proposed_value_observed', 'Test'))
            first_path = Path(directory) / first['record']
            original_observation = first_path.read_bytes()
            second = recover(backend, directory, 'forward', **titles)
            self.assertNotEqual(first['record'], second['record'])
            self.assertEqual(second['observation'], first['observation'])
            self.assertEqual(original_observation, first_path.read_bytes())
            self.assertEqual(original_bytes, attempt.read_bytes())
            self.assertFalse((Path(directory) / 'forward-result.json').exists())
            self.assertEqual(backend.saves, 1)

    def test_unreadable_and_intervening_state_are_recorded_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Backend()
            titles = self.interrupt(backend, directory, 'crash-after')
            backend.epoch = 'c' * 64
            backend.mode = 'unreadable'
            result = recover(backend, directory, 'forward', **titles)
            self.assertEqual(result['observation'], 'unavailable_or_unresolved')
            self.assertEqual(result['reason'], 'read_unavailable')
            self.assertNotIn('private diagnostic', (Path(directory) / result['record']).read_text())

            backend.mode = 'success'
            recover(backend, directory, 'forward', **titles)
            backend.title = 'Intervening title'
            result = recover(backend, directory, 'forward', **titles)
            self.assertEqual(result['observation'], 'different_value_observed')
            with self.assertRaisesRegex(ValueError, 'proposed Title'):
                transition(backend, directory, 'restore', expected='Test', replacement=titles['expected'])
            self.assertEqual(backend.saves, 1)

    def test_completed_result_is_bound_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Backend()
            titles = {'expected': backend.title, 'replacement': 'Test'}
            backend.mode = 'lost-before'
            transition(backend, directory, 'forward', **titles)
            result = Path(directory) / 'forward-result.json'
            original = result.read_bytes()
            backend.epoch = 'c' * 64
            recover(backend, directory, 'forward', **titles)
            self.assertEqual(result.read_bytes(), original)
            self.assertEqual(backend.saves, 1)

    def test_rejects_corrupt_partial_legacy_or_mismatched_journals_before_reading(self):
        for case in ('truncated attempt', 'duplicate field', 'missing writer', 'wrong intent',
                     'partial result', 'mismatched result', 'partial recovery'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                backend = Backend()
                titles = self.interrupt(backend, directory, 'crash-before')
                folder = Path(directory)
                attempt = folder / 'forward-attempt.json'
                value = json.loads(attempt.read_bytes())
                if case == 'truncated attempt':
                    attempt.write_text('{')
                elif case == 'duplicate field':
                    raw = attempt.read_text()
                    attempt.write_text(raw[:-1] + ', "outcome": "attempted"}')
                elif case == 'missing writer':
                    del value['writer_epoch']
                    attempt.write_text(json.dumps(value))
                elif case == 'wrong intent':
                    titles['replacement'] = 'Other'
                elif case == 'partial result':
                    (folder / 'forward-result.json').write_text('{')
                elif case == 'mismatched result':
                    (folder / 'forward-result.json').write_text(json.dumps({
                        'outcome': 'applied', 'actual': 'Test', 'response': None, 'error_type': None,
                        'write_attempted': True, 'observed_utc': value['observed_utc'],
                        'attempt_sha256': 'f' * 64,
                    }))
                else:
                    (folder / 'forward-recovery-incomplete.json').write_text('{')
                reads = backend.reads
                with self.assertRaisesRegex(ValueError, r'forward-(attempt|result|recovery)'):
                    recover(backend, directory, 'forward', **titles)
                self.assertEqual(backend.reads, reads)
                self.assertEqual(backend.saves, 0)

    def test_destination_mismatch_rejects_even_when_raw_title_would_match(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Backend()
            titles = self.interrupt(backend, directory, 'crash-before')
            other = Backend()
            other.identity = 'd' * 64
            other.epoch = 'c' * 64
            with self.assertRaisesRegex(ValueError, 'differs from the recorded destination'):
                recover(other, directory, 'forward', **titles)
            self.assertEqual(other.reads, 0)
            self.assertEqual(other.saves, 0)
