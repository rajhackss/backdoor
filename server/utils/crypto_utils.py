#!/usr/bin/env python3
"""
Shadow C2 — Low-level Cryptographic Primitives
Built on top of `cryptography` library and stdlib hashlib/hmac.
"""

import os
import hmac as _hmac
import hashlib
import uuid as _uuid
import struct
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.x509 import (
    CertificateBuilder, Name, NameAttribute, random_serial_number
)
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import ec
import datetime

try:
    import bcrypt as _bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False


# ---------------------------------------------------------------------------
# Random
# ---------------------------------------------------------------------------

def generate_random_bytes(n: int) -> bytes:
    """Cryptographically secure random bytes."""
    return os.urandom(n)


def generate_random_hex(n: int) -> str:
    """Random hex string of n bytes (2n hex chars)."""
    return os.urandom(n).hex()


def generate_uuid() -> str:
    """Generate a random UUID4 string."""
    return str(_uuid.uuid4())


# ---------------------------------------------------------------------------
# XOR
# ---------------------------------------------------------------------------

def xor_bytes(data: bytes, key: bytes) -> bytes:
    """Repeating-key XOR."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


# ---------------------------------------------------------------------------
# AES-256-GCM
# ---------------------------------------------------------------------------

def aes_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """
    AES-256-GCM encrypt.
    Returns: nonce(12) || ciphertext || tag(16)
    Key must be 32 bytes.
    """
    if len(key) != 32:
        raise ValueError("AES-256 key must be 32 bytes")
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)  # ct includes 16-byte tag
    return nonce + ct


def aes_decrypt(data: bytes, key: bytes) -> bytes:
    """
    AES-256-GCM decrypt.
    Expects: nonce(12) || ciphertext || tag(16)
    """
    if len(key) != 32:
        raise ValueError("AES-256 key must be 32 bytes")
    if len(data) < 28:  # 12 nonce + 16 tag minimum
        raise ValueError("Ciphertext too short")
    nonce = data[:12]
    ct = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


# ---------------------------------------------------------------------------
# Key Derivation
# ---------------------------------------------------------------------------

def derive_key(password: str, salt: bytes = None, iterations: int = 100_000,
               length: int = 32) -> Tuple[bytes, bytes]:
    """
    PBKDF2-HMAC-SHA256 key derivation.
    Returns (derived_key, salt).
    """
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode()), salt


def hkdf_expand(key_material: bytes, info: bytes, length: int = 32) -> bytes:
    """HKDF-SHA256 expand."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=info,
    )
    return hkdf.derive(key_material)


# ---------------------------------------------------------------------------
# HMAC
# ---------------------------------------------------------------------------

def hmac_sign(data: bytes, key: bytes) -> bytes:
    """HMAC-SHA256 signature."""
    return _hmac.new(key, data, hashlib.sha256).digest()


def hmac_verify(data: bytes, key: bytes, signature: bytes) -> bool:
    """Constant-time HMAC-SHA256 verification."""
    expected = _hmac.new(key, data, hashlib.sha256).digest()
    return _hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_hash(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def sha256_hash_str(s: str) -> str:
    return sha256_hash(s.encode())


# ---------------------------------------------------------------------------
# X25519 Key Exchange (ECDH)
# ---------------------------------------------------------------------------

def generate_x25519_keypair() -> Tuple[bytes, bytes]:
    """
    Generate X25519 keypair for ECDH.
    Returns (private_key_bytes, public_key_bytes).
    """
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption()
    )
    pub_bytes = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw
    )
    return priv_bytes, pub_bytes


def x25519_derive_shared(private_bytes: bytes, peer_public_bytes: bytes) -> bytes:
    """Derive shared secret from X25519 ECDH."""
    private_key = X25519PrivateKey.from_private_bytes(private_bytes)
    peer_public = X25519PublicKey.from_public_bytes(peer_public_bytes)
    return private_key.exchange(peer_public)


# ---------------------------------------------------------------------------
# RSA
# ---------------------------------------------------------------------------

def generate_rsa_keypair(bits: int = 2048) -> Tuple[bytes, bytes]:
    """Generate RSA keypair. Returns (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()
    )
    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return priv_pem, pub_pem


def rsa_encrypt(plaintext: bytes, public_pem: bytes) -> bytes:
    """RSA-OAEP encrypt."""
    pub_key = serialization.load_pem_public_key(public_pem)
    return pub_key.encrypt(
        plaintext,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def rsa_decrypt(ciphertext: bytes, private_pem: bytes) -> bytes:
    """RSA-OAEP decrypt."""
    priv_key = serialization.load_pem_private_key(private_pem, password=None)
    return priv_key.decrypt(
        ciphertext,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


# ---------------------------------------------------------------------------
# Self-signed certificate
# ---------------------------------------------------------------------------

def generate_self_signed_cert(hostname: str = "localhost",
                              cert_path: str = None,
                              key_path: str = None) -> Tuple[bytes, bytes]:
    """
    Generate a self-signed TLS certificate.
    Returns (cert_pem, key_pem). Optionally writes to files.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = Name([
        NameAttribute(NameOID.COUNTRY_NAME, "US"),
        NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
        NameAttribute(NameOID.ORGANIZATION_NAME, "Shadow Security Research"),
        NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()
    )
    if cert_path:
        with open(cert_path, "wb") as f:
            f.write(cert_pem)
    if key_path:
        with open(key_path, "wb") as f:
            f.write(key_pem)
    return cert_pem, key_pem


# ---------------------------------------------------------------------------
# Bcrypt (password hashing)
# ---------------------------------------------------------------------------

def bcrypt_hash(password: str) -> str:
    """Hash password with bcrypt. Falls back to PBKDF2 if bcrypt unavailable."""
    if HAS_BCRYPT:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    # Fallback: PBKDF2
    key, salt = derive_key(password)
    return f"pbkdf2${salt.hex()}${key.hex()}"


def bcrypt_verify(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    if HAS_BCRYPT and hashed.startswith("$2"):
        return _bcrypt.checkpw(password.encode(), hashed.encode())
    # Fallback PBKDF2
    if hashed.startswith("pbkdf2$"):
        parts = hashed.split("$")
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
        key, _ = derive_key(password, salt)
        return _hmac.compare_digest(key, expected)
    return False
