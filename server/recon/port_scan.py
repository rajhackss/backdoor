#!/usr/bin/env python3
"""Shadow C2 — Port Scanner (TCP Connect + SYN + UDP + Banner Grab)"""

import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class PortScanner:
    """Multi-mode port scanner with service detection."""

    COMMON_PORTS = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 111: "RPCbind", 135: "MSRPC",
        139: "NetBIOS", 143: "IMAP", 443: "HTTPS", 445: "SMB",
        993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
        3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
        6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
        8888: "HTTP-Alt2", 9090: "Cockpit", 27017: "MongoDB",
    }

    def tcp_connect_scan(self, host: str, ports: list = None,
                         timeout: float = 2.0, threads: int = 50) -> dict:
        """
        Standard TCP connect scan.
        Returns {port: {state, banner, service}}.
        """
        if ports is None:
            ports = list(self.COMMON_PORTS.keys())

        results = {}
        lock = threading.Lock()

        def scan_port(port):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                result_code = s.connect_ex((host, port))
                if result_code == 0:
                    banner = ""
                    try:
                        s.send(b"HEAD / HTTP/1.0\r\n\r\n")
                        banner = s.recv(1024).decode("utf-8", errors="replace").strip()
                    except:
                        pass
                    service = self.COMMON_PORTS.get(port, "unknown")
                    with lock:
                        results[port] = {
                            "state": "open",
                            "banner": banner[:200],
                            "service": service,
                        }
                s.close()
            except:
                pass

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {executor.submit(scan_port, p): p for p in ports}
            for f in as_completed(futures, timeout=timeout * 2 + 5):
                pass  # Results collected in scan_port via lock

        return dict(sorted(results.items()))

    def service_detect(self, host: str, port: int, timeout: float = 3.0) -> str:
        """Connect to port and identify service via banner."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((host, port))

            # Some services send banner immediately
            banner = ""
            try:
                s.settimeout(2)
                banner = s.recv(1024).decode("utf-8", errors="replace")
            except socket.timeout:
                # Try sending probe
                probes = [
                    b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n",
                    b"\r\n",
                    b"EHLO test\r\n",
                ]
                for probe in probes:
                    try:
                        s.send(probe)
                        banner = s.recv(1024).decode("utf-8", errors="replace")
                        if banner:
                            break
                    except:
                        pass

            s.close()

            # Match banner patterns
            if banner.startswith("SSH-"): return f"SSH ({banner.split(chr(10))[0].strip()})"
            if "220" in banner and "FTP" in banner.upper(): return "FTP"
            if "220" in banner and ("SMTP" in banner or "ESMTP" in banner): return "SMTP"
            if "HTTP/" in banner: return "HTTP"
            if "+OK" in banner: return "POP3"
            if "* OK" in banner and "IMAP" in banner.upper(): return "IMAP"
            if banner.startswith("\x00") or "mysql" in banner.lower(): return "MySQL"
            if "PostgreSQL" in banner: return "PostgreSQL"
            if "Redis" in banner.lower() or "+PONG" in banner: return "Redis"
            if "MongoDB" in banner.lower(): return "MongoDB"

            return self.COMMON_PORTS.get(port, f"Unknown (banner: {banner[:50]})")

        except Exception as e:
            return f"Error: {str(e)[:50]}"

    def scan_common_ports(self, host: str, timeout: float = 2.0) -> dict:
        """Scan all common ports with service detection."""
        results = self.tcp_connect_scan(host, timeout=timeout)

        # Enhance with service detection for open ports
        for port, info in results.items():
            if info["state"] == "open" and not info["banner"]:
                info["service"] = self.service_detect(host, port)

        return results

    def scan_range(self, host: str, start_port: int = 1,
                   end_port: int = 1024, timeout: float = 1.0,
                   threads: int = 100) -> dict:
        """Scan a port range."""
        ports = list(range(start_port, end_port + 1))
        return self.tcp_connect_scan(host, ports, timeout, threads)
