<?php
/* Disposable local CLI only. No endpoint, capability or publisher certificate. */
$request = json_decode(stream_get_contents(STDIN), true, 32, JSON_THROW_ON_ERROR);
if (!in_array($request['operation'] ?? '', array('read', 'save'), true)) {
    throw new Exception('Unsupported operation');
}
require '/var/www/html/wp-load.php';
if (wp_get_environment_type() !== 'local' ||
    !defined('LSEO_LOCAL_INSTANCE') || LSEO_LOCAL_INSTANCE !== 'title-rehearsal-20261117' ||
    WP_HOME !== 'http://127.0.0.1:18718' || DB_NAME !== 'meadow_rep' || $table_prefix !== 'rep_' ||
    !DISABLE_WP_CRON || !WP_HTTP_BLOCK_EXTERNAL) {
    throw new Exception('Wrong disposable destination');
}
$db = $wpdb->get_row('SELECT DATABASE() AS db, @@skip_networking AS offline, @@event_scheduler AS events', ARRAY_A);
if ($db['db'] !== 'meadow_rep' || (int)$db['offline'] !== 1 || $db['events'] !== 'DISABLED') {
    throw new Exception('Database isolation failed');
}
// Serialize this CLI's writers. The runtime has no browser/editor network route.
$lock = fopen('/tmp/lseo-title-rehearsal.lock', 'c');
if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) { throw new Exception('Writer already running'); }
$id = 716;
clean_post_cache($id);
$post = get_post($id, ARRAY_A, 'raw');
if (!$post || $post['post_type'] !== 'page' || $post['post_status'] !== 'publish' ||
    $post['post_name'] !== 'psychological-assessments-paoli') { throw new Exception('Wrong representative page'); }
$title = $post['post_title'];
$result = array('post_id'=>$id, 'title'=>$title, 'operation'=>$request['operation'], 'write_attempted'=>false);
if ($request['operation'] === 'save') {
    if (!is_string($request['expected'] ?? null) || !is_string($request['replacement'] ?? null) ||
        $request['expected'] === $request['replacement'] || strlen($request['replacement']) > 500) {
        throw new Exception('Invalid exact title transition');
    }
    if ($title !== $request['expected']) {
        $result['status'] = 'conflict';
    } else {
        $result['write_attempted'] = true;
        // Normal WordPress save: preserve raw strings through the API's unslashing.
        $saved = wp_update_post(wp_slash(array('ID'=>$id, 'post_title'=>$request['replacement'])), true);
        clean_post_cache($id);
        $result['title'] = get_post_field('post_title', $id, 'raw');
        $result['status'] = is_wp_error($saved) ? 'failed' : 'returned';
        $result['returned_id'] = is_wp_error($saved) ? null : $saved;
    }
} else { $result['status'] = 'read'; }
flock($lock, LOCK_UN);
echo json_encode($result, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE), "\n";
