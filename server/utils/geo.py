#!/usr/bin/env python3
"""
Shadow C2 — GeoIP Lookup
Uses ip-api.com (free, no key needed). Caching with 1-hour TTL.
"""

import json
import time
import urllib.request
import urllib.error
import ssl
import threading
from typing import Optional

from server.config import GEOIP_API_URL


class GeoIPCache:
    """Thread-safe GeoIP cache with TTL."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._cache = {}  # {ip: (timestamp, data)}
        self._lock = threading.Lock()

    def get(self, ip: str) -> Optional[dict]:
        with self._lock:
            if ip in self._cache:
                ts, data = self._cache[ip]
                if time.time() - ts < self.ttl:
                    return data
                del self._cache[ip]
        return None

    def set(self, ip: str, data: dict):
        with self._lock:
            self._cache[ip] = (time.time(), data)

    def clear_expired(self):
        now = time.time()
        with self._lock:
            expired = [k for k, (ts, _) in self._cache.items() if now - ts >= self.ttl]
            for k in expired:
                del self._cache[k]


_cache = GeoIPCache()


def geolocate_ip(ip: str) -> dict:
    """
    Geolocate an IP address.
    Returns dict with: latitude, longitude, country, city, isp, org.
    Falls back to empty values on failure.
    """
    # Skip private/local IPs
    if ip.startswith(("127.", "10.", "192.168.", "172.16.", "172.17.",
                      "172.18.", "172.19.", "172.20.", "172.21.",
                      "172.22.", "172.23.", "172.24.", "172.25.",
                      "172.26.", "172.27.", "172.28.", "172.29.",
                      "172.30.", "172.31.", "0.", "::1", "fe80:")):
        return _empty_geo()

    # Check cache
    cached = _cache.get(ip)
    if cached is not None:
        return cached

    # Query ip-api.com
    url = GEOIP_API_URL.format(ip=ip)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Shadow-C2-GeoIP/1.0")
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read())

        if data.get("status") == "success":
            result = {
                "latitude": data.get("lat", 0.0),
                "longitude": data.get("lon", 0.0),
                "country": data.get("country", ""),
                "country_code": data.get("countryCode", ""),
                "city": data.get("city", ""),
                "region": data.get("regionName", ""),
                "isp": data.get("isp", ""),
                "org": data.get("org", ""),
                "as": data.get("as", ""),
                "timezone": data.get("timezone", ""),
            }
            _cache.set(ip, result)
            return result
    except Exception:
        pass

    return _empty_geo()


def _empty_geo() -> dict:
    return {
        "latitude": 0.0,
        "longitude": 0.0,
        "country": "",
        "country_code": "",
        "city": "",
        "region": "",
        "isp": "",
        "org": "",
        "as": "",
        "timezone": "",
    }


def batch_geolocate(ips: list) -> dict:
    """
    Geolocate multiple IPs. Returns {ip: geo_dict}.
    ip-api.com supports batch queries (POST to /batch).
    """
    results = {}
    uncached = []

    for ip in ips:
        cached = _cache.get(ip)
        if cached:
            results[ip] = cached
        else:
            uncached.append(ip)

    if not uncached:
        return results

    # Batch query (ip-api.com allows POST to /batch, max 100)
    for chunk in [uncached[i:i + 100] for i in range(0, len(uncached), 100)]:
        try:
            payload = json.dumps([{"query": ip} for ip in chunk]).encode()
            req = urllib.request.Request(
                "http://ip-api.com/batch",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                batch_data = json.loads(resp.read())

            for entry in batch_data:
                if entry.get("status") == "success":
                    ip = entry.get("query", "")
                    result = {
                        "latitude": entry.get("lat", 0.0),
                        "longitude": entry.get("lon", 0.0),
                        "country": entry.get("country", ""),
                        "country_code": entry.get("countryCode", ""),
                        "city": entry.get("city", ""),
                        "region": entry.get("regionName", ""),
                        "isp": entry.get("isp", ""),
                        "org": entry.get("org", ""),
                        "as": entry.get("as", ""),
                        "timezone": entry.get("timezone", ""),
                    }
                    _cache.set(ip, result)
                    results[ip] = result
        except Exception:
            pass

    # Fill in empties for anything that failed
    for ip in uncached:
        if ip not in results:
            results[ip] = _empty_geo()

    return results
