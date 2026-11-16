import hashlib
import binascii
import io
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from seo_agent.source_manifest import Limits, manifest_archive


class SourceManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'source.zip'

    def archive(self, entries, compression=zipfile.ZIP_DEFLATED):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.path, 'w', compression=compression) as z:
                for name, value in entries:
                    z.writestr(name, value)
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def validate(self, digest=None, **kwargs):
        return manifest_archive(self.path,
            expected_sha256=digest or hashlib.sha256(self.path.read_bytes()).hexdigest(),
            prefix='copy', directories=['code'], files=['index.php'], **kwargs)

    def test_manifest_retains_packaged_files_without_extraction_or_execution(self):
        original = [('copy/', ''), ('copy/code/', ''), ('copy/code/.htaccess', 'Deny from all'),
                    ('copy/code/vendor/tests/example.php', '<?php never_execute();'), ('copy/index.php', 'entry')]
        digest = self.archive(original)
        before = self.path.read_bytes()
        result = self.validate(digest)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(list(self.root.iterdir()), [self.path])
        self.assertEqual(result['source_bytes'], sum(len(x.encode()) for _, x in original))
        self.assertEqual(result['files'][1]['sha256'], hashlib.sha256(b'<?php never_execute();').hexdigest())
        self.assertEqual(result['directories'], ['code', 'code/vendor', 'code/vendor/tests'])
        self.assertIn('No extraction', result['limits'])
        self.assertNotIn('publishing_compatible', result)

    def test_tree_hash_ignores_zip_order_compression_and_explicit_parent_entries(self):
        items = [('copy/code/a.php', 'alpha'), ('copy/index.php', 'entry')]
        self.archive(items)
        first = self.validate()
        self.archive([('copy/code/', '')] + list(reversed(items)), zipfile.ZIP_STORED)
        second = self.validate()
        self.assertNotEqual(first['archive_sha256'], second['archive_sha256'])
        self.assertEqual(first['tree_sha256'], second['tree_sha256'])
        self.archive([('copy/code/a.php', 'changed'), ('copy/index.php', 'entry')])
        self.assertNotEqual(first['tree_sha256'], self.validate()['tree_sha256'])

    def test_wrong_digest_and_missing_approved_items(self):
        self.archive([('copy/code/a.php', 'data'), ('copy/index.php', 'entry')])
        with self.assertRaisesRegex(ValueError, 'retained SHA256'):
            self.validate('0' * 64)
        for missing in [('copy/code/a.php', 'data'), ('copy/index.php', 'entry')]:
            self.archive([missing])
            with self.assertRaisesRegex(ValueError, 'missing'):
                self.validate()

    def test_forged_directory_count_is_rejected_before_zipfile_allocation(self):
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        raw = bytearray(self.path.read_bytes())
        end = raw.rfind(b'PK\x05\x06')
        struct.pack_into('<HH', raw, end + 8, 1, 1)
        self.path.write_bytes(raw)
        with patch('zipfile.ZipFile', side_effect=AssertionError('must not allocate')):
            with self.assertRaises(ValueError):
                self.validate(limits=Limits(entries=1))

    def test_omitted_local_member_cannot_hide_outside_the_manifest(self):
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')], zipfile.ZIP_STORED)
        original = self.path.read_bytes()
        extra = io.BytesIO()
        with zipfile.ZipFile(extra, 'w') as z:
            z.writestr('copy/wp-config.php', 'synthetic excluded value')
        extra = extra.getvalue()
        orphan = extra[:struct.unpack_from('<L', extra, len(extra) - 6)[0]]
        start = struct.unpack_from('<L', original, len(original) - 6)[0]
        forged = bytearray(original[:start] + orphan + original[start:])
        struct.pack_into('<L', forged, len(forged) - 6, start + len(orphan))
        self.path.write_bytes(forged)
        with self.assertRaisesRegex(ValueError, 'Unindexed'):
            self.validate()

    def test_stored_truncation_and_deflate_trailing_bytes_are_rejected(self):
        self.archive([('copy/code/a', 'ABCD'), ('copy/index.php', '')], zipfile.ZIP_STORED)
        raw = bytearray(self.path.read_bytes())
        central = raw.index(b'PK\x01\x02')
        struct.pack_into('<L', raw, central + 16, binascii.crc32(b'A'))
        struct.pack_into('<L', raw, central + 24, 1)
        struct.pack_into('<L', raw, 14, binascii.crc32(b'A'))
        struct.pack_into('<L', raw, 22, 1)
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'Stored archive lengths'):
            self.validate()
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        with zipfile.ZipFile(self.path) as z:
            last = z.infolist()[-1]
        raw = self.path.read_bytes()
        central_start = struct.unpack_from('<L', raw, len(raw) - 6)[0]
        forged = bytearray(raw[:central_start] + b'junk' + raw[central_start:])
        central_last = forged.rfind(b'PK\x01\x02')
        struct.pack_into('<L', forged, central_last + 20, last.compress_size + 4)
        struct.pack_into('<L', forged, last.header_offset + 18, last.compress_size + 4)
        struct.pack_into('<L', forged, len(forged) - 6, central_start + 4)
        self.path.write_bytes(forged)
        with self.assertRaisesRegex(ValueError, 'Trailing bytes'):
            self.validate()

    def test_small_zip64_local_headers_are_rejected(self):
        with zipfile.ZipFile(self.path, 'w') as z:
            with z.open('copy/code/a', 'w', force_zip64=True) as f:
                f.write(b'data')
            z.writestr('copy/index.php', '')
        with self.assertRaises(ValueError):
            self.validate()

    def test_derived_tree_depth_nodes_and_path_bytes_are_bounded(self):
        self.archive([('copy/code/' + 'a/' * 40 + 'file', 'data'), ('copy/index.php', '')])
        with self.assertRaises(ValueError):
            self.validate()
        self.archive([('copy/code/a/b/c/file', 'data'), ('copy/index.php', '')])
        for limits in (Limits(path_depth=4), Limits(tree_nodes=3), Limits(tree_path_bytes=10)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                self.validate(limits=limits)

    def test_portable_reserved_names_rejected_posix_names_preserved(self):
        for name in ('NUL.php', 'CON', 'COM1.txt', 'LPT²', 'CONIN$', 'CONOUT$',
                     'NUL .txt', 'COM1 .php', 'bad?.php', 'a|b', 'quote".php'):
            with self.subTest(name=name):
                self.archive([('copy/code/' + name, 'x'), ('copy/index.php', '')])
                with self.assertRaises(ValueError):
                    self.validate()
                self.assertEqual(len(self.validate(path_semantics='posix')['files']), 2)

    def test_bounded_streaming_deflate_and_data_descriptors(self):
        # Incompressible data spans several bounded inflater chunks.
        value = b''.join(hashlib.sha256(str(n).encode()).digest() for n in range(5000))
        class Unseekable(io.BytesIO):
            def seek(self, *args):
                raise io.UnsupportedOperation()
        output = Unseekable()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('copy/code/data', value)
            z.writestr('copy/index.php', 'entry')
        self.path.write_bytes(output.getvalue())
        result = self.validate()
        self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(value).hexdigest())
        self.assertEqual(result['source_bytes'], len(value) + 5)

    def test_empty_approved_directory_is_evidence(self):
        self.archive([('copy/code/', ''), ('copy/index.php', '')])
        self.assertEqual(self.validate()['directories'], ['code'])

    def test_path_escape_and_unapproved_files(self):
        for name in ('outside.php', 'copy2/code/a.php', 'copy/../code/a.php',
                     'copy/code/../../escape.php', '/copy/code/a.php', 'copy/code\\escape.php',
                     'copy/code/a.php:stream', 'copy/code/./a.php', 'copy/code//a.php',
                     'copy/code/file. ', 'copy/wp-config.php', 'copy/code2/a.php'):
            with self.subTest(name=name):
                self.archive([('copy/code/a.php', 'data'), ('copy/index.php', ''), (name, '')])
                if '\\' in name:
                    # Windows ZipInfo writing normalizes separators. Inject the
                    # malformed wire spelling into both ZIP name records.
                    self.path.write_bytes(self.path.read_bytes().replace(name.replace('\\', '/').encode(), name.encode()))
                with self.assertRaises(ValueError):
                    self.validate()

    def test_duplicate_case_unicode_and_file_parent_aliases(self):
        for first, second in [('copy/code/a.php', 'copy/code/a.php'),
                              ('copy/code/a.php', 'copy/code/A.php'),
                              ('copy/code/caf\u00e9.php', 'copy/code/cafe\u0301.php'),
                              ('copy/code/sub', 'copy/code/sub/a.php'),
                              ('copy/code/Sub', 'copy/code/sub/a.php'),
                              ('copy/code/Sub/a.php', 'copy/code/sub/b.php')]:
            with self.subTest(first=first, second=second):
                self.archive([(first, 'x'), (second, 'y'), ('copy/index.php', '')])
                with self.assertRaises(ValueError):
                    self.validate()

    def test_links_special_files_and_directory_type_conflicts(self):
        for mode, name in [(stat.S_IFLNK, 'copy/code/a'), (stat.S_IFIFO, 'copy/code/a'),
                           (stat.S_IFCHR, 'copy/code/a'), (stat.S_IFDIR, 'copy/code/a'),
                           (stat.S_IFREG, 'copy/code/a/')]:
            with self.subTest(mode=mode):
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (mode | 0o600) << 16
                self.archive([(info, ''), ('copy/index.php', '')])
                with self.assertRaises(ValueError):
                    self.validate()

    def test_explicit_posix_manifest_preserves_linux_case_distinct_sources(self):
        self.archive([('copy/code/services/a.php', 'a'), ('copy/code/Services/a.php', 'b'), ('copy/index.php', '')])
        with self.assertRaises(ValueError):
            self.validate()
        report = self.validate(path_semantics='posix')
        self.assertEqual(report['path_semantics'], 'posix')
        self.assertEqual([f['path'] for f in report['files']], ['code/Services/a.php', 'code/services/a.php', 'index.php'])
        self.assertNotEqual(report['files'][0]['sha256'], report['files'][1]['sha256'])
        self.archive([('copy/code/a.php', 'a'), ('copy/code/a.php', 'b'), ('copy/index.php', '')])
        with self.assertRaises(ValueError):
            self.validate(path_semantics='posix')
        with self.assertRaises(ValueError):
            self.validate(path_semantics='guess')

    def test_limits_reject_before_member_reads_or_unbounded_directory_loading(self):
        self.archive([('copy/code/a', 'a' * 100), ('copy/index.php', 'b' * 100)])
        for limits in (Limits(archive_bytes=10), Limits(entries=1), Limits(central_bytes=20)):
            with self.subTest(limits=limits), patch('zipfile.ZipFile', side_effect=AssertionError('must not parse')):
                with self.assertRaises(ValueError):
                    self.validate(limits=limits)
        for limits in (Limits(source_bytes=199), Limits(file_bytes=99), Limits(compression_ratio=1)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                self.validate(limits=limits)
        with self.assertRaisesRegex(ValueError, 'tighten'):
            self.validate(limits=Limits(entries=60_001))

    def test_bad_crc_unsupported_compression_and_trailing_layout(self):
        self.archive([('copy/code/a', 'original'), ('copy/index.php', '')], zipfile.ZIP_STORED)
        raw = self.path.read_bytes().replace(b'original', b'corrupt!')
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.validate()
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')], zipfile.ZIP_BZIP2)
        with self.assertRaises(ValueError):
            self.validate()
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        self.path.write_bytes(self.path.read_bytes() + b'trailing bytes')
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.validate()

    def test_encrypted_and_zip64_claims_are_rejected(self):
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        raw = bytearray(self.path.read_bytes())
        central = raw.index(b'PK\x01\x02')
        struct.pack_into('<H', raw, central + 34, 1)
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'Multipart'):
            self.validate()
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        raw = bytearray(self.path.read_bytes())
        central = raw.index(b'PK\x01\x02')
        raw[central + 8] |= 1
        self.path.write_bytes(raw)
        with self.assertRaises(ValueError):
            self.validate()
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        raw = bytearray(self.path.read_bytes())
        end = raw.rfind(b'PK\x05\x06')
        struct.pack_into('<HH', raw, end + 8, 65_535, 65_535)
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.validate()

    def test_no_misleading_success_when_archive_changes_during_validation(self):
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        import seo_agent.source_manifest as module
        real_digest = module._digest
        count = 0
        def changing_digest(handle):
            nonlocal count
            count += 1
            return real_digest(handle) if count == 1 else '0' * 64
        with patch.object(module, '_digest', side_effect=changing_digest):
            with self.assertRaisesRegex(ValueError, 'changed during'):
                self.validate()

    def test_ambiguous_allowlists_and_file_directory_swaps(self):
        self.archive([('copy/code/a', 'data'), ('copy/index.php', '')])
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        for directories, files in [([], []), (['code'], ['code/a']), (['code'], ['CODE']),
                                   (['../code'], []), ('code', ['index.php'])]:
            with self.subTest(directories=directories, files=files), self.assertRaises(ValueError):
                manifest_archive(self.path, expected_sha256=digest, prefix='copy', directories=directories, files=files)
        for entries in [[('copy/code', ''), ('copy/index.php', '')],
                        [('copy/code/a', ''), ('copy/index.php/', '')]]:
            self.archive(entries)
            with self.assertRaises(ValueError):
                self.validate()


if __name__ == '__main__':
    unittest.main()
