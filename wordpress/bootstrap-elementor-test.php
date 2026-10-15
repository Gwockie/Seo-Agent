<?php
// ONLY synthetic local container. Its application password is consumed in memory.
$_SERVER['HTTP_HOST'] = '127.0.0.1:8879';
require '/var/www/html/wp-load.php';
if (LSEO_INSTANCE !== 'synthetic-local-wordpress' || wp_get_environment_type() !== 'local') { exit(2); }
if (ELEMENTOR_VERSION !== '3.31.3') { exit(3); }
$kit = \Elementor\Plugin::$instance->kits_manager->get_active_kit_for_frontend();
foreach (array(3,4) as $id) {
    $raw = '[ {"id":"root' . $id . '", "elType":"container", "settings":{}, "elements":[' .
        '{"id":"heading1","elType":"widget","widgetType":"heading","settings":{"title":"Our service","header_size":"h1"},"elements":[]},' .
        '{"id":"heading2","elType":"widget","widgetType":"heading","settings":{"title":"Adjacent synthetic content","header_size":"h2"},"elements":[]}' .
        ']} ]';
    // Initial fixture setup may use ordinary save APIs; the publication adapter never does.
    global $wpdb;
    $wpdb->delete($wpdb->postmeta, array('post_id'=>$id));
    update_post_meta($id, '_elementor_data', wp_slash($raw));
    update_post_meta($id, '_elementor_edit_mode', 'builder');
    update_post_meta($id, '_elementor_version', ELEMENTOR_VERSION);
    update_post_meta($id, '_wp_page_template', 'elementor_canvas');
    update_post_meta($id, '_elementor_page_settings', array());
    update_post_meta($id, 'synthetic_note', 'Preserve this unrelated row exactly');
    $mirror = \Elementor\Plugin::$instance->db->get_plain_text_from_data(json_decode($raw,true));
    $wpdb->update($wpdb->posts, array('post_content'=>$mirror,'post_excerpt'=>'Fixed synthetic explicit excerpt.'), array('ID'=>$id));
    clean_post_cache($id);
    $css = new \Elementor\Core\Files\CSS\Post($id);
    $css->update();
}
$user = get_user_by('id', LSEO_USER_ID);
WP_Application_Passwords::delete_all_application_passwords($user->ID);
$password = WP_Application_Passwords::create_new_application_password($user->ID, array('name'=>'ephemeral synthetic Elementor test'));
echo json_encode(array('username'=>$user->user_login,'password'=>$password[0]));
