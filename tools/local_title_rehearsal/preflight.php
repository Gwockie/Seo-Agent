<?php
if (PHP_SAPI !== 'cli') { exit(1); }
ob_start();
require '/var/www/html/wp-load.php';
$wpdb->suppress_errors(true);
if (wp_get_environment_type() !== 'local' || LSEO_LOCAL_INSTANCE !== 'title-rehearsal-20261117' ||
    WP_HOME !== 'http://127.0.0.1:18718' || DB_NAME !== 'meadow_rep' || $table_prefix !== 'rep_' ||
    !DISABLE_WP_CRON || !WP_HTTP_BLOCK_EXTERNAL) { throw new Exception('Wrong local runtime'); }
$db = $wpdb->get_row('SELECT DATABASE() AS db, @@skip_networking AS offline, @@event_scheduler AS events', ARRAY_A);
if (!$db || $db['db'] !== 'meadow_rep' || (int)$db['offline'] !== 1 || $db['events'] !== 'DISABLED') {
    throw new Exception('Database isolation failed');
}
$http = wp_remote_get('https://example.invalid/local-isolation-probe', array('timeout'=>1));
$mail = wp_mail('nobody@example.invalid', 'Synthetic local isolation probe', 'Must be intercepted.');
$cron = wp_schedule_single_event(time()+3600, 'lseo_title_isolation_probe', array(), true);
if (!is_wp_error($http) || $http->get_error_code() !== 'local_staging_network_blocked' ||
    $mail !== false || !is_wp_error($cron) || get_option('blog_public') !== '0') {
    throw new Exception('Local service guards failed');
}
if (getenv('LSEO_TITLE_SANITIZE') === '1') {
    // A retained empty row also prevents the installed plugin's add_option()
    // initialization from creating a new signing key when WordPress boots.
    $lock = fopen('/tmp/lseo-title-rehearsal.lock', 'c');
    if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) { throw new Exception('Writer already running'); }
    $name = 'mcp_jwt_secret';
    $query = $wpdb->prepare("SELECT option_value FROM {$wpdb->options} WHERE option_name = %s", $name);
    $stored = $wpdb->get_row($query, ARRAY_A)['option_value'] ?? null;
    if (!is_string($stored) || !preg_match('/\A[0-9a-f]{64}\z/', $stored) ||
        !update_option($name, '') || ($wpdb->get_row($query, ARRAY_A)['option_value'] ?? null) !== '') {
        throw new Exception('Signing option clear could not be confirmed');
    }
    flock($lock, LOCK_UN);
    ob_end_clean();
    echo "{\"signing_option_cleared\":true}\n";
    exit;
}
$meta = get_post_meta(716, '_elementor_data', true);
$options = $wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options}", ARRAY_A);
foreach ($options as &$option) {
    // Inspect values without constructing serialized plugin classes.
    if (is_serialized($option['option_value'])) {
        $option['option_value'] = unserialize($option['option_value'], array('allowed_classes'=>false));
    }
}
unset($option);
ob_end_clean();
echo json_encode(array('http_intercepted'=>true, 'mail_intercepted'=>true, 'jobs_intercepted'=>true,
    'blog_public'=>get_option('blog_public'), 'local_instance'=>LSEO_LOCAL_INSTANCE,
    'options'=>$options,
    'elementor_data'=>$meta), JSON_THROW_ON_ERROR), "\n";
