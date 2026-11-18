<?php
/* App inspection uses SQL reads only. Loading WordPress can run write hooks. */
if (PHP_SAPI !== 'cli') { exit(1); }
$lock = fopen('/tmp/lseo-title-rehearsal.lock', 'c');
if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) { exit(1); }
$boot = trim(file_get_contents('/proc/sys/kernel/random/boot_id'));
$stat = file_get_contents('/proc/1/stat');
$fields = explode(' ', substr($stat, strrpos($stat, ') ') + 2));
$started = $fields[19] ?? '';
if (!preg_match('/^[0-9a-f-]{36}$/D', $boot) || !ctype_digit($started)) { exit(1); }

mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
$password = trim(file_get_contents('/run/secrets/db-user'));
$db = new mysqli('localhost', 'meadow_rep', $password, 'meadow_rep', 0, '/run/lseo-db/mysql.sock');
$db->set_charset('utf8mb4');
$db->begin_transaction(MYSQLI_TRANS_START_READ_ONLY);
$server = $db->query('SELECT DATABASE() AS db, @@skip_networking AS offline, @@event_scheduler AS events')->fetch_assoc();
if ($server['db'] !== 'meadow_rep' || (int)$server['offline'] !== 1 || $server['events'] !== 'DISABLED') {
    echo '{"blocker":"isolation"}';
    exit;
}
$post = $db->query('SELECT post_type, post_status, post_name, post_title FROM rep_posts WHERE ID = 716')->fetch_assoc();
if (!$post || $post['post_type'] !== 'page' || $post['post_status'] !== 'publish' ||
    $post['post_name'] !== 'psychological-assessments-paoli') {
    echo '{"blocker":"page"}';
    exit;
}
$options = $db->query("SELECT option_name, option_value FROM rep_options WHERE option_name IN ('blog_public', 'mcp_jwt_secret')");
$values = array_column($options->fetch_all(MYSQLI_ASSOC), 'option_value', 'option_name');
if (($values['blog_public'] ?? null) !== '0') {
    echo '{"blocker":"isolation"}';
    exit;
}
if (($values['mcp_jwt_secret'] ?? null) !== '') {
    echo '{"blocker":"signing_option"}';
    exit;
}
$heading = $db->query("SELECT meta_value FROM rep_postmeta WHERE post_id = 716 AND meta_key = '_elementor_data' LIMIT 2");
$meta = $heading->num_rows === 1 ? $heading->fetch_assoc()['meta_value'] : null;
$db->rollback();
echo json_encode(array('post_id'=>716, 'title'=>$post['post_title'], 'elementor_data'=>$meta,
    'epoch'=>hash('sha256', $boot . ':' . $started)), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
