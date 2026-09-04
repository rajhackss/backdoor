#!/usr/bin/env python3
"""
Shadow C2 — WebSocket Channel
Real-time bidirectional C2 via Flask-SocketIO.
Namespace /c2 for victim connections, /dashboard for operator.
"""

import logging
import time
from typing import Dict, Optional

from server.c2.channels import BaseChannel

logger = logging.getLogger("shadow_c2.channel.ws")


class WebSocketChannel(BaseChannel):
    """
    WebSocket channel using Flask-SocketIO.
    Setup is done in app.py — this class tracks connection state.
    """

    def __init__(self):
        self._alive = False
        self._connected_victims: Dict[str, dict] = {}  # {uuid: {sid, connected_at, last_ping}}
        self._operator_sids: set = set()

    @property
    def channel_type(self) -> str:
        return "websocket"

    @property
    def priority(self) -> int:
        return 2

    @property
    def bandwidth_estimate(self) -> str:
        return "high"

    def start(self):
        self._alive = True
        logger.info("WebSocket channel active (managed by SocketIO)")

    def stop(self):
        self._alive = False
        self._connected_victims.clear()
        self._operator_sids.clear()

    def is_alive(self) -> bool:
        return self._alive

    # -- victim connection tracking ------------------------------------------

    def register_victim(self, uuid: str, sid: str):
        """Track a victim WebSocket connection."""
        self._connected_victims[uuid] = {
            "sid": sid,
            "connected_at": time.time(),
            "last_ping": time.time(),
        }
        logger.info(f"WS victim connected: {uuid} (sid: {sid})")

    def unregister_victim(self, uuid: str = None, sid: str = None):
        """Remove victim connection tracking."""
        if uuid:
            self._connected_victims.pop(uuid, None)
        elif sid:
            to_remove = [u for u, d in self._connected_victims.items() if d["sid"] == sid]
            for u in to_remove:
                del self._connected_victims[u]

    def get_victim_sid(self, uuid: str) -> Optional[str]:
        """Get the SocketIO session ID for a victim."""
        info = self._connected_victims.get(uuid)
        return info["sid"] if info else None

    def is_victim_connected(self, uuid: str) -> bool:
        return uuid in self._connected_victims

    def update_ping(self, uuid: str):
        if uuid in self._connected_victims:
            self._connected_victims[uuid]["last_ping"] = time.time()

    def connected_victim_count(self) -> int:
        return len(self._connected_victims)

    def list_connected_victims(self) -> list:
        return list(self._connected_victims.keys())

    # -- operator connection tracking ----------------------------------------

    def register_operator(self, sid: str):
        self._operator_sids.add(sid)
        logger.info(f"Operator connected: {sid}")

    def unregister_operator(self, sid: str):
        self._operator_sids.discard(sid)

    def get_operator_sids(self) -> set:
        return self._operator_sids.copy()

    def has_operator(self) -> bool:
        return len(self._operator_sids) > 0
