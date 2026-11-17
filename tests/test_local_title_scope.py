import copy
import tempfile
import unittest
from unittest.mock import Mock

from tools.local_title_rehearsal.scope import CURRENT, PROPOSED, expected_scope, save_forward, validate_scope


class LocalTitleScopeTests(unittest.TestCase):
    titles = ['Comprehensive Psychological Assessments | Local test', 'Contact Us | Local test']

    def test_complete_fixed_contract_is_accepted(self):
        scope = expected_scope(self.titles)
        self.assertEqual(validate_scope(scope, document_titles=self.titles), scope)
        self.assertEqual([len(page['title_effects']) for page in scope['pages']], [7, 4])
        self.assertEqual([len(page['publication_effects']) for page in scope['pages']], [8, 7])
        backend = Mock()
        backend.read.side_effect = [CURRENT, PROPOSED]
        backend.save.return_value = {'status': 'returned'}
        with tempfile.TemporaryDirectory() as directory:
            result = save_forward(backend, directory, scope, document_titles=self.titles)
        self.assertEqual(result['outcome'], 'applied')
        backend.save.assert_called_once_with(expected=CURRENT, replacement=PROPOSED)

    def test_empty_missing_extra_and_reordered_pages_cannot_reach_backend(self):
        valid = expected_scope(self.titles)
        bad = [{}, {'pages': []}, {'pages': valid['pages'][:1]},
               {'pages': [*valid['pages'], valid['pages'][0]]}, {'pages': list(reversed(valid['pages']))},
               {'pages': valid['pages'], 'unexpected': True}]
        for key in ('title_effects', 'publication_effects'):
            for value in (None, []):
                scope = copy.deepcopy(valid)
                scope['pages'][0][key] = value
                bad.append(scope)
            scope = copy.deepcopy(valid)
            del scope['pages'][0][key]
            bad.append(scope)
        for scope in bad:
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                backend = Mock()
                with self.assertRaises(ValueError):
                    save_forward(backend, directory, scope, document_titles=self.titles)
                backend.read.assert_not_called()
                backend.save.assert_not_called()

    def test_changed_urls_locations_values_and_rule_coverage_are_rejected(self):
        bad = []
        for key, value in [('url', 'https://example.com/'), ('title_effects', []), ('publication_effects', [])]:
            scope = expected_scope(self.titles)
            scope['pages'][0][key] = value
            bad.append(scope)
        for key in ('title_effects', 'publication_effects'):
            for mutation in ('missing', 'duplicate', 'selector', 'type'):
                scope = expected_scope(self.titles)
                rules = scope['pages'][0][key]
                if mutation == 'missing': rules.pop()
                if mutation == 'duplicate': rules.append(dict(rules[0]))
                if mutation == 'selector': rules[0]['selector'] = 'body *'
                if mutation == 'type': rules[0]['count' if key == 'title_effects' else 'kind'] = True
                bad.append(scope)
        scope = expected_scope(self.titles)
        scope['pages'][0]['publication_effects'][-1]['after'] = 'index'
        bad.append(scope)
        for value in (None, 7):
            scope = expected_scope(self.titles)
            scope['pages'][0]['publication_effects'][-1]['before'] = value
            bad.append(scope)
        for scope in bad:
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                backend = Mock()
                with self.assertRaises(ValueError):
                    save_forward(backend, directory, scope, document_titles=self.titles)
                backend.assert_not_called()
                backend.read.assert_not_called()
                backend.save.assert_not_called()
