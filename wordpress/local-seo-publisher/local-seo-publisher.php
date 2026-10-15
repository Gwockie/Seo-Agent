<?php
/**
 * Plugin Name: Local SEO Exact Heading Publisher
 * Description: Opt-in, conditional page-local heading writes with a durable request journal.
 * Version: 0.2.0
 */
if (!defined('ABSPATH')) { exit; }

require_once __DIR__ . '/elementor-publisher.php';

function lseo_fail($message = 'Unsupported configuration or conflicting CMS values', $status = 409) {
    throw new RuntimeException($message, $status);
}

register_activation_hook(__FILE__, function () {
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta("CREATE TABLE {$wpdb->prefix}lseo_operations (
        request_id varchar(32) NOT NULL,
        page_id bigint(20) unsigned NOT NULL,
        payload longtext NOT NULL,
        PRIMARY KEY  (request_id)
    ) ENGINE=InnoDB " . $wpdb->get_charset_collate() . ';');
    add_role('lseo_publisher', 'Exact heading publisher', array('read' => true, 'lseo_publish_heading' => true));
});

function lseo_permission($request) {
    // No cookie/editor or ambient admin access. A separately configured application password
    // belonging to a dedicated minimal-capability account is required on every request.
    return defined('LSEO_INSTANCE') && defined('LSEO_USER_ID') && defined('LSEO_PAGE_IDS')
        && defined('LSEO_ENVIRONMENT') && in_array(LSEO_ENVIRONMENT, array('local', 'staging', 'production'), true)
        && get_current_user_id() === LSEO_USER_ID && current_user_can('lseo_publish_heading')
        && !empty($GLOBALS['wp_rest_application_password_uuid'])
        && in_array((int)$request['id'], LSEO_PAGE_IDS, true);
}

function lseo_inventory() {
    global $wpdb, $wp_version;
    require_once ABSPATH . 'wp-admin/includes/plugin.php';
    // Read authoritative options, not the request's pre-transaction alloptions cache.
    $option_names = array('active_plugins','stylesheet','template','home','siteurl','permalink_structure',
        'show_on_front','page_on_front','page_for_posts','blog_public','timezone_string','gmt_offset','blogname','blogdescription');
    $options = array();
    foreach ($option_names as $name) {
        $raw = $wpdb->get_row($wpdb->prepare("SELECT option_value FROM {$wpdb->options} WHERE option_name=%s", $name), ARRAY_A);
        $options[$name] = $raw === null ? false : maybe_unserialize($raw['option_value']);
        if (get_option($name) !== $options[$name]) { lseo_fail('Option changed during this request'); }
    }
    $plugins = $options['active_plugins'];
    sort($plugins);
    // First supported combination is deliberately small; builders/SEO plugins are detected,
    // reported by name and rejected, never treated as WordPress's post_title/content fields.
    if ($plugins !== array(plugin_basename(__FILE__)) || get_mu_plugins() || get_dropins()
        || is_multisite() || get_option('stylesheet') !== 'twentytwentyfive'
        || get_option('template') !== 'twentytwentyfive') { lseo_fail(); }
    foreach (array($wpdb->posts, $wpdb->postmeta, $wpdb->options, $wpdb->prefix . 'lseo_operations') as $table) {
        $engine = $wpdb->get_var($wpdb->prepare('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', $table));
        if ($engine !== 'InnoDB') { lseo_fail('Transactional InnoDB storage required'); }
    }
    $files = array();
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator(get_template_directory(), FilesystemIterator::SKIP_DOTS));
    foreach ($iterator as $file) {
        if ($file->isLink()) { lseo_fail(); }
        if ($file->isFile()) { $files[$file->getPathname()] = hash_file('sha256', $file->getPathname()); }
    }
    ksort($files);
    // Template/style customizations and globals are included in every concurrency token.
    $templates = $wpdb->get_results("SELECT * FROM {$wpdb->posts} WHERE post_type IN ('wp_template','wp_template_part','wp_global_styles','wp_navigation') ORDER BY ID", ARRAY_A);
    foreach ($templates as $template) {
        if (!in_array($template['post_type'], array('wp_global_styles', 'wp_navigation'), true)) { lseo_fail('Customized/shared templates are unsupported'); }
        if ($template['post_type'] === 'wp_navigation') {
            $pending = parse_blocks($template['post_content']);
            while ($pending) {
                $nav = array_pop($pending);
                if ($nav['blockName'] === null && trim($nav['innerHTML']) === '') { continue; }
                if (!in_array($nav['blockName'], array('core/page-list','core/navigation-link','core/navigation-submenu'), true)
                    || isset($nav['attrs']['metadata'])) { lseo_fail('Navigation with shared content is unsupported'); }
                $pending = array_merge($pending, $nav['innerBlocks']);
            }
        }
    }
    // Reusable blocks/query loops elsewhere can expose this page's content on a
    // second URL. Fail closed rather than infer shared scope from the visible page.
    $shared = $wpdb->get_var("SELECT ID FROM {$wpdb->posts} WHERE post_status='publish' AND (post_content LIKE '%<!-- wp:query%' OR post_content LIKE '%<!-- wp:post-content%' OR post_content LIKE '%<!-- wp:block %' OR post_content LIKE '%<!-- wp:shortcode%') LIMIT 1");
    if ($shared) { lseo_fail('Potential shared content rendering requires a different adapter'); }
    return array('wordpress' => $wp_version, 'editor' => 'core blocks', 'seo_plugin' => 'none',
        'theme' => 'twentytwentyfive', 'plugins' => $plugins, 'theme_hash' => hash('sha256', wp_json_encode($files)),
        'options_hash' => hash('sha256', wp_json_encode($options)),
        'templates_hash' => hash('sha256', wp_json_encode($templates)), 'adapter_hash' => hash_file('sha256', __FILE__));
}

function lseo_state($id, $locked = false) {
    global $wpdb;
    $inventory = lseo_inventory();
    $row = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->posts} WHERE ID=%d" . ($locked ? ' FOR UPDATE' : ''), $id), ARRAY_A);
    if (!$row || $row['post_type'] !== 'page' || $row['post_status'] !== 'publish' || $row['post_password'] !== ''
        || trim($row['post_excerpt']) === '') { lseo_fail('Published page with a fixed explicit excerpt required'); }
    $meta = $wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->postmeta} WHERE post_id=%d ORDER BY meta_id" . ($locked ? ' FOR UPDATE' : ''), $id), ARRAY_A);
    foreach ($meta as $item) {
        if (preg_match('/elementor|_et_|_fl_|_bricks|yoast|rank_math|aioseo/i', $item['meta_key'])) { lseo_fail(); }
        if ($item['meta_key'] === '_wp_page_template' && !in_array($item['meta_value'], array('', 'default'), true)) { lseo_fail(); }
    }
    $headings = array();
    $blocks = parse_blocks($row['post_content']);
    foreach ($blocks as $index => $block) {
        if ($block['blockName'] === null && trim($block['innerHTML']) === '') { continue; }
        if (!in_array($block['blockName'], array('core/heading', 'core/paragraph'), true) || $block['innerBlocks']
            || isset($block['attrs']['metadata']) || strpos($block['innerHTML'], '[') !== false) { lseo_fail(); }
        if ($block['blockName'] !== 'core/heading') { continue; }
        $anchor = $block['attrs']['anchor'] ?? '';
        if (!preg_match('/^[A-Za-z][A-Za-z0-9_-]{0,79}$/D', $anchor)) { continue; }
        $pattern = '/^(\s*<h([1-6])\b[^>]*\bid="' . preg_quote($anchor, '/') . '"[^>]*>)([^<>]*)(<\/h\2>\s*)$/sD';
        if (!preg_match($pattern, $block['innerHTML'], $match)) { lseo_fail('Heading must be plain text with one explicit anchor'); }
        $headings[] = array('anchor' => $anchor, 'block_index' => $index,
            'text' => html_entity_decode($match[3], ENT_QUOTES | ENT_HTML5, 'UTF-8'));
    }
    if (count(array_unique(array_column($headings, 'anchor'))) !== count($headings)) { lseo_fail(); }
    // No remote state secrets: return content + hashes, never metadata values/options.
    $preserved = $row;
    unset($preserved['post_content'], $preserved['post_modified'], $preserved['post_modified_gmt']);
    $preserved = hash('sha256', wp_json_encode(array($preserved, $meta, $inventory)));
    $token = hash('sha256', wp_json_encode(array($row, $meta, $inventory, home_url('/'), LSEO_INSTANCE, LSEO_ENVIRONMENT)));
    return array('protocol' => 'local-seo-heading/1', 'instance' => LSEO_INSTANCE, 'home' => home_url('/'),
        'environment' => LSEO_ENVIRONMENT, 'id' => $id, 'url' => get_permalink($id), 'type' => 'page', 'status' => 'publish',
        'supported' => true, 'inventory' => $inventory, 'headings' => $headings, 'content' => $row['post_content'],
        'token' => $token, 'preserved' => $preserved);
}

function lseo_write($request) {
    global $wpdb;
    $id = (int)$request['id'];
    $body = $request->get_json_params();
    $keys = array('request_id','instance','url','token','anchor','block_index','current','proposed');
    if (!is_array($body) || count(array_diff($keys, array_keys($body))) || count($body) !== count($keys)
        || !is_string($body['request_id']) || !preg_match('/^[a-f0-9]{32}$/D', $body['request_id'])
        || !is_int($body['block_index']) || !is_string($body['current']) || !is_string($body['proposed'])
        || $body['current'] === $body['proposed'] || trim($body['proposed']) === ''
        || mb_strlen($body['proposed']) > 500 || preg_match('/[<>\r\n\[\]]/', $body['proposed'])) { lseo_fail('Unsupported write request', 400); }
    // Repeatable-read next-key locks include insert gaps. This deliberately short,
    // conservative transaction serializes inventory changes as well as page edits.
    // Acquire locks BEFORE any consistent read can establish a stale snapshot.
    if ($wpdb->query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ') === false
        || $wpdb->query('START TRANSACTION') === false) { lseo_fail(); }
    try {
        foreach (array($wpdb->options, $wpdb->posts) as $table) {
            if ($wpdb->query("SELECT * FROM {$table} ORDER BY 1 FOR UPDATE") === false) { lseo_fail(); }
        }
        $before = lseo_state($id, true); // Row lock also serializes ordinary human WP updates.
        $saved = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}lseo_operations WHERE request_id=%s FOR UPDATE", $body['request_id']), ARRAY_A);
        if ($saved) {
            $result = json_decode($saved['payload'], true);
            if ((int)$saved['page_id'] !== $id || $result['request'] != $body) { lseo_fail('Request identity reused with different scope'); }
            $wpdb->query('COMMIT');
            clean_post_cache($id);
            return $result;
        }
        if ($before['instance'] !== $body['instance'] || $before['url'] !== $body['url'] || !hash_equals($before['token'], $body['token'])) { lseo_fail(); }
        $matches = array_values(array_filter($before['headings'], function ($h) use ($body) {
            return $h['anchor'] === $body['anchor'] && $h['block_index'] === $body['block_index'] && $h['text'] === $body['current'];
        }));
        if (count($matches) !== 1) { lseo_fail(); }
        $block = parse_blocks($before['content'])[$body['block_index']];
        $html = $block['innerHTML'];
        $pattern = '/^(\s*<h([1-6])\b[^>]*\bid="' . preg_quote($body['anchor'], '/') . '"[^>]*>)([^<>]*)(<\/h\2>\s*)$/sD';
        if (!preg_match($pattern, $html, $match) || substr_count($before['content'], $html) !== 1) { lseo_fail(); }
        // Proposed values are literal plain text, including entity-looking text.
        // esc_html() preserves existing entities and would silently decode them.
        $replacement = $match[1] . htmlspecialchars($body['proposed'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8', true) . $match[4];
        // Preserve every byte outside this heading. No block reserialization, wp_update_post
        // hooks, autosaves, post revisions, metadata writes, or generic field updates.
        $after_content = str_replace($html, $replacement, $before['content']);
        $count = $wpdb->query($wpdb->prepare("UPDATE {$wpdb->posts} SET post_content=%s,post_modified=%s,post_modified_gmt=%s WHERE ID=%d AND BINARY post_content=BINARY %s",
            $after_content, current_time('mysql'), current_time('mysql', true), $id, $before['content']));
        if ($count !== 1) { lseo_fail(); }
        $after = lseo_state($id, true);
        $result = array('request_id' => $body['request_id'], 'request' => $body, 'status' => 'applied',
            'before_token' => $before['token'], 'after_token' => $after['token'],
            'before_content' => $before['content'], 'after_content' => $after_content, 'written_utc' => gmdate('c'));
        if (!$wpdb->insert($wpdb->prefix . 'lseo_operations', array('request_id' => $body['request_id'], 'page_id' => $id, 'payload' => wp_json_encode($result)))) { lseo_fail(); }
        if ($wpdb->query('COMMIT') === false) { lseo_fail(); }
        clean_post_cache($id);
        return $result;
    } catch (Throwable $error) {
        $wpdb->query('ROLLBACK');
        throw $error;
    }
}

function lseo_dispatch($request) {
    global $wpdb;
    try {
        if ($request->get_method() === 'POST') { $result = lseo_write($request); }
        elseif ($request->get_param('request_id')) {
            $row = $wpdb->get_row($wpdb->prepare("SELECT payload FROM {$wpdb->prefix}lseo_operations WHERE request_id=%s AND page_id=%d", $request['request_id'], (int)$request['id']), ARRAY_A);
            $result = $row ? json_decode($row['payload'], true) : array('status' => 'unknown');
            // Keep committed receipts readable after a subsequent incompatible
            // editor/plugin change; verification may fail, but a write is still
            // known to have succeeded. A copied journal is not another site's proof.
            if ($row && ($result['request']['instance'] !== LSEO_INSTANCE
                || strpos($result['request']['url'], home_url('/')) !== 0)) { lseo_fail(); }
        } else { $result = lseo_state((int)$request['id']); }
        $response = new WP_REST_Response($result, 200);
        $response->header('Cache-Control', 'no-store');
        return $response;
    } catch (Throwable $error) {
        return new WP_Error('lseo_rejected', 'Unsupported configuration, request or concurrent CMS change; inspect safely before another attempt.', array('status' => 409));
    }
}

add_action('rest_api_init', function () {
    register_rest_route('local-seo/v1', '/pages/(?P<id>\d+)', array(
        'methods' => array('GET', 'POST'), 'permission_callback' => 'lseo_permission', 'callback' => 'lseo_dispatch'));
    register_rest_route('local-seo/v1', '/pages/(?P<id>\d+)/operations/(?P<request_id>[a-f0-9]{32})', array(
        'methods' => 'GET', 'permission_callback' => 'lseo_permission', 'callback' => 'lseo_dispatch'));
});
