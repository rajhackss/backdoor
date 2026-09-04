#!/usr/bin/env python3
"""Shadow C2 — Target Fingerprinting"""

import re
import ssl
import socket
from server.utils.network import make_request, get_http_headers


class TargetFingerprint:
    """Full target fingerprinting via HTTP analysis."""

    def fingerprint(self, url: str) -> dict:
        """Complete target analysis."""
        result = {
            "url": url,
            "server_software": "",
            "powered_by": "",
            "php_version": "",
            "technologies": [],
            "cookies": [],
            "security_headers": {},
            "response_time_ms": 0,
            "http_methods": [],
            "common_files": [],
            "ssl_info": {},
            "os_guess": "",
        }

        import time
        start = time.time()
        resp = make_request(url)
        result["response_time_ms"] = round((time.time() - start) * 1000)

        headers = resp.headers
        body = resp.text

        # Server software
        result["server_software"] = headers.get("Server", "")

        # X-Powered-By
        powered = headers.get("X-Powered-By", "")
        result["powered_by"] = powered
        if "PHP" in powered:
            match = re.search(r'PHP/([\d.]+)', powered)
            if match:
                result["php_version"] = match.group(1)

        # Technologies
        result["technologies"] = self._detect_technologies(headers, body)

        # Cookies
        for cookie_header in ["Set-Cookie"]:
            val = headers.get(cookie_header, "")
            if val:
                result["cookies"].append(val)

        # Security headers
        sec_headers = ["Content-Security-Policy", "Strict-Transport-Security",
                       "X-Frame-Options", "X-Content-Type-Options",
                       "X-XSS-Protection", "Referrer-Policy",
                       "Permissions-Policy", "Cross-Origin-Opener-Policy"]
        for sh in sec_headers:
            val = headers.get(sh, "")
            if val:
                result["security_headers"][sh] = val

        # OS guess
        result["os_guess"] = self._detect_os(headers)

        # HTTP methods
        result["http_methods"] = self._check_methods(url)

        # Common files
        result["common_files"] = self._check_common_files(url)

        # SSL info
        if url.startswith("https"):
            result["ssl_info"] = self._get_ssl_info(url)

        return result

    def _detect_technologies(self, headers: dict, body: str) -> list:
        techs = []
        server = headers.get("Server", "").lower()

        if "nginx" in server: techs.append("Nginx")
        if "apache" in server: techs.append("Apache")
        if "iis" in server: techs.append("IIS")
        if "litespeed" in server: techs.append("LiteSpeed")
        if "cloudflare" in server: techs.append("Cloudflare")

        if headers.get("X-Powered-By", ""):
            powered = headers["X-Powered-By"]
            if "PHP" in powered: techs.append("PHP")
            if "ASP" in powered: techs.append("ASP.NET")
            if "Express" in powered: techs.append("Express.js")

        # Body analysis
        if "jquery" in body.lower() or "jQuery" in body: techs.append("jQuery")
        if "bootstrap" in body.lower(): techs.append("Bootstrap")
        if "react" in body.lower() or "reactDOM" in body: techs.append("React")
        if "angular" in body.lower() or "ng-app" in body: techs.append("Angular")
        if "vue" in body.lower() or "Vue.js" in body: techs.append("Vue.js")
        if "wp-content" in body: techs.append("WordPress")
        if "Joomla" in body: techs.append("Joomla")
        if "Drupal" in body: techs.append("Drupal")
        if "shopify" in body.lower(): techs.append("Shopify")

        # Cookie-based detection
        cookies = headers.get("Set-Cookie", "")
        if "PHPSESSID" in cookies: techs.append("PHP Sessions")
        if "JSESSIONID" in cookies: techs.append("Java")
        if "ASP.NET" in cookies: techs.append("ASP.NET")
        if "csrftoken" in cookies: techs.append("Django")

        return list(set(techs))

    def _detect_os(self, headers: dict) -> str:
        server = headers.get("Server", "")
        if "Win" in server or "IIS" in server: return "Windows"
        if "Ubuntu" in server: return "Ubuntu Linux"
        if "Debian" in server: return "Debian Linux"
        if "CentOS" in server or "Red Hat" in server: return "CentOS/RHEL"
        if "Unix" in server or "nginx" in server.lower(): return "Linux/Unix"
        return "Unknown"

    def _check_methods(self, url: str) -> list:
        resp = make_request(url, method="OPTIONS")
        allow = resp.headers.get("Allow", "")
        if allow:
            return [m.strip() for m in allow.split(",")]
        return ["GET", "POST"]  # Assume basic

    def _check_common_files(self, url: str) -> list:
        base = url.rstrip("/")
        found = []
        files = ["/robots.txt", "/sitemap.xml", "/.git/config", "/.env",
                 "/phpinfo.php", "/.htaccess", "/wp-config.php.bak",
                 "/web.config", "/crossdomain.xml", "/.well-known/security.txt",
                 "/server-status", "/server-info", "/.DS_Store",
                 "/backup.sql", "/dump.sql", "/debug.log"]
        for f in files:
            resp = make_request(base + f, method="HEAD")
            if resp.status_code == 200:
                found.append(f)
        return found

    def _get_ssl_info(self, url: str) -> dict:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            hostname = parsed.hostname
            port = parsed.port or 443
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert(binary_form=False)
                    if cert:
                        return {
                            "subject": str(cert.get("subject", "")),
                            "issuer": str(cert.get("issuer", "")),
                            "notBefore": cert.get("notBefore", ""),
                            "notAfter": cert.get("notAfter", ""),
                            "version": ssock.version(),
                        }
        except: pass
        return {}
