"""SQLite storage: every job ever seen (for dedupe), notification state, and source health."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jobhunt.models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY,
    key           TEXT NOT NULL UNIQUE,  -- identity from identity.py, e.g. greenhouse:123
    url           TEXT NOT NULL,         -- normalized posting URL, the secondary identity
    company       TEXT NOT NULL,
    title         TEXT NOT NULL,
    location      TEXT NOT NULL,
    source        TEXT NOT NULL,         -- the source that found it first
    published_at  TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    status        TEXT NOT NULL,         -- seen (recorded while seeding) | filtered | pending | notified
    reason        TEXT NOT NULL DEFAULT '',  -- why it was filtered, or notes for the notification
    early_career  INTEGER NOT NULL DEFAULT 0,
    notified_at   TEXT
);
CREATE INDEX IF NOT EXISTS jobs_url ON jobs (url);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs (status);

CREATE TABLE IF NOT EXISTS sources (
    id              TEXT PRIMARY KEY,
    last_success_at TEXT,
    job_count       INTEGER,             -- jobs listed at the last successful poll
    failing_since   TEXT,
    last_error      TEXT,
    alerted         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # --- jobs ---

    def identities(self) -> tuple[set[str], set[str]]:
        rows = self.conn.execute("SELECT key, url FROM jobs").fetchall()
        return {r["key"] for r in rows}, {r["url"] for r in rows}

    def add_job(self, job: Job, source_id: str, status: str, reason: str = "", early_career: bool = False) -> None:
        """Insert a new job. Not committed until commit(), so a whole source is saved in one transaction."""
        timestamp = now()
        published = job.published_at.isoformat(timespec="seconds") if job.published_at else None
        self.conn.execute(
            """INSERT INTO jobs (key, url, company, title, location, source, published_at,
                                 first_seen_at, last_seen_at, status, reason, early_career)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.key,
                job.url,
                job.company,
                job.title,
                job.location,
                source_id,
                published,
                timestamp,
                timestamp,
                status,
                reason,
                int(early_career),
            ),
        )

    def commit(self) -> None:
        self.conn.commit()

    def touch(self, jobs: list[Job]) -> None:
        """Record that already-known jobs are still listed. Writes at most once a day per job."""
        timestamp, day_ago = now(), _days_ago(1)
        with self.conn:
            self.conn.executemany(
                "UPDATE jobs SET last_seen_at = ? WHERE (key = ? OR url = ?) AND last_seen_at < ?",
                [(timestamp, job.key, job.url, day_ago) for job in jobs],
            )

    def pending(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM jobs WHERE status = 'pending' ORDER BY id").fetchall()

    def mark_notified(self, job_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE jobs SET status = 'notified', notified_at = ? WHERE id = ?", (now(), job_id))

    def prune(self, days: int = 90) -> int:
        """Forget unnotified jobs that haven't been listed for a long time. Notified ones are kept forever."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM jobs WHERE status IN ('seen', 'filtered') AND last_seen_at < ?", (_days_ago(days),)
            )
        return cursor.rowcount

    def stats_since(self, since: str) -> dict[str, int]:
        query = """SELECT
            COUNT(*) FILTER (WHERE first_seen_at >= :since AND status != 'seen') AS new,
            COUNT(*) FILTER (WHERE notified_at >= :since) AS notified
            FROM jobs"""
        return dict(self.conn.execute(query, {"since": since}).fetchone())

    # --- sources ---

    def last_success(self, source_id: str) -> str | None:
        row = self.conn.execute("SELECT last_success_at FROM sources WHERE id = ?", (source_id,)).fetchone()
        return row["last_success_at"] if row else None

    def record_success(self, source_id: str, job_count: int) -> bool:
        """Returns True if the source had been failing long enough to trigger an alert (i.e. it recovered)."""
        row = self.conn.execute("SELECT alerted FROM sources WHERE id = ?", (source_id,)).fetchone()
        with self.conn:
            self.conn.execute(
                """INSERT INTO sources (id, last_success_at, job_count) VALUES (?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET last_success_at = excluded.last_success_at,
                       job_count = excluded.job_count, failing_since = NULL, last_error = NULL, alerted = 0""",
                (source_id, now(), job_count),
            )
        return bool(row and row["alerted"])

    def record_failure(self, source_id: str, error: str) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT INTO sources (id, failing_since, last_error) VALUES (?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET last_error = excluded.last_error,
                       failing_since = COALESCE(failing_since, excluded.failing_since)""",
                (source_id, now(), error[:500]),
            )

    def failures_to_alert(self, after: timedelta) -> list[sqlite3.Row]:
        """Sources failing for longer than `after` that haven't been alerted about yet; marks them alerted."""
        cutoff = (datetime.now(UTC) - after).isoformat(timespec="seconds")
        rows = self.conn.execute("SELECT * FROM sources WHERE failing_since < ? AND alerted = 0", (cutoff,)).fetchall()
        with self.conn:
            self.conn.executemany("UPDATE sources SET alerted = 1 WHERE id = ?", [(r["id"],) for r in rows])
        return rows

    def failing_sources(self) -> list[str]:
        return [r["id"] for r in self.conn.execute("SELECT id FROM sources WHERE failing_since IS NOT NULL")]

    def empty_sources(self) -> list[str]:
        """Sources that work but listed no jobs last time: fine for a seasonal board, suspicious if it persists."""
        query = "SELECT id FROM sources WHERE job_count = 0 AND failing_since IS NULL"
        return [r["id"] for r in self.conn.execute(query)]

    # --- meta ---

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def _days_ago(days: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
