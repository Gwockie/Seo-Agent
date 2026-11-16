"""Failure probes for the disposable, synthetic publisher container only."""
import json
import subprocess

from seo_agent.wordpress import CMSFailure


def reject_nontransactional_tables(test, container):
    if container != "lseo-publishing-test-wordpress-1":
        raise RuntimeError("Wrong synthetic fixture container")
    # Verify the actual container provenance before DDL, not merely its name.
    info = json.loads(subprocess.run(["docker", "inspect", container], check=True,
                                    capture_output=True, text=True).stdout)[0]
    labels = info["Config"]["Labels"]
    if (labels.get("com.docker.compose.project") != "lseo-publishing-test"
            or labels.get("com.docker.compose.service") != "wordpress"):
        raise RuntimeError("Wrong synthetic fixture provenance")

    def php(code):
        guard = ("$_SERVER['HTTP_HOST']='127.0.0.1:8879'; require '/var/www/html/wp-load.php'; "
                 "if (LSEO_INSTANCE!=='synthetic-local-wordpress'||wp_get_environment_type()!=='local' "
                 "||$wpdb->dbname!=='wordpress'||$wpdb->prefix!=='wp_') { exit(2); } ")
        result = subprocess.run(["docker", "exec", container, "php", "-r", guard + code],
                                check=True, capture_output=True, text=True)
        return result.stdout

    snapshot = (
        "$posts=$wpdb->get_results(\"SELECT * FROM {$wpdb->posts} WHERE ID IN (3,4) ORDER BY ID\",ARRAY_A);"
        "$meta=$wpdb->get_results(\"SELECT * FROM {$wpdb->postmeta} WHERE post_id IN (3,4) ORDER BY meta_id\",ARRAY_A);"
        "$journal=$wpdb->get_results(\"SELECT * FROM {$wpdb->prefix}lseo_operations ORDER BY request_id\",ARRAY_A);"
        "if ($wpdb->last_error) { exit(3); } echo hash('sha256',serialize(array($posts,$meta,$journal)));"
    )
    # Keep a known success to prove that later incompatibility does not erase it.
    before = test.client.state(3)
    body = test.body(before, "Synthetic engine-check heading")
    committed = test.client.write(3, body)
    test.client.write(3, test.body(test.client.state(3), body["current"]))
    for role in ("posts", "postmeta", "options", "lseo_operations"):
        with test.subTest(engine="MyISAM", table=role):
            state = test.client.state(3)
            fresh = test.body(state, "Must remain blocked")
            baseline = php(snapshot)
            # Only literal fixture table names, never imported or user input.
            table = "wp_" + role
            try:
                php(f"if ($wpdb->query('ALTER TABLE {table} ENGINE=MyISAM')===false) {{ exit(4); }}")
                with test.assertRaises(CMSFailure):
                    test.client.state(3)
                with test.assertRaises(CMSFailure):
                    test.client.write(3, fresh)
                test.assertEqual(php(snapshot), baseline, "Rejected request changed content, timestamps, metadata or journal")
                test.assertEqual(test.client.operation(3, body["request_id"]), committed)
            finally:
                php(f"if ($wpdb->query('ALTER TABLE {table} ENGINE=InnoDB')===false) {{ exit(4); }}")
            test.assertEqual(php(snapshot), baseline)
            test.assertEqual(test.client.state(3)["content"], state["content"])
