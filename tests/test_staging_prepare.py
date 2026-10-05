import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_staging import mapped_files, prepare, safe_path, target_settings


def configuration():
    return {
        "schema_version": 1, "environment": "staging", "remote_writes_enabled": False,
        "staging_site_url": "https://staging1.practice.example",
        "production_site_url": "https://practice.example",
        "staging_wp_root": "/www/staging1.practice.example/public_html",
        "production_wp_root": "/www/practice.example/public_html",
        "theme_slug": "practice-child",
        "theme_dir": "/www/staging1.practice.example/public_html/wp-content/themes/practice-child",
        "files": [{"source": "src/schema/test.json", "target": "assets/schema/test.json"}],
    }


class StagingPreparationTests(unittest.TestCase):
    def test_local_payload_and_manifest_hashes_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "src/schema/test.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"confirmed": false}', encoding="utf-8")
            config = root / "config.json"
            config.write_text(json.dumps(configuration()), encoding="utf-8")
            release = prepare(config, root, {})
            manifest_data = (release / "manifest.json").read_bytes()
            manifest = json.loads(manifest_data)
            payload = (release / "payload/assets/schema/test.json").read_bytes()
            self.assertEqual(payload, source.read_bytes())
            self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual((release / "manifest.sha256").read_text().strip(),
                             hashlib.sha256(manifest_data).hexdigest())
            self.assertFalse(manifest["remote_writes_enabled"])
            self.assertIn("UNKNOWN", (release / "review.md").read_text())
            self.assertEqual(list(release.glob("*.sftp")), [])

    def test_production_and_ambiguous_targets_refused(self):
        cases = [
            {"environment": "production"}, {"remote_writes_enabled": True},
            {"staging_site_url": "https://www.practice.example"},
            {"staging_wp_root": "/www/practice.example/public_html"},
            {"staging_wp_root": "/www/practice.example/public_html/staging"},
            {"production_wp_root": "/www"},
            {"theme_dir": "/www/practice.example/public_html/wp-content/themes/practice-child"},
            {"staging_site_url": "https://user:password@staging1.practice.example"},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                target_settings(configuration() | overrides, {})

    def test_missing_env_variable_is_not_silently_used(self):
        config = configuration() | {"staging_wp_root": "${SG_STAGING_WP_ROOT}"}
        with self.assertRaises(ValueError):
            target_settings(config, {})
        self.assertEqual(target_settings(config, {"SG_STAGING_WP_ROOT": configuration()["staging_wp_root"]})
                         ["staging_wp_root"], configuration()["staging_wp_root"])

    def test_path_traversal_and_batch_injection_refused(self):
        for path in ["../secrets/token.json", "/outside/test.json", "src/../test.json",
                     "assets//test.json", "assets\\test.json", 'a"b.json', "a\nput-secret.json"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_path(path)

    def test_secrets_docs_empty_maps_and_duplicates_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "src/schema/test.json"
            source.parent.mkdir(parents=True)
            source.write_text("{}", encoding="utf-8")
            bad_maps = [[], [{"source": "secrets/token.json", "target": "assets/token.json"}],
                        [{"source": "src/schema/README.md", "target": "README.md"}],
                        configuration()["files"] * 2,
                        configuration()["files"] + [{"source": "src/schema/test.json",
                                                     "target": "ASSETS/schema/TEST.json"}],
                        [{"source": "src/schema/test.json", "target": "payload.php"}]]
            for files in bad_maps:
                with self.subTest(files=files), self.assertRaises(ValueError):
                    mapped_files(configuration() | {"files": files}, root)

    def test_invalid_json_and_missing_php_runtime_stop_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "src/schema/test.json"
            source.parent.mkdir(parents=True)
            for content in ['{"bad":NaN}', '{"x":1,"x":2}', '{broken']:
                source.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    mapped_files(configuration(), root)
            php = root / "src/schema/test.php"
            php.write_text("<?php // local example", encoding="utf-8")
            config = configuration() | {"files": [{"source": "src/schema/test.php", "target": "test.php"}]}
            with patch("scripts.prepare_staging.shutil.which", return_value=None), self.assertRaises(ValueError):
                mapped_files(config, root)


if __name__ == "__main__":
    unittest.main()
