"""Real pinned Elementor writes, opt-in and loopback-only. No live credentials."""
import copy
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from seo_agent import elementor_publishing as ep
from seo_agent.elementor import map_heading, preview_heading, _parse
from seo_agent.storage import new_id
from seo_agent.wordpress import WordPress, CMSFailure
from tests import test_wordpress_integration as core

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = core.CONTAINER


@unittest.skipUnless(os.environ.get("LSEO_ELEMENTOR_TEST") == "1", "Opt-in real Docker Elementor integration")
class ElementorIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Creates synthetic base installation and minimal account if absent.
        core.WordPressIntegration.setUpClass()
        package = ROOT / '.tmp/elementor.3.31.3.zip'
        import hashlib
        if hashlib.sha256(package.read_bytes()).hexdigest() != ep.contract_manifest()["elementor_archive_sha256"]:
            raise RuntimeError("Official pinned synthetic Elementor package is missing or differs")
        subprocess.run(["docker", "cp", str(package), CONTAINER + ":/tmp/elementor.3.31.3.zip"], check=True, capture_output=True)
        for name in ('prepare-elementor-test.php', 'bootstrap-elementor-test.php'):
            subprocess.run(["docker", "cp", str(ROOT / 'wordpress' / name), CONTAINER + ':/tmp/' + name], check=True, capture_output=True)
            result = subprocess.run(["docker", "exec", CONTAINER, "php", "/tmp/" + name], check=True, capture_output=True, text=True)
        try:
            saved = json.loads(result.stdout)
        except ValueError:
            raise RuntimeError("Synthetic Elementor bootstrap failed; raw credential-bearing output suppressed") from None
        class Vault:
            def read(self, _): return saved["username"], saved["password"]
        cls.vault = Vault()
        cls.d = dict(url="http://127.0.0.1:8879/", instance="synthetic-local-wordpress", environment="local", credential_id=new_id(), adapter=ep.ADAPTER)
        # Public rendering during fixture setup initializes generated assets/kit.
        with_client = WordPress(cls.d, cls.vault)
        try:
            for page in (3,4):
                with_client.public(cls.d['url'] + '?page_id=' + str(page))
        finally:
            with_client.close()

    def setUp(self):
        self.client = WordPress(self.d, self.vault)

    def tearDown(self):
        self.client.close()

    def php(self, code, output=False):
        guard = "$_SERVER['HTTP_HOST']='127.0.0.1:8879'; require '/var/www/html/wp-load.php'; if (LSEO_INSTANCE!=='synthetic-local-wordpress'||wp_get_environment_type()!=='local') { exit(2); } "
        result = subprocess.run(["docker", "exec", CONTAINER, "php", "-r", guard + code], check=True, capture_output=True, text=True)
        return result.stdout if output else None

    def body(self, state, text, token=None):
        m = map_heading(state['elementor_data'], page_id=state['id'], element_id='heading1')
        return dict(request_id=new_id(), instance=self.d['instance'], environment=self.d['environment'], url=state['url'],
            token=state['token'], current=m.current, proposed=text, adapter=ep.ADAPTER, contract=ep.CONTRACT,
            metadata_row_id=state['metadata_row_id'], element_id=m.element_id, path=list(m.path),
            replacement_token=json.dumps(text) if token is None else token)

    def restore(self, before):
        after = self.client.state(before['id'])
        m = map_heading(before['elementor_data'], page_id=before['id'], element_id='heading1')
        if after['elementor_data'] != before['elementor_data']:
            _, spans = _parse(before['elementor_data']); start, end = spans[m.path]
            self.client.write(before['id'], self.body(after, m.current, before['elementor_data'][start:end]))

    def test_exact_apply_duplicate_raw_mirror_assets_render_and_inverse(self):
        before = self.client.state(3)
        ep.inspect_state(self.d, before, before['url'])
        m = map_heading(before['elementor_data'], page_id=3, element_id='heading1')
        rendered = ep.render(self.client.public(before['url']), m, m.current)
        body = self.body(before, 'Synthetic revised heading – City')
        try:
            result = self.client.write(3, body)
            self.assertEqual(result, self.client.write(3, body))
            self.assertEqual(result, self.client.operation(3, body['request_id']))
            after = self.client.state(3)
            self.assertEqual(after['elementor_data'], preview_heading(before['elementor_data'], m, body['proposed']))
            self.assertEqual(after['content'], ep.mirror_candidate(before['content'], before['headings'], 'heading1', body['proposed']))
            self.assertEqual(after['preserved'], before['preserved'])
            self.assertEqual(after['assets_hash'], before['assets_hash'])
            self.assertEqual(after['token'], result['after_token'])
            self.assertEqual(ep.render(self.client.public(before['url']), m, body['proposed']), rendered)
            # A public GET must not lazily change CSS/metadata after the write.
            self.assertEqual(self.client.state(3)['token'], result['after_token'])
        finally:
            self.restore(before)
        self.assertEqual(self.client.state(3)['elementor_data'], before['elementor_data'])
        self.assertEqual(self.client.state(3)['content'], before['content'])

    def test_concurrent_requests_only_one_commits(self):
        before = self.client.state(4)
        def send(body):
            client = WordPress(self.d, self.vault)
            try:
                client.write(4, body)
                return 'applied'
            except CMSFailure:
                return 'conflict'
            finally:
                client.close()
        try:
            with ThreadPoolExecutor(2) as pool:
                result = list(pool.map(send, [self.body(before, 'Concurrent A'), self.body(before, 'Concurrent B')]))
            self.assertEqual(sorted(result), ['applied','conflict'])
        finally:
            self.restore(before)

    def test_wrong_scope_row_field_token_and_entity_rejected(self):
        before = self.client.state(3)
        for fields in ({'instance':'other'}, {'environment':'production'}, {'metadata_row_id':-1}, {'element_id':'missing'},
                       {'path':[0]}, {'field':'post_title'}, {'contract':'other'}, {'token':'0'*64},
                       {'proposed':'A &amp; B', 'replacement_token':'"A &amp; B"'}, {'replacement_token':'"Different"'}):
            with self.subTest(fields=fields), self.assertRaises(CMSFailure):
                self.client.write(3, {**self.body(before,'Rejected'), **fields})
        with self.assertRaises(CMSFailure): self.client.state(1)
        self.assertEqual(self.client.state(3)['token'], before['token'])

    def test_metadata_and_configuration_conflicts_preserve_concurrent_edit(self):
        before = self.client.state(3)
        self.php("update_post_meta(3,'synthetic_note','Concurrent human metadata');")
        try:
            with self.assertRaises(CMSFailure): self.client.write(3, self.body(before,'Rejected'))
            self.assertEqual(self.client.state(3)['elementor_data'], before['elementor_data'])
        finally:
            self.php("update_post_meta(3,'synthetic_note','Preserve this unrelated row exactly');")
        before = self.client.state(3)
        original = self.php("echo json_encode(get_option('posts_per_page'));", output=True)
        self.php("update_option('posts_per_page',27);")
        try:
            with self.assertRaises(CMSFailure): self.client.write(3, self.body(before,'Rejected'))
        finally:
            self.php("update_option('posts_per_page',json_decode('" + original + "')); ")

    def test_mirror_shared_nested_dynamic_and_duplicate_metadata_fail_closed(self):
        before = self.client.state(3)
        for mutation in (
            "$wpdb->update($wpdb->posts,array('post_content'=>'Unmatched mirror'),array('ID'=>3));",
            "update_post_meta(3,'_elementor_data',wp_slash(str_replace('heading1','heading2',get_post_meta(3,'_elementor_data',true))));",
            "update_post_meta(3,'_elementor_data',wp_slash(str_replace('\"widgetType\":\"heading\"','\"widgetType\":\"template\"',get_post_meta(3,'_elementor_data',true))));",
            "update_post_meta(3,'_elementor_data',wp_slash(str_replace('\"header_size\":\"h1\"','\"header_size\":\"h1\",\"__dynamic__\":{\"title\":\"shared\"}',get_post_meta(3,'_elementor_data',true))));",
            "$wpdb->insert($wpdb->postmeta,array('post_id'=>3,'meta_key'=>'_elementor_data','meta_value'=>'[]'));",
        ):
            try:
                self.php(mutation)
                with self.assertRaises(CMSFailure): self.client.state(3)
            finally:
                # Synthetic recovery bypasses the adapter only to restore rejected fixtures.
                raw, content = json.dumps(before['elementor_data']), json.dumps(before['content'])
                self.php("$wpdb->query(\"DELETE FROM {$wpdb->postmeta} WHERE post_id=3 AND meta_key='_elementor_data' AND meta_id<>" + str(before['metadata_row_id']) + "\");"
                    + "$wpdb->update($wpdb->postmeta,array('meta_value'=>json_decode(" + json.dumps(raw) + ",true)),array('meta_id'=>" + str(before['metadata_row_id']) + "));"
                    + "$wpdb->update($wpdb->posts,array('post_content'=>json_decode(" + json.dumps(content) + ",true)),array('ID'=>3));")

    def test_committed_journal_survives_incompatible_stack_then_missing_journal_is_unknown(self):
        before = self.client.state(3)
        body = self.body(before,'Journal test heading')
        try:
            result = self.client.write(3, body)
            self.php("update_option('elementor_experiment-e_element_cache','active');")
            try:
                with self.assertRaises(CMSFailure): self.client.state(3)
                self.assertEqual(result, self.client.operation(3, body['request_id']))
                self.assertEqual(result, self.client.write(3, body))
            finally:
                self.php("update_option('elementor_experiment-e_element_cache','inactive');")
            self.php("$wpdb->delete($wpdb->prefix.'lseo_operations',array('request_id'=>'" + body['request_id'] + "'));")
            self.assertEqual(self.client.operation(3, body['request_id']), {'status':'unknown'})
            with self.assertRaises(CMSFailure): self.client.write(3, body)
        finally:
            self.restore(before)

    def test_minimal_account_and_core_route_stay_restricted(self):
        with self.assertRaises(CMSFailure): self.client.request('POST', '?rest_route=/wp/v2/pages/3', {'content':'Forbidden'})
        with self.assertRaises(CMSFailure): self.client.request('GET', '?rest_route=/local-seo/v1/pages/3')

    def test_waiting_writer_rechecks_concurrent_configuration_template_and_content(self):
        for kind in ('configuration', 'template', 'content'):
            with self.subTest(kind=kind):
                before = self.client.state(3)
                table = 'options' if kind == 'configuration' else 'posts'
                original = self.php("echo json_encode(get_option('posts_per_page'));", output=True)
                mutation = {
                    'configuration': "$wpdb->update($wpdb->options,array('option_value'=>'27'),array('option_name'=>'posts_per_page'));",
                    'template': "$wpdb->insert($wpdb->posts,array('post_author'=>1,'post_type'=>'wp_template','post_status'=>'publish','post_name'=>'synthetic-elementor-race','post_content'=>''));",
                    'content': "$wpdb->update($wpdb->posts,array('post_content'=>'Concurrent human edit'),array('ID'=>3));",
                }[kind]
                code = "$_SERVER['HTTP_HOST']='127.0.0.1:8879'; require '/var/www/html/wp-load.php'; if(LSEO_INSTANCE!=='synthetic-local-wordpress')exit(2); " + \
                    "$wpdb->query('START TRANSACTION'); $wpdb->query(\"SELECT * FROM {$wpdb->" + table + "} FOR UPDATE\"); echo \"locked\\n\"; flush(); fgets(STDIN); " + mutation + "$wpdb->query('COMMIT');"
                holder = subprocess.Popen(['docker','exec','-i',CONTAINER,'php','-r',code],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.assertEqual(holder.stdout.readline().strip(), 'locked')
                    with ThreadPoolExecutor(1) as pool:
                        write = pool.submit(self.client.write, 3, self.body(before, 'Must preserve concurrent change'))
                        waiting = False
                        for _ in range(40):
                            result = subprocess.run(['docker','exec','lseo-publishing-test-db-1','mariadb',
                                '-uroot','-psynthetic-local-only','-Nse','SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS'],
                                capture_output=True, text=True, check=True)
                            if int(result.stdout.strip()):
                                waiting = True
                                break
                            time.sleep(0.1)
                        holder.communicate('commit\n', timeout=10)
                        self.assertTrue(waiting, 'Publisher never reached the held inventory lock')
                        with self.assertRaises(CMSFailure): write.result(timeout=20)
                    raw = self.php("echo get_post_meta(3,'_elementor_data',true);", output=True)
                    self.assertEqual(raw, before['elementor_data'])
                    if kind == 'content':
                        self.assertEqual(self.php("echo get_post(3)->post_content;", output=True), 'Concurrent human edit')
                finally:
                    if holder.poll() is None: holder.communicate('commit\n', timeout=10)
                    self.php("$wpdb->query(\"DELETE FROM {$wpdb->posts} WHERE post_name='synthetic-elementor-race'\");"
                        + "$wpdb->update($wpdb->posts,array('post_content'=>json_decode(" + json.dumps(json.dumps(before['content'])) + ",true)),array('ID'=>3));"
                        + "update_option('posts_per_page',json_decode('" + original + "'));")

    def test_timeout_after_real_commit_reconciles_with_rotated_credentials(self):
        before = self.client.state(3)
        body = self.body(before, 'Synthetic committed before timeout')
        try:
            def timed_out():
                self.client.write(3, body)
                raise CMSFailure('Synthetic response lost after server commit')
            with self.assertRaises(CMSFailure): timed_out()
            saved = json.loads(self.php("$u=get_user_by('id',LSEO_USER_ID); WP_Application_Passwords::delete_all_application_passwords($u->ID); "
                + "$p=WP_Application_Passwords::create_new_application_password($u->ID,array('name'=>'rotated synthetic')); echo json_encode(array($u->user_login,$p[0]));", output=True))
            class RotatedVault:
                def read(self, _): return tuple(saved)
            type(self).vault = RotatedVault()
            self.client.close()
            self.client = WordPress({**self.d, 'credential_id':new_id()}, self.vault)
            result = self.client.operation(3, body['request_id'])
            self.assertEqual(result['status'], 'applied')
            self.assertEqual(result['request'], body)
            self.assertEqual(self.client.state(3)['token'], result['after_token'])
            self.assertEqual(self.client.write(3, body), result)
        finally:
            self.restore(before)
