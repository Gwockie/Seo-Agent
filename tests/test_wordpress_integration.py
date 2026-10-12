"""Opt-in real WordPress test; only the named synthetic loopback compose project."""
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from seo_agent.storage import new_id
from seo_agent.wordpress import WordPress, CMSFailure, inspect_state, rendered

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = "lseo-publishing-test-wordpress-1"


@unittest.skipUnless(os.environ.get("LSEO_WORDPRESS_TEST") == "1", "Opt-in local Docker WordPress integration")
class WordPressIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["docker", "cp", str(ROOT / "wordpress/bootstrap-test.php"), CONTAINER + ":/tmp/bootstrap-test.php"], check=True, capture_output=True)
        result = subprocess.run(["docker", "exec", CONTAINER, "php", "/tmp/bootstrap-test.php"], check=True, capture_output=True, text=True)
        # Application password is only in subprocess memory; never emit raw output.
        try:
            saved = json.loads(result.stdout)
        except ValueError:
            raise RuntimeError("Synthetic bootstrap did not return valid setup data") from None
        cls.version = saved["wordpress"]
        class MemoryVault:
            def read(self, key):
                return saved["username"], saved["password"]
        cls.vault = MemoryVault()
        cls.d = dict(url="http://127.0.0.1:8879/", instance="synthetic-local-wordpress", environment="local", credential_id=new_id())

    def setUp(self):
        self.client = WordPress(self.d, self.vault)

    def tearDown(self):
        self.client.close()

    def body(self, state, text):
        return dict(request_id=new_id(), instance=self.d["instance"], url=state["url"], token=state["token"],
                    anchor="service", block_index=state["headings"][0]["block_index"], current=state["headings"][0]["text"], proposed=text)

    def test_real_atomic_write_duplicate_verification_and_rollback(self):
        before = self.client.state(3)
        inspect_state(self.d, before, "http://127.0.0.1:8879/?page_id=3")
        source = rendered(self.client.public(before["url"]), "service", before["headings"][0]["text"])
        # WordPress may initialize its global-styles record on first public render.
        before = self.client.state(3)
        body = self.body(before, "Synthetic approved heading")
        result = self.client.write(3, body)
        self.assertEqual(result, self.client.write(3, body))
        self.assertEqual(result, self.client.operation(3, body["request_id"]))
        after = self.client.state(3)
        self.assertEqual(after["preserved"], before["preserved"])
        self.assertEqual(after["token"], result["after_token"])
        self.assertEqual(after["content"], before["content"].replace("Our service", "Synthetic approved heading"))
        self.assertEqual(source, rendered(self.client.public(before["url"]), "service", "Synthetic approved heading"))
        with self.assertRaises(CMSFailure):
            self.client.write(3, {**body, "request_id": new_id()})
        rollback = self.body(after, body["current"])
        self.client.write(3, rollback)
        self.assertEqual(self.client.state(3)["content"], before["content"])

    def test_concurrent_requests_only_one_wins(self):
        state = self.client.state(4)
        bodies = [self.body(state, "Concurrent A"), self.body(state, "Concurrent B")]
        def write(body):
            client = WordPress(self.d, self.vault)
            try:
                return client.write(4, body)["status"]
            except CMSFailure:
                return "conflict"
            finally:
                client.close()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(write, bodies))
        self.assertEqual(sorted(results), ["applied", "conflict"])
        self.client.write(4, self.body(self.client.state(4), "Our service"))

    def test_wrong_instance_object_and_unsupported_fields(self):
        state = self.client.state(3)
        for changes in ({"instance": "wrong-site"}, {"anchor": "missing"}, {"field": "post_title"}, {"proposed": "<b>rich text</b>"}):
            with self.assertRaises(CMSFailure):
                self.client.write(3, {**self.body(state, "Rejected heading"), **changes})
        with self.assertRaises(CMSFailure):
            self.client.state(1)
        self.assertEqual(self.client.state(3)["content"], state["content"])

    def test_minimal_account_cannot_use_core_write_endpoint(self):
        with self.assertRaises(CMSFailure):
            self.client.request("POST", "?rest_route=/wp/v2/pages/3", {"title": "Not authorized"})

    def fixture_php(self, code):
        bootstrap = "require '/var/www/html/wp-load.php'; if (LSEO_INSTANCE !== 'synthetic-local-wordpress' || wp_get_environment_type() !== 'local') { exit(2); } "
        subprocess.run(["docker", "exec", CONTAINER, "php", "-r", bootstrap + code], check=True, capture_output=True)

    def test_builder_metadata_is_not_treated_as_block_content(self):
        try:
            self.fixture_php("update_post_meta(3, '_elementor_data', '[]');")
            with self.assertRaises(CMSFailure):
                self.client.state(3)
        finally:
            self.fixture_php("delete_post_meta(3, '_elementor_data');")

    def test_concurrent_metadata_edit_is_preserved_and_blocks_write(self):
        state = self.client.state(3)
        try:
            self.fixture_php("update_post_meta(3, 'synthetic_note', 'human change');")
            with self.assertRaises(CMSFailure):
                self.client.write(3, self.body(state, 'Must not overwrite'))
            current = self.client.state(3)
            self.assertEqual(current['content'], state['content'])
            self.assertNotEqual(current['preserved'], state['preserved'])
        finally:
            self.fixture_php("delete_post_meta(3, 'synthetic_note');")

    def test_configuration_change_while_waiting_for_page_lock_rejects_write(self):
        # A separate CMS connection owns the page lock, then saves navigation while
        # the publisher is blocked. The publisher must read the newly committed
        # inventory, not an earlier repeatable-read snapshot.
        self.fixture_php("$GLOBALS['wpdb']->query(\"DELETE FROM {$GLOBALS['wpdb']->posts} WHERE post_name='synthetic-race-navigation'\");")
        before = self.client.state(3)
        code = """require '/var/www/html/wp-load.php';
        if (LSEO_INSTANCE !== 'synthetic-local-wordpress') { exit(2); }
        $wpdb->query('START TRANSACTION');
        $wpdb->get_row("SELECT * FROM {$wpdb->posts} WHERE ID=3 FOR UPDATE");
        echo "locked\n"; flush(); fgets(STDIN);
        $wpdb->insert($wpdb->posts, array('post_type'=>'wp_navigation', 'post_status'=>'publish',
            'post_name'=>'synthetic-race-navigation', 'post_title'=>'Concurrent navigation', 'post_content'=>''));
        $wpdb->query('COMMIT');
        """
        holder = subprocess.Popen(["docker", "exec", "-i", CONTAINER, "php", "-r", code],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            with ThreadPoolExecutor(1) as pool:
                write = pool.submit(self.client.write, 3, self.body(before, "Must not write under changed navigation"))
                waiting = False
                for _ in range(60):
                    result = subprocess.run(["docker", "exec", "lseo-publishing-test-db-1", "mariadb",
                        "-uroot", "-psynthetic-local-only", "-Nse", "SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS"],
                        capture_output=True, text=True, check=True)
                    if int(result.stdout.strip()) > 0:
                        waiting = True
                        break
                    time.sleep(0.1)
                holder.communicate("commit\n", timeout=10)
                self.assertTrue(waiting, "Publisher did not reach the locked page")
                with self.assertRaises(CMSFailure):
                    write.result(timeout=20)
            self.assertEqual(self.client.state(3)["content"], before["content"])
        finally:
            if holder.poll() is None:
                holder.communicate("commit\n", timeout=10)
            self.fixture_php("$GLOBALS['wpdb']->query(\"DELETE FROM {$GLOBALS['wpdb']->posts} WHERE post_name='synthetic-race-navigation'\");")

    def test_literal_entities_are_not_silently_decoded(self):
        before = self.client.state(3)
        proposed = "Literal &amp; and &#65; text"
        try:
            self.client.write(3, self.body(before, proposed))
            self.assertEqual(self.client.state(3)["headings"][0]["text"], proposed)
            rendered(self.client.public(before["url"]), "service", proposed)
        finally:
            state = self.client.state(3)
            if state["headings"][0]["text"] != before["headings"][0]["text"]:
                self.client.write(3, self.body(state, before["headings"][0]["text"]))


if __name__ == "__main__":
    unittest.main()
