import tempfile
import unittest
from pathlib import Path

from seo_agent.local_title_rehearsal import transition


class Backend:
    title = "Original 'title' \\ literal"
    saves = 0
    mode = 'success'

    def read(self):
        if self.mode == 'unreadable' and self.saves:
            raise TimeoutError('private diagnostic')
        return self.title

    def save(self, *, expected, replacement):
        self.saves += 1
        if self.mode == 'failed':
            return {'status': 'failed'}
        if self.mode == 'conflict':
            self.title = 'Intervening edit'
            return {'status': 'conflict'}
        if self.mode != 'lost-before':
            self.title = replacement
        if self.mode in {'lost-before', 'lost-after', 'unreadable'}:
            raise TimeoutError('private diagnostic')
        return {'status': 'returned'}


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
            result = transition(backend, directory, 'restore', expected='Synthetic test', replacement='Original')
            self.assertEqual(result['outcome'], 'conflict')
            self.assertEqual(backend.saves, 0)

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
