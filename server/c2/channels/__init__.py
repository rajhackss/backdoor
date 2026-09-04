#!/usr/bin/env python3
"""
Shadow C2 — C2 Channel Base + Package Init
Abstract base class for all C2 channels.
"""

from abc import ABC, abstractmethod


class BaseChannel(ABC):
    """Abstract base for C2 transport channels."""

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Channel identifier: 'https', 'dns', 'websocket', 'icmp', 'social'."""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Lower = higher priority. HTTPS=1, WS=2, DNS=3, ICMP=4, Social=5."""
        ...

    @property
    def bandwidth_estimate(self) -> str:
        return "medium"

    @abstractmethod
    def start(self):
        """Start the channel listener."""
        ...

    @abstractmethod
    def stop(self):
        """Stop the channel listener."""
        ...

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if channel is operational."""
        ...

    def send(self, victim_uuid: str, data: bytes) -> bool:
        """Send data to a victim. Override in push-capable channels."""
        return False

    def receive(self) -> tuple:
        """Receive data. Returns (victim_uuid, data) or (None, None)."""
        return None, None
