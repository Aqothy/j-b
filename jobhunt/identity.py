"""Job identity, used for deduplication.

Two postings are treated as the same job only when they share an exact identity:
the ATS job ID (parsed from the URL when needed) or the normalized posting URL.
There is deliberately no fuzzy company/title matching: two similar postings
(e.g. the same title in two cities) are different applications.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = re.compile(r"^(utm_.*|ref|source|src|gh_src|lever-.*|campaign)$", re.I)

# (kind, pattern) -> key "<kind>:<groups joined by ':'>". Keys must match what adapters build.
_JOB_PATTERNS = [
    ("greenhouse", r"greenhouse\.io/(?!embed/)[\w-]+/jobs/(\d+)"),
    ("greenhouse", r"greenhouse\.io/embed/job_app\?.*\btoken=(\d+)"),
    ("greenhouse", r"[?&]gh_jid=(\d+)"),
    ("lever", r"jobs\.(?:eu\.)?lever\.co/[^/]+/([0-9a-f-]{36})"),
    ("ashby", r"jobs\.ashbyhq\.com/[^/]+/([0-9a-f-]{36})"),
    ("ashby", r"[?&]ashby_jid=([0-9a-f-]{36})"),
    ("workday", r"//([\w-]+)\.wd\d+\.myworkdayjobs\.com/.*?/job/(?:[^/?#]+/)*([^/?#]+)"),
]

# (kind, pattern) -> the board a posting URL belongs to, as written in sources.yaml.
_BOARD_PATTERNS = [
    ("greenhouse", r"greenhouse\.io/(?!embed/)([\w-]+)/jobs/"),
    ("greenhouse", r"greenhouse\.io/embed/job_app\?for=([\w-]+)"),
    ("lever", r"jobs\.lever\.co/([\w.-]+)/"),
    ("ashby", r"jobs\.ashbyhq\.com/([\w.%-]+)/"),
    ("workday", r"//([\w-]+\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)/job/"),
]


def normalize_url(url: str) -> str:
    """Canonical form of a posting URL: https, lowercase host, no tracking params or /apply suffix."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(k)]
    path = re.sub(r"/(apply|application)$", "", parts.path.rstrip("/"))
    return urlunsplit(("https", parts.netloc.lower(), path, urlencode(query), ""))


def job_key(url: str) -> str:
    for kind, pattern in _JOB_PATTERNS:
        if match := re.search(pattern, url, re.I):
            return f"{kind}:" + ":".join(match.groups()).lower()
    return "url:" + normalize_url(url)


def board_of(url: str) -> tuple[str, str] | None:
    """The (kind, ident) of the job board a posting URL lives on, if it's a supported ATS."""
    for kind, pattern in _BOARD_PATTERNS:
        if match := re.search(pattern, url):
            return kind, "/".join(match.groups())
    return None
