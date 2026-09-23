"""Notifications: a Discord webhook when configured, otherwise printed to the console (handy locally)."""

import logging
import os
import re
import sqlite3
import time
from datetime import UTC, datetime

import requests

log = logging.getLogger(__name__)

SUPPRESS_EMBEDS = 1 << 2  # no link previews
SUPPRESS_NOTIFICATIONS = 1 << 12  # delivered silently (no push/sound)


def from_env() -> "Discord | Console":
    if url := os.getenv("DISCORD_WEBHOOK_URL"):
        return Discord(url)
    if os.getenv("GITHUB_ACTIONS"):
        # Printing in CI would mark jobs as notified without anyone seeing them.
        raise SystemExit("Set the DISCORD_WEBHOOK_URL repository secret.")
    log.info("DISCORD_WEBHOOK_URL not set; printing notifications instead")
    return Console()


def format_job(job: sqlite3.Row) -> str:
    """🟢 = early-career title (sent with a notification), 🟡 = possible fit (sent silently)."""
    icon = "🟢" if job["early_career"] else "🟡"
    lines = [f"{icon} **{_escape(job['company'])}** · [{_escape(job['title'])}](<{job['url']}>)"]
    details = []
    if job["location"]:
        details.append(f"📍 {_escape(_truncate(job['location'], 120))}")
    found_via = job["source"].split(":")[0]
    details.append(
        f"🕒 posted {_age(job['published_at'])} ago · {found_via}" if job["published_at"] else f"🕒 via {found_via}"
    )
    lines.append("  ".join(details))
    if job["reason"]:
        lines.append(f"📝 {_escape(job['reason'])}")
    return "\n".join(lines)


class Console:
    def send_job(self, job: sqlite3.Row) -> None:
        print(f"\n{format_job(job)}")

    def send_text(self, text: str) -> None:
        print(f"\n{text}")


class Discord:
    SEND_INTERVAL = 2.1  # webhooks allow about 30 messages a minute per channel

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_job(self, job: sqlite3.Row) -> None:
        flags = SUPPRESS_EMBEDS | (0 if job["early_career"] else SUPPRESS_NOTIFICATIONS)
        self._post(format_job(job), flags)
        time.sleep(self.SEND_INTERVAL)

    def send_text(self, text: str) -> None:
        self._post(text, SUPPRESS_EMBEDS)

    def _post(self, content: str, flags: int) -> None:
        body = {"content": content[:2000], "flags": flags, "allowed_mentions": {"parse": []}}
        for _ in range(3):
            try:
                response = requests.post(self.webhook_url, json=body, timeout=30)
            except requests.RequestException as error:
                # Don't let the exception text (which includes the secret webhook URL) reach the logs.
                raise RuntimeError(f"Discord webhook failed: {type(error).__name__}") from None
            if response.status_code == 429:
                time.sleep(float(response.json().get("retry_after", 5)))
                continue
            if response.ok:
                return
            raise RuntimeError(f"Discord webhook failed: HTTP {response.status_code} {response.text[:200]}")
        raise RuntimeError("Discord webhook failed: still rate limited")


def _escape(text: str) -> str:
    return re.sub(r"([\\*_~`|\[\]])", r"\\\1", text)


def _age(iso: str) -> str:
    minutes = int((datetime.now(UTC) - datetime.fromisoformat(iso)).total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 0)}m"
    if minutes < 48 * 60:
        return f"{minutes // 60}h"
    return f"{minutes // (24 * 60)}d"


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
