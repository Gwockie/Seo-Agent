<?php
// ONLY the repository's synthetic disposable loopback fixture.
$_SERVER['HTTP_HOST'] = '127.0.0.1:8879';
require '/var/www/html/wp-load.php';
if (LSEO_INSTANCE !== 'synthetic-local-wordpress' || wp_get_environment_type() !== 'local') { exit(2); }
$archive = '/tmp/elementor.3.31.3.zip';
if (hash_file('sha256', $archive) !== 'dfb51239e1ff09f1447f0d6ed42946367b7daefd78c5b4a072e352ebb7fe9e36') { exit(3); }
$zip = new ZipArchive();
if ($zip->open($archive) !== true) { exit(4); }
if (!$zip->extractTo(WP_PLUGIN_DIR)) { exit(5); }
$zip->close();
require_once ABSPATH . 'wp-admin/includes/plugin.php';
$error = activate_plugin('elementor/elementor.php');
if (is_wp_error($error)) { exit(6); }
update_option('elementor_experiment-e_element_cache', 'inactive');
update_option('elementor_experiment-container', 'active');
update_option('elementor_css_print_method', 'internal');
update_option('elementor_allow_tracking', 'no');
update_option('elementor_google_font', '0');
update_option('elementor_load_fa4_shim', 'no');
echo "Synthetic Elementor package prepared\n";
