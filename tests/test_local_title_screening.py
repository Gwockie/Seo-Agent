import json
import unittest
from unittest.mock import Mock

from tools.local_title_rehearsal.screening import SIGNING_OPTION, SIGNING_REJECTION, ScreeningRejected, screen_options


class LocalTitleScreeningTests(unittest.TestCase):
    def setUp(self):
        # Minimal stand-ins for the sealed traversal and its decoders. The
        # retained runtime uses the actual historical scanner in preflight.
        self.parse_php = Mock(return_value={'secret_fixture': 'private-value'})
        self.historical = Mock(side_effect=ValueError('Sensitive input key'))

    def screen(self, options):
        return screen_options(options, self.historical, self.parse_php, json.loads)

    def test_exact_static_option_is_reported_without_value_and_still_rejected(self):
        for private_value in ('a' * 64, 'synthetic-jwt-signing-key', 'https://x.test/?token=synthetic'):
            with self.subTest(private_value=private_value), self.assertRaises(ScreeningRejected) as raised:
                self.screen({SIGNING_OPTION: private_value})
            self.assertEqual(raised.exception.diagnostic, SIGNING_REJECTION)
            self.assertNotIn(private_value, json.dumps(raised.exception.diagnostic))
            self.historical.assert_called_with({SIGNING_OPTION: private_value})

    def test_dynamic_keys_are_redacted_at_every_depth(self):
        for value, suffix in [
            ({SIGNING_OPTION: 'private-value'}, ['entry[0]']),
            ('{"api_key_private_name":"private-value"}', ['json', 'entry[0]']),
            ('a:1:{s:14:"secret_fixture";s:13:"private-value";}', ['php', 'entry[0]']),
        ]:
            with self.subTest(value=value), self.assertRaises(ScreeningRejected) as raised:
                self.screen({'dynamic-private-name': [value]})
            self.assertEqual(raised.exception.diagnostic, {
                'rule': 'nonempty_sensitive_key',
                'location': ['options', 'entry[0]', 'item[0]', *suffix],
                'value_type': 'str',
            })

    def test_historical_success_is_returned_without_mutating_input(self):
        options = {SIGNING_OPTION: ''}
        self.historical.side_effect = None
        metrics = self.historical.return_value = {'nodes': 3}
        self.assertIs(self.screen(options), metrics)
        self.historical.assert_called_once_with({SIGNING_OPTION: ''})
        self.assertEqual(options, {SIGNING_OPTION: ''})

    def test_other_rule_and_parser_errors_do_not_disclose_messages(self):
        self.historical.side_effect = ValueError('Credential-shaped input with private detail')
        with self.assertRaises(ScreeningRejected) as raised:
            self.screen({'ordinary': 'private-value'})
        self.assertEqual(raised.exception.diagnostic, {'rule': 'historical_screen_rejected'})
        self.assertNotIn('private', str(raised.exception))
        self.historical.side_effect = ValueError('Sensitive input key')
        self.parse_php.side_effect = ValueError('private serialization detail')
        with self.assertRaises(ScreeningRejected) as raised:
            self.screen({'ordinary': 'a:invalid'})
        self.assertEqual(raised.exception.diagnostic, {'rule': 'nonempty_sensitive_key'})
        self.assertNotIn('private', str(raised.exception))
