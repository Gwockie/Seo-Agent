<?php
require '/var/www/html/wp-load.php';
if (wp_get_environment_type() !== 'local' || LSEO_LOCAL_INSTANCE !== 'title-rehearsal-20261117' ||
    WP_HOME !== 'http://127.0.0.1:18718') { throw new Exception('Wrong local runtime'); }
$http = wp_remote_get('https://example.invalid/local-isolation-probe', array('timeout'=>1));
$mail = wp_mail('nobody@example.invalid', 'Synthetic local isolation probe', 'Must be intercepted.');
$cron = wp_schedule_single_event(time()+3600, 'lseo_title_isolation_probe', array(), true);
if (!is_wp_error($http) || $http->get_error_code() !== 'local_staging_network_blocked' ||
    $mail !== false || !is_wp_error($cron) || get_option('blog_public') !== '0') {
    throw new Exception('Local service guards failed');
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
echo json_encode(array('http_intercepted'=>true, 'mail_intercepted'=>true, 'jobs_intercepted'=>true,
    'blog_public'=>get_option('blog_public'), 'local_instance'=>LSEO_LOCAL_INSTANCE,
    'options'=>$options,
    'elementor_data'=>$meta), JSON_THROW_ON_ERROR), "\n";
