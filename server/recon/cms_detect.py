#!/usr/bin/env python3
"""Shadow C2 — CMS Detection"""

import re
from server.utils.network import make_request


class CMSDetector:
    """Detect Content Management Systems."""

    def detect(self, url: str) -> dict:
        base = url.rstrip("/")
        resp = make_request(base)
        body = resp.text
        headers = resp.headers

        result = {"cms": "", "version": "", "confidence": 0.0, "details": {}}

        detections = [
            self._check_wordpress(base, body, headers),
            self._check_joomla(base, body, headers),
            self._check_drupal(base, body, headers),
            self._check_magento(base, body),
            self._check_shopify(base, body),
        ]

        best = max(detections, key=lambda x: x.get("confidence", 0))
        if best.get("confidence", 0) > 0.2:
            return best
        return result

    def _check_wordpress(self, base: str, body: str, headers: dict) -> dict:
        score = 0.0
        details = {}

        if "/wp-content/" in body: score += 0.3
        if "/wp-includes/" in body: score += 0.2
        if 'name="generator" content="WordPress' in body:
            score += 0.4
            match = re.search(r'content="WordPress\s+([\d.]+)"', body)
            if match: details["version"] = match.group(1)

        # Check key paths
        paths = {"/wp-login.php": 0.3, "/wp-admin/": 0.2,
                 "/xmlrpc.php": 0.2, "/wp-json/": 0.2}
        for path, s in paths.items():
            r = make_request(base + path, method="HEAD")
            if r.status_code in (200, 301, 302, 403): score += s; break

        version = details.get("version", "")
        if not version:
            r = make_request(base + "/feed/")
            if r.status_code == 200:
                m = re.search(r'generator>https://wordpress.org/\?v=([\d.]+)', r.text)
                if m: version = m.group(1)

        return {"cms": "WordPress", "version": version,
                "confidence": min(score, 1.0), "details": details}

    def _check_joomla(self, base: str, body: str, headers: dict) -> dict:
        score = 0.0
        details = {}

        if 'content="Joomla' in body: score += 0.4
        if "/administrator/" in body: score += 0.2
        if "/media/system/js/" in body: score += 0.2
        if "/templates/" in body and "/joomla" in body.lower(): score += 0.2

        r = make_request(base + "/administrator/", method="HEAD")
        if r.status_code in (200, 301, 302): score += 0.2

        # Version from manifest
        r = make_request(base + "/administrator/manifests/files/joomla.xml")
        if r.status_code == 200:
            m = re.search(r'<version>([\d.]+)</version>', r.text)
            if m: details["version"] = m.group(1)

        return {"cms": "Joomla", "version": details.get("version", ""),
                "confidence": min(score, 1.0), "details": details}

    def _check_drupal(self, base: str, body: str, headers: dict) -> dict:
        score = 0.0
        details = {}

        if "Drupal" in headers.get("X-Generator", ""): score += 0.4
        if "drupal" in body.lower(): score += 0.2
        if "/sites/default/" in body: score += 0.2
        if "/core/misc/drupal.js" in body: score += 0.3

        r = make_request(base + "/core/install.php", method="HEAD")
        if r.status_code in (200, 403): score += 0.2

        r = make_request(base + "/CHANGELOG.txt")
        if r.status_code == 200:
            m = re.search(r'Drupal\s+([\d.]+)', r.text)
            if m: details["version"] = m.group(1)

        return {"cms": "Drupal", "version": details.get("version", ""),
                "confidence": min(score, 1.0), "details": details}

    def _check_magento(self, base: str, body: str) -> dict:
        score = 0.0
        if "/skin/frontend/" in body: score += 0.3
        if "Mage.Cookies" in body: score += 0.3
        if "/js/mage/" in body: score += 0.2
        r = make_request(base + "/downloader/", method="HEAD")
        if r.status_code in (200, 302): score += 0.2
        return {"cms": "Magento", "version": "", "confidence": min(score, 1.0), "details": {}}

    def _check_shopify(self, base: str, body: str) -> dict:
        score = 0.0
        if "cdn.shopify.com" in body: score += 0.4
        if "Shopify.theme" in body: score += 0.3
        if "myshopify.com" in body: score += 0.3
        return {"cms": "Shopify", "version": "", "confidence": min(score, 1.0), "details": {}}
