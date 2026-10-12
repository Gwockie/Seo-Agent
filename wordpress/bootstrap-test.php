<?php
// Synthetic loopback container only. The integration test captures credentials in
// memory; never print this script's output to a terminal/log or use it on a real site.
$_SERVER['HTTP_HOST'] = '127.0.0.1:8879';
define('WP_INSTALLING', true);
require '/var/www/html/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
if (wp_get_environment_type() !== 'local' || LSEO_INSTANCE !== 'synthetic-local-wordpress') { exit(2); }
if (!is_blog_installed()) {
    wp_install('Synthetic publishing test', 'synthetic_admin', 'nobody@example.invalid', false, '', wp_generate_password(32));
}
update_option('home', 'http://127.0.0.1:8879');
update_option('siteurl', 'http://127.0.0.1:8879');
update_option('permalink_structure', '');
require_once ABSPATH . 'wp-admin/includes/plugin.php';
activate_plugin('local-seo-publisher/local-seo-publisher.php');
switch_theme('twentytwentyfive');
$user = get_user_by('login', 'synthetic_publisher');
if (!$user) {
    $uid = wp_create_user('synthetic_publisher', wp_generate_password(32), 'publisher@example.invalid');
    $user = get_user_by('id', $uid);
    $user->set_role('lseo_publisher');
}
if ($user->ID !== LSEO_USER_ID) { exit(3); }
foreach (array(3, 4) as $id) {
    $data = array('post_type' => 'page', 'post_status' => 'publish', 'post_title' => 'Synthetic page ' . $id,
        'post_excerpt' => 'Fixed synthetic excerpt; unaffected by heading changes.',
        'post_content' => '<!-- wp:heading {"anchor":"service"} -->' . "\n" . '<h2 class="wp-block-heading" id="service">Our service</h2>' . "\n" . '<!-- /wp:heading -->' . "\n\n" . '<!-- wp:paragraph -->' . "\n" . '<p>Adjacent content stays unchanged.</p>' . "\n" . '<!-- /wp:paragraph -->');
    if (get_post($id)) { $data['ID'] = $id; wp_update_post($data); }
    else { $data['import_id'] = $id; wp_insert_post($data); }
}
WP_Application_Passwords::delete_all_application_passwords($user->ID);
$password = WP_Application_Passwords::create_new_application_password($user->ID, array('name' => 'ephemeral synthetic integration test'));
echo json_encode(array('username' => $user->user_login, 'password' => $password[0], 'wordpress' => $wp_version));
