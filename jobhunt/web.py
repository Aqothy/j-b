"""Small HTTP and text helpers shared by the source adapters."""

import html
import re
from datetime import UTC, datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

TIMEOUT = 30

_session = requests.Session()
_session.headers["User-Agent"] = "jobhunt (personal job alerts)"
# Retry transient failures (Workday in particular returns sporadic 500s). allowed_methods=None includes POST.
_retry = Retry(total=2, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=None)
_session.mount("https://", HTTPAdapter(pool_maxsize=32, max_retries=_retry))


def get_json(url: str, **params):
    response = _session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def post_json(url: str, body: dict):
    response = _session.post(url, json=body, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def html_to_text(markup: str) -> str:
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", markup, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"[ \t\xa0]+", " ", text).strip()


def parse_time(value: str | int | float | None) -> datetime | None:
    """Parse an ISO string or a unix timestamp (seconds or milliseconds)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
