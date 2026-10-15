<?php
// Separate closed protocol. The core/heading route retains its original restrictions.
if (!defined('ABSPATH')) { exit; }

function lseo_e_plain($text) {
    if (!is_string($text) || trim($text) === '' || mb_strlen($text) > 500
        || preg_match('/[<>\x00-\x1f\[\]]|&(?:#|[A-Za-z])/u', $text)) { lseo_fail(); }
    return $text;
}

// JSON parser with duplicate-key detection and byte spans. Never reserialize a document.
function lseo_e_parse($raw) {
    if (!is_string($raw) || strlen($raw) > 500000) { lseo_fail(); }
    json_decode($raw, true, 64, JSON_THROW_ON_ERROR);
    $pos = 0; $count = 0; $spans = array(); $length = strlen($raw);
    $space = function () use (&$pos, $raw, $length) {
        while ($pos < $length && strpos(" \r\n\t", $raw[$pos]) !== false) { $pos++; }
    };
    $string = function () use (&$pos, $raw, $length) {
        $start = $pos++;
        while ($pos < $length) {
            $char = $raw[$pos++];
            if ($char === '\\') { $pos++; }
            elseif ($char === '"') { return json_decode(substr($raw, $start, $pos - $start), true, 64, JSON_THROW_ON_ERROR); }
        }
        lseo_fail();
    };
    $visit = function ($path, $depth) use (&$visit, &$pos, &$count, &$spans, $space, $string, $raw, $length) {
        if ($depth > 60 || ++$count > 20000) { lseo_fail(); }
        $space(); $start = $pos;
        if ($raw[$pos] === '{') {
            $pos++; $space(); $keys = array();
            while ($raw[$pos] !== '}') {
                $key = $string();
                if (in_array($key, $keys, true)) { lseo_fail(); }
                $keys[] = $key; $space(); $pos++; // colon (whole JSON already validated)
                $visit(array_merge($path, array($key)), $depth + 1); $space();
                if ($raw[$pos] === '}') { break; }
                $pos++; $space();
            }
            $pos++;
        } elseif ($raw[$pos] === '[') {
            $pos++; $space(); $index = 0;
            while ($raw[$pos] !== ']') {
                $visit(array_merge($path, array($index++)), $depth + 1); $space();
                if ($raw[$pos] === ']') { break; }
                $pos++; $space();
            }
            $pos++;
        } elseif ($raw[$pos] === '"') { $string(); }
        else { while ($pos < $length && strpos(",]} \r\n\t", $raw[$pos]) === false) { $pos++; } }
        $spans[json_encode($path)] = array($start, $pos);
    };
    $visit(array(), 0);
    $data = json_decode($raw, false, 64, JSON_THROW_ON_ERROR);
    if (!is_array($data)) { lseo_fail(); }
    return array($data, $spans);
}

function lseo_e_headings($raw) {
    list($data, $spans) = lseo_e_parse($raw);
    $seen = array(); $headings = array();
    $walk = function ($nodes, $path, $ancestors) use (&$walk, &$seen, &$headings) {
        if (!is_array($nodes)) { lseo_fail(); }
        foreach ($nodes as $index => $node) {
            if (!is_object($node) || array_diff(array_keys(get_object_vars($node)), array('id','elType','settings','elements','widgetType','isInner'))
                || !isset($node->id, $node->elType, $node->settings, $node->elements)
                || !is_string($node->id) || !preg_match('/^[A-Za-z0-9_-]{1,80}$/D', $node->id)
                || in_array($node->id, $seen, true) || !is_array($node->elements)) { lseo_fail(); }
            $seen[] = $node->id;
            $settings = $node->settings;
            if ($settings === array()) { $settings = new stdClass(); }
            if (!is_object($settings)) { lseo_fail(); }
            $here = array_merge($path, array($index));
            if ($node->elType === 'widget') {
                if (($node->widgetType ?? '') !== 'heading' || $node->elements
                    || array_diff(array_keys(get_object_vars($settings)), array('title','header_size','size'))
                    || !in_array($settings->header_size ?? '', array('h1','h2','h3','h4','h5','h6'), true)
                    || !in_array($settings->size ?? 'default', array('default','small','medium','large','xl','xxl'), true)) { lseo_fail(); }
                $headings[] = array('element_id' => $node->id, 'path' => array_merge($here, array('settings','title')),
                    'ancestor_ids' => $ancestors, 'tag' => $settings->header_size, 'text' => lseo_e_plain($settings->title ?? null));
            } elseif (!in_array($node->elType, array('container','section','column'), true)
                || count(get_object_vars($settings)) || isset($node->widgetType)) { lseo_fail(); }
            $walk($node->elements, array_merge($here, array('elements')), array_merge($ancestors, array($node->id)));
        }
    };
    $walk($data, array(), array());
    if (!$headings) { lseo_fail(); }
    return array($headings, $spans);
}

function lseo_e_tree_hash($root, $php_only = false) {
    if (!is_dir($root) || is_link($root)) { lseo_fail(); }
    $files = array(); $size = 0;
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS)) as $file) {
        if ($file->isLink()) { lseo_fail(); }
        if (!$file->isFile() || ($php_only && $file->getExtension() !== 'php')) { continue; }
        $size += $file->getSize();
        if (count($files) > 20000 || $size > 200000000) { lseo_fail(); }
        $relative = str_replace(DIRECTORY_SEPARATOR, '/', substr($file->getPathname(), strlen($root) + 1));
        $files[$relative] = hash_file('sha256', $file->getPathname());
    }
    ksort($files, SORT_STRING); $source = '';
    foreach ($files as $path => $hash) { $source .= $path . "\0" . $hash . "\n"; }
    return hash('sha256', $source);
}

function lseo_e_root_hash() {
    $files = array(); $source = '';
    foreach (glob(ABSPATH . '*.php') as $file) {
        if (basename($file) === 'wp-config.php') { continue; }
        if (is_link($file)) { lseo_fail(); }
        $files[basename($file)] = hash_file('sha256', $file);
    }
    ksort($files, SORT_STRING);
    foreach ($files as $name => $hash) { $source .= $name . "\0" . $hash . "\n"; }
    return hash('sha256', $source);
}

function lseo_e_inventory($id) {
    global $wpdb, $wp_version;
    require_once ABSPATH . 'wp-admin/includes/plugin.php';
    $manifest_raw = file_get_contents(__DIR__ . '/elementor-contract.json');
    $manifest = json_decode($manifest_raw, true, 32, JSON_THROW_ON_ERROR);
    if (!defined('LSEO_ELEMENTOR_CONTRACT') || LSEO_ELEMENTOR_CONTRACT !== $manifest['contract']
        || !defined('DISABLE_WP_CRON') || DISABLE_WP_CRON !== true
        || (defined('WP_CACHE') && WP_CACHE) || wp_using_ext_object_cache()
        || ini_get('auto_prepend_file') || ini_get('auto_append_file')
        || $wp_version !== $manifest['wordpress'] || (PHP_MAJOR_VERSION . '.' . PHP_MINOR_VERSION) !== $manifest['php']
        || PHP_VERSION !== $manifest['php_runtime'] || $wpdb->get_var('SELECT VERSION()') !== $manifest['database_runtime']
        || !defined('ELEMENTOR_VERSION') || ELEMENTOR_VERSION !== $manifest['elementor']
        || get_mu_plugins() || get_dropins() || is_multisite()
        || get_option('stylesheet') !== $manifest['theme'] || get_option('template') !== $manifest['theme']) { lseo_fail(); }
    $plugins = get_option('active_plugins'); sort($plugins);
    if ($plugins !== array('elementor/elementor.php','local-seo-publisher/local-seo-publisher.php')) { lseo_fail(); }
    $options = $wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options} WHERE option_name NOT LIKE '_transient_%' AND option_name NOT LIKE '_site_transient_%' ORDER BY option_name", ARRAY_A);
    $cached_options = wp_load_alloptions();
    $notoptions = wp_cache_get('notoptions', 'options');
    foreach ($options as $option) {
        $name = $option['option_name'];
        // Compare stored cache bytes before option filters (e.g. ping_sites on a
        // noindex fixture) or unserialized object identity can change the value.
        $cached = array_key_exists($name, $cached_options) ? $cached_options[$name] : wp_cache_get($name, 'options');
        if (($cached !== false && $cached !== $option['option_value']) || isset($notoptions[$name])) { lseo_fail('Configuration changed during request'); }
    }
    if (get_option('elementor_google_font') !== '0' || \Elementor\Fonts::is_google_fonts_enabled()
        || get_option('elementor_allow_tracking') !== 'no' || get_option('elementor_css_print_method') !== 'internal'
        || get_option('elementor_experiment-e_element_cache') !== 'inactive'
        || \Elementor\Plugin::$instance->experiments->is_feature_active('e_element_cache')) { lseo_fail(); }
    foreach (array($wpdb->posts, $wpdb->postmeta, $wpdb->options, $wpdb->prefix . 'lseo_operations') as $table) {
        if ($wpdb->get_var($wpdb->prepare('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', $table)) !== 'InnoDB') { lseo_fail(); }
    }
    $hashes = array('elementor_files' => lseo_e_tree_hash(WP_PLUGIN_DIR . '/elementor'),
        'theme_files' => lseo_e_tree_hash(get_template_directory()),
        'core_includes_php' => lseo_e_tree_hash(ABSPATH . WPINC, true),
        'core_admin_php' => lseo_e_tree_hash(ABSPATH . 'wp-admin', true), 'core_root_php' => lseo_e_root_hash());
    foreach ($hashes as $key => $value) { if (($manifest[$key] ?? '') !== $value) { lseo_fail('Runtime file hashes differ from certificate'); } }
    // Reject shared templates, global widgets, shortcodes and embedding/query routes.
    // A default Elementor kit contains only style configuration and is fingerprinted.
    $kit = (int)get_option('elementor_active_kit');
    $others = $wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->posts} WHERE ID<>%d ORDER BY ID", $id), ARRAY_A);
    foreach ($others as $row) {
        if ($row['post_type'] === 'elementor_library' && (int)$row['ID'] !== $kit
            || in_array($row['post_type'], array('wp_template','wp_template_part','wp_block'), true)
            || preg_match('/\[elementor|<!-- wp:(query|post-content|block|shortcode)/', $row['post_content'])) { lseo_fail(); }
    }
    $other_meta = $wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->postmeta} WHERE post_id<>%d ORDER BY meta_id", $id), ARRAY_A);
    foreach ($other_meta as $meta) {
        if ($meta['meta_key'] === '_elementor_data') {
            if ((int)$meta['post_id'] === $kit) {
                if (!in_array($meta['meta_value'], array('', '[]'), true)) { lseo_fail(); }
            } else { lseo_e_headings($meta['meta_value']); }
        }
    }
    return array_merge($hashes, array('wordpress' => $wp_version, 'php' => PHP_VERSION,
        'database' => $wpdb->get_var('SELECT VERSION()'), 'elementor' => ELEMENTOR_VERSION,
        'theme' => $manifest['theme'], 'plugins' => $plugins, 'kit_id' => $kit,
        'options_hash' => hash('sha256', wp_json_encode($options)),
        'dependencies_hash' => hash('sha256', wp_json_encode(array($others,$other_meta))),
        'adapter_hash' => hash('sha256', file_get_contents(__FILE__) . file_get_contents(__DIR__ . '/local-seo-publisher.php')),
        'configuration_hash' => hash('sha256', file_get_contents(ABSPATH . 'wp-config.php') . wp_json_encode(array(LSEO_INSTANCE,LSEO_ENVIRONMENT,LSEO_USER_ID,LSEO_PAGE_IDS))),
        'contract_hash' => hash('sha256', trim($manifest_raw))));
}

function lseo_e_mirror($content, $headings, $element_id = null, $proposed = null) {
    preg_match_all('/<(h[1-6])>([^<>]*)<\/\1>/', $content, $matches, PREG_SET_ORDER | PREG_OFFSET_CAPTURE);
    if (count($matches) !== count($headings) || trim(preg_replace('/<h[1-6]>[^<>]*<\/h[1-6]>/', '', $content)) !== '') { lseo_fail(); }
    foreach ($matches as $index => $match) {
        $h = $headings[$index];
        if ($match[1][0] !== $h['tag'] || $match[2][0] !== $h['text']) { lseo_fail('Plain content mirror differs'); }
    }
    foreach ($matches as $index => $match) {
        if ($headings[$index]['element_id'] === $element_id) {
            return substr_replace($content, lseo_e_plain($proposed), $match[2][1], strlen($match[2][0]));
        }
    }
    if ($element_id !== null) { lseo_fail(); }
    return $content;
}

function lseo_e_state($id, $locked = false) {
    global $wpdb;
    $inventory = lseo_e_inventory($id);
    $row = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->posts} WHERE ID=%d", $id), ARRAY_A);
    if (!$row || $row['post_type'] !== 'page' || $row['post_status'] !== 'publish'
        || $row['post_password'] !== '' || trim($row['post_excerpt']) === '') { lseo_fail(); }
    $meta = $wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->postmeta} WHERE post_id=%d ORDER BY meta_id", $id), ARRAY_A);
    $values = array(); $data_row = null; $preserved_meta = array();
    foreach ($meta as $item) {
        if (array_key_exists($item['meta_key'], $values)) { lseo_fail('Duplicate metadata identity'); }
        $values[$item['meta_key']] = $item['meta_value'];
        if ($item['meta_key'] === '_elementor_data') { $data_row = $item; $item['meta_value'] = '__EXACT_ELEMENTOR_DATA__'; }
        $preserved_meta[] = $item;
        if (preg_match('/_elementor_(element_cache|controls_usage)|yoast|rank_math|aioseo|_et_|_fl_|_bricks/i', $item['meta_key'])) { lseo_fail(); }
    }
    if (!$data_row || ($values['_elementor_edit_mode'] ?? '') !== 'builder'
        || ($values['_wp_page_template'] ?? '') !== 'elementor_canvas'
        || ($values['_elementor_version'] ?? '') !== ELEMENTOR_VERSION
        || !in_array($values['_elementor_page_settings'] ?? '', array('', 'a:0:{}'), true)) { lseo_fail(); }
    list($headings, $spans) = lseo_e_headings($data_row['meta_value']);
    lseo_e_mirror($row['post_content'], $headings);
    // No CSS regeneration: title is not a CSS control on the pinned static widget.
    // Require a warmed existing cache record so public verification creates no assets.
    $css = maybe_unserialize($values['_elementor_css'] ?? '');
    if (!is_array($css) || empty($css['time']) || !isset($css['status'])) { lseo_fail('Warm generated CSS before independent discovery'); }
    $uploads = wp_get_upload_dir();
    $asset_root = $uploads['basedir'] . '/elementor/css';
    $assets = is_dir($asset_root) ? lseo_e_tree_hash($asset_root) : hash('sha256', '');
    $fixed = $row; unset($fixed['post_content'], $fixed['post_modified'], $fixed['post_modified_gmt']);
    $preserved = hash('sha256', wp_json_encode(array($fixed,$preserved_meta,$inventory,$assets)));
    $token = hash('sha256', wp_json_encode(array($row,$meta,$inventory,$assets,home_url('/'),LSEO_INSTANCE,LSEO_ENVIRONMENT)));
    return array('protocol' => 'local-seo-elementor/1', 'contract' => LSEO_ELEMENTOR_CONTRACT,
        'contract_hash' => $inventory['contract_hash'], 'instance' => LSEO_INSTANCE, 'environment' => LSEO_ENVIRONMENT,
        'home' => home_url('/'), 'id' => $id, 'url' => get_permalink($id), 'type' => 'page', 'status' => 'publish',
        'supported' => true, 'template' => 'elementor_canvas', 'metadata_row_id' => (int)$data_row['meta_id'],
        'elementor_data' => $data_row['meta_value'], 'content' => $row['post_content'], 'excerpt' => $row['post_excerpt'],
        'headings' => $headings, 'inventory' => $inventory, 'assets_hash' => $assets, 'preserved' => $preserved, 'token' => $token);
}

function lseo_e_write($request) {
    global $wpdb;
    $id = (int)$request['id']; $body = $request->get_json_params();
    $keys = array('request_id','instance','environment','url','token','current','proposed','adapter','contract','metadata_row_id','element_id','path','replacement_token');
    if (!is_array($body) || count($body) !== count($keys) || array_diff($keys, array_keys($body))
        || !is_string($body['request_id']) || !preg_match('/^[a-f0-9]{32}$/D', $body['request_id'])
        || $body['adapter'] !== 'elementor-heading/1' || $body['contract'] !== 'elementor-3.31.3-canvas-heading/1'
        || $body['environment'] !== LSEO_ENVIRONMENT || !is_int($body['metadata_row_id'])
        || !is_string($body['element_id']) || !is_array($body['path']) || !is_string($body['replacement_token'])
        || strlen($body['replacement_token']) > 6002 || $body['current'] === $body['proposed']) { lseo_fail(); }
    lseo_e_plain($body['current']); lseo_e_plain($body['proposed']);
    if (json_decode($body['replacement_token'], true, 4, JSON_THROW_ON_ERROR) !== $body['proposed']
        || $body['replacement_token'][0] !== '"' || substr($body['replacement_token'], -1) !== '"') { lseo_fail(); }
    if ($wpdb->query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ') === false || $wpdb->query('START TRANSACTION') === false) { lseo_fail(); }
    try {
        foreach (array($wpdb->options,$wpdb->posts,$wpdb->postmeta) as $table) {
            if ($wpdb->query("SELECT * FROM {$table} ORDER BY 1 FOR UPDATE") === false) { lseo_fail(); }
        }
        // Committed receipts remain readable/duplicate-safe even after compatibility changes.
        $saved = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}lseo_operations WHERE request_id=%s FOR UPDATE", $body['request_id']), ARRAY_A);
        if ($saved) {
            $result = json_decode($saved['payload'], true);
            if ((int)$saved['page_id'] !== $id || $result['request'] != $body || $body['instance'] !== LSEO_INSTANCE
                || strpos($body['url'], home_url('/')) !== 0) { lseo_fail(); }
            if ($wpdb->query('COMMIT') === false) { lseo_fail(); }
            return $result;
        }
        $before = lseo_e_state($id, true);
        if ($before['instance'] !== $body['instance'] || $before['url'] !== $body['url'] || !hash_equals($before['token'], $body['token'])
            || $before['metadata_row_id'] !== $body['metadata_row_id']) { lseo_fail(); }
        list($headings, $spans) = lseo_e_headings($before['elementor_data']);
        $found = array_values(array_filter($headings, function ($h) use ($body) {
            return $h['element_id'] === $body['element_id'] && $h['path'] === $body['path'] && $h['text'] === $body['current'];
        }));
        if (count($found) !== 1) { lseo_fail(); }
        list($start,$end) = $spans[json_encode($body['path'])];
        $raw = substr_replace($before['elementor_data'], $body['replacement_token'], $start, $end - $start);
        $content = lseo_e_mirror($before['content'], $headings, $body['element_id'], $body['proposed']);
        if ($wpdb->query($wpdb->prepare("UPDATE {$wpdb->postmeta} SET meta_value=%s WHERE meta_id=%d AND post_id=%d AND meta_key='_elementor_data' AND BINARY meta_value=BINARY %s",
            $raw, $body['metadata_row_id'], $id, $before['elementor_data'])) !== 1) { lseo_fail(); }
        if ($wpdb->query($wpdb->prepare("UPDATE {$wpdb->posts} SET post_content=%s,post_modified=%s,post_modified_gmt=%s WHERE ID=%d AND BINARY post_content=BINARY %s",
            $content,current_time('mysql'),current_time('mysql',true),$id,$before['content'])) !== 1) { lseo_fail(); }
        $after = lseo_e_state($id, true);
        if ($after['preserved'] !== $before['preserved']) { lseo_fail(); }
        $result = array('request_id' => $body['request_id'], 'request' => $body, 'status' => 'applied',
            'before_token' => $before['token'], 'after_token' => $after['token'], 'before_content' => $before['content'],
            'after_content' => $content, 'before_data' => $before['elementor_data'], 'after_data' => $raw, 'written_utc' => gmdate('c'));
        if (!$wpdb->insert($wpdb->prefix . 'lseo_operations', array('request_id'=>$body['request_id'],'page_id'=>$id,'payload'=>wp_json_encode($result)))
            || $wpdb->query('COMMIT') === false) { lseo_fail(); }
        // Persistent caches are prohibited. Avoid clean_post_cache's global/hook effects.
        wp_cache_delete($id, 'posts'); wp_cache_delete($id, 'post_meta');
        return $result;
    } catch (Throwable $e) { $wpdb->query('ROLLBACK'); throw $e; }
}

function lseo_e_dispatch($request) {
    global $wpdb;
    try {
        if ($request->get_method() === 'POST') { $value = lseo_e_write($request); }
        elseif ($request->get_param('request_id')) {
            $raw = $wpdb->get_var($wpdb->prepare("SELECT payload FROM {$wpdb->prefix}lseo_operations WHERE request_id=%s AND page_id=%d", $request['request_id'], (int)$request['id']));
            $value = $raw ? json_decode($raw, true) : array('status'=>'unknown');
            if ($raw && (($value['request']['adapter'] ?? '') !== 'elementor-heading/1'
                || $value['request']['instance'] !== LSEO_INSTANCE || $value['request']['environment'] !== LSEO_ENVIRONMENT
                || strpos($value['request']['url'], home_url('/')) !== 0)) { lseo_fail(); }
        } else { $value = lseo_e_state((int)$request['id']); }
        $response = new WP_REST_Response($value, 200); $response->header('Cache-Control','no-store'); return $response;
    } catch (Throwable $e) {
        return new WP_Error('lseo_elementor_rejected', 'Elementor effect contract, identity or concurrency check failed. Inspect current installation evidence; no generic replacement is supported.', array('status'=>409));
    }
}

add_action('rest_api_init', function () {
    register_rest_route('local-seo-elementor/v1', '/pages/(?P<id>\d+)', array('methods'=>array('GET','POST'), 'permission_callback'=>'lseo_permission','callback'=>'lseo_e_dispatch'));
    register_rest_route('local-seo-elementor/v1', '/pages/(?P<id>\d+)/operations/(?P<request_id>[a-f0-9]{32})', array('methods'=>'GET','permission_callback'=>'lseo_permission','callback'=>'lseo_e_dispatch'));
});
