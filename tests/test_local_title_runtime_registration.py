from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from seo_agent.coordination import run_lock
from seo_agent.local_title_rehearsal import DestinationMismatch
from tools.local_title_rehearsal import locator, migrate, run, runtime


class RuntimeRegistrationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.destination = self.root/'runtime'
        self.destination.mkdir()
        self.retired = {'app': {'id': 'a'*64}, 'db': {'id': 'b'*64}}
        self.replacement = {'app': {'id': 'c'*64}, 'db': {'id': 'd'*64}}

    def register_fixture(self):
        (self.destination/locator.OPERATION_LOCK).write_bytes(b'0')
        files = {}
        for name in locator.ACTIVE_FILES:
            path = self.destination/name
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = ((runtime.HERE/name).read_bytes() if name in locator.SUPPORTED_SOURCE
                       else b'fixture')
            path.write_bytes(payload)
            files[name] = sha256(payload).hexdigest()
        record = {
            'version': 1, 'root': str(self.destination), 'active_sha256': files,
            'retired_runtime': self.retired, 'replacement_runtime': self.replacement,
            'validation': {'original_title_restored': True, 'historical_evidence_preserved': True,
                           'private_storage_verified': True},
        }
        self.write_registration(record)
        return record

    def write_registration(self, record):
        (self.destination/locator.REGISTRATION).write_text(json.dumps(record), encoding='utf-8')

    def test_registered_runtime_requires_explicit_path_and_windows_protection(self):
        record = self.register_fixture()
        with patch.object(locator, 'require_protected') as protection:
            self.assertEqual(locator.require_registered(self.destination), record)
            protection.assert_called_once_with(self.destination)
        with run_lock(self.destination/locator.OPERATION_LOCK, create=False):
            self.assertEqual(locator.load_registration(self.destination), record)
        record['root'] = str(self.root/'elsewhere'/'runtime')
        self.write_registration(record)
        with self.assertRaisesRegex(ValueError, 'invalid or incompatible'):
            locator.load_registration(self.destination)

    def test_missing_changed_and_incompatible_writer_are_distinct(self):
        record = self.register_fixture()
        writer = self.destination/'save-title.php'
        writer.unlink()
        with self.assertRaisesRegex(ValueError, 'missing: save-title.php'):
            locator.load_registration(self.destination)
        writer.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed since registration: save-title.php'):
            locator.load_registration(self.destination)
        record['active_sha256']['save-title.php'] = locator.file_digest(writer)
        self.write_registration(record)
        with self.assertRaisesRegex(ValueError, 'source is incompatible: save-title.php'):
            locator.load_registration(self.destination)

    def test_rejects_another_container_before_any_writer_probe(self):
        self.register_fixture()
        wrong = {**self.replacement, 'app': {'id': 'e'*64}}
        with patch.object(run, 'RUNTIME_PRIVATE', self.destination), patch.object(
            run, 'inspect_runtime', return_value=wrong
        ), patch.object(run, 'verify_runtime_mounts') as probe:
            with self.assertRaisesRegex(DestinationMismatch, 'registered replacement'):
                run.Backend().read_state()
            probe.assert_not_called()

    def test_rejects_running_retired_writer_before_any_writer_probe(self):
        self.register_fixture()
        old = {'Id': self.retired['app']['id'], 'State': {'Status': 'running'}}
        with patch.object(run, 'RUNTIME_PRIVATE', self.destination), patch.object(
            run, 'inspect_runtime', return_value=self.replacement
        ), patch.object(run, 'inspect_docker', return_value=old), patch.object(run, 'verify_runtime_mounts') as probe:
            with self.assertRaisesRegex(ValueError, 'or it is running'):
                run.Backend().read_state()
            probe.assert_not_called()

    def test_migration_preserves_historical_bytes_and_exclusive_destinations(self):
        source = self.root/'source'
        source.mkdir()
        original = source/'attempt.json'
        prior = b'{ "writer_epoch":"old", "observed_utc":"2026-11-17T18:00:00+00:00" }\r\n'
        original.write_bytes(prior)
        relative = 'history/run-000001/attempt.json'
        inputs = {relative: (original, locator.file_digest(original))}
        migrate.copy_verified(inputs, self.destination)
        self.assertEqual((self.destination/relative).read_bytes(), prior)
        self.assertEqual(migrate.inventory(source), migrate.inventory((self.destination/relative).parent))
        with self.assertRaises(FileExistsError):
            migrate.copy_verified(inputs, self.destination)
        self.assertEqual(original.read_bytes(), prior)
        self.assertEqual((self.destination/relative).read_bytes(), prior)

    def test_partial_copy_and_pending_manifest_leave_destination_unregistered(self):
        source = self.root/'original.json'
        source.write_bytes(b'preserved')
        inputs = {'a.json': (source, locator.file_digest(source)),
                  'b.json': (self.root/'missing.json', '1'*64)}
        with self.assertRaisesRegex(ValueError, 'missing: missing.json'):
            migrate.copy_verified(inputs, self.destination)
        (self.destination/(locator.REGISTRATION+'.pending')).write_bytes(b'{"version":')
        self.assertEqual((self.destination/'a.json').read_bytes(), source.read_bytes())
        with self.assertRaisesRegex(ValueError, 'migration is incomplete'):
            locator.load_registration(self.destination)

    def test_conflicting_destination_rejected_before_protection_or_docker(self):
        with patch.object(migrate, 'STABLE_ROOT', self.destination), patch.object(
            migrate, 'require_protected'
        ) as protection, patch.object(runtime, 'inspect_docker') as inspect:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                migrate.inspect_inputs()
            protection.assert_not_called()
            inspect.assert_not_called()

    def test_migration_rejects_traversal_and_linked_sources(self):
        source = self.root/'source'
        source.write_bytes(b'input')
        digest = locator.file_digest(source)
        with self.assertRaisesRegex(ValueError, 'Unexpected migration path'):
            migrate.copy_verified({'../escaped': (source, digest)}, self.destination)
        self.assertFalse((self.root/'escaped').exists())
        actual_lstat = Path.lstat

        def linked_lstat(path):
            info = actual_lstat(path)
            if path == source:
                return SimpleNamespace(st_mode=info.st_mode, st_nlink=2)
            return info

        with patch.object(type(source), 'lstat', linked_lstat):
            with self.assertRaisesRegex(ValueError, 'unsafe: source'):
                migrate.copy_verified({'writer': (source, digest)}, self.destination)
        self.assertFalse((self.destination/'writer').exists())

    def test_changed_source_bytes_leave_copy_inactive(self):
        source = self.root/'config.php'
        source.write_bytes(b'original')
        digest = locator.file_digest(source)
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'copy digest mismatch'):
            migrate.copy_verified({'config.php': (source, digest)}, self.destination)
        with self.assertRaisesRegex(ValueError, 'migration is incomplete'):
            locator.load_registration(self.destination)


if __name__ == '__main__':
    unittest.main()
