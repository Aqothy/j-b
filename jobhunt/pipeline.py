"""One polling run: fetch every source, dedupe, filter, notify, and report on health."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, tzinfo

from jobhunt.db import Database
from jobhunt.filters import Filters, Verdict
from jobhunt.models import Job, Source
from jobhunt.notify import Console, Discord
from jobhunt.sources import ADAPTERS

log = logging.getLogger(__name__)

WORKERS = 16
MAX_NOTIFICATIONS_PER_RUN = 40  # a safety valve; the rest go out next run
ALERT_AFTER = timedelta(hours=3)
SUMMARY_HOUR = 9  # local time of the daily summary


def run(db: Database, sources: list[Source], filters: Filters, notifier: Discord | Console, tz: tzinfo) -> bool:
    """Returns False if notifications couldn't be sent, so the caller can fail loudly (Discord can't alert about itself)."""
    due = [s for s in sources if _is_due(db, s)]
    results = _fetch_all(due)
    known_keys, known_urls = db.identities()
    # Sources are in ADAPTERS order, so direct ATS sources claim a job before a backfill feed sees it.
    for source in due:
        result = results[source]
        if isinstance(result, Exception):
            log.warning("%s failed: %s", source.id, result)
            db.record_failure(source.id, f"{type(result).__name__}: {result}")
            continue
        try:
            _ingest(db, source, result, filters, known_keys, known_urls)
        except Exception as error:
            db.conn.rollback()
            log.exception("%s: processing failed", source.id)
            db.record_failure(source.id, f"{type(error).__name__}: {error}")
            continue
        if db.record_success(source.id, len(result)):
            _guard("sending recovery notice", notifier.send_text, f"✅ {source.id} is working again")

    delivered = _notify_pending(db, notifier)
    _guard("checking source health", _alert_failures, db, sources, notifier)
    _guard("sending the daily summary", _daily_summary, db, sources, notifier, tz)
    return delivered


def _is_due(db: Database, source: Source) -> bool:
    every = getattr(ADAPTERS[source.kind], "POLL_EVERY", None)
    last = db.last_success(source.id)
    return not (every and last and datetime.fromisoformat(last) > datetime.now(UTC) - every)


def _fetch_all(sources: list[Source]) -> dict[Source, list[Job] | Exception]:
    def fetch(source: Source) -> list[Job] | Exception:
        try:
            return ADAPTERS[source.kind].fetch_jobs(source)
        except Exception as error:  # one broken source must not affect the others
            return error

    with ThreadPoolExecutor(WORKERS) as pool:
        return dict(zip(sources, pool.map(fetch, sources)))


def _ingest(
    db: Database, source: Source, jobs: list[Job], filters: Filters, known_keys: set[str], known_urls: set[str]
) -> None:
    # The first successful poll of a source only records what's already listed, so adding a
    # company (or starting from an empty database) doesn't flood you with old postings.
    seeding = db.last_success(source.id) is None
    already_known, new, relevant = [], 0, 0
    for job in jobs:
        if job.key in known_keys or job.url in known_urls:
            already_known.append(job)
            continue
        known_keys.add(job.key)
        known_urls.add(job.url)
        new += 1
        if seeding:
            db.add_job(job, source.id, "seen")
            continue
        verdict = _assess(job, source, filters)
        relevant += verdict.keep
        status = "pending" if verdict.keep else "filtered"
        db.add_job(job, source.id, status, verdict.reason or " · ".join(verdict.notes), verdict.early_career)
    db.touch(already_known)
    db.commit()
    log.info("%s: %d listed, %d new%s", source.id, len(jobs), new, " (seeded)" if seeding else f", {relevant} relevant")


def _assess(job: Job, source: Source, filters: Filters) -> Verdict:
    if reason := filters.title_reason(job.title):
        return Verdict(False, reason)
    adapter = ADAPTERS[source.kind]
    if job.description is None and hasattr(adapter, "load_details"):
        try:
            adapter.load_details(job)
        except Exception as error:  # keep the job; it just won't get experience/location refinements
            log.warning("Couldn't load details for %s: %s", job.url, error)
    return filters.assess(job)


def _notify_pending(db: Database, notifier: Discord | Console) -> bool:
    for job in db.pending()[:MAX_NOTIFICATIONS_PER_RUN]:
        try:
            notifier.send_job(job)
        except Exception:
            log.exception("Sending notification failed; will retry next run")
            return False
        db.mark_notified(job["id"])
    return True


def _alert_failures(db: Database, sources: list[Source], notifier: Discord | Console) -> None:
    configured = {s.id for s in sources}
    for row in db.failures_to_alert(ALERT_AFTER):
        if row["id"] in configured:
            notifier.send_text(f"⚠️ {row['id']} has been failing since {row['failing_since']}\n{row['last_error']}")


def _daily_summary(db: Database, sources: list[Source], notifier: Discord | Console, tz: tzinfo) -> None:
    local_now = datetime.now(tz)
    today = local_now.date().isoformat()
    if local_now.hour < SUMMARY_HOUR or db.get_meta("summary_date") == today:
        return
    stats = db.stats_since((datetime.now(UTC) - timedelta(days=1)).isoformat(timespec="seconds"))
    configured = {s.id for s in sources}
    failing = [s for s in db.failing_sources() if s in configured]
    empty = [s for s in db.empty_sources() if s in configured]
    lines = [
        "📊 Daily summary",
        f"Sources monitored: {len(sources)} ({len(failing)} failing)",
        f"Last 24h: {stats['new']} new jobs, {stats['notified']} relevant ones sent",
    ]
    if failing:
        lines.append("Failing: " + ", ".join(failing))
    if empty:
        lines.append(
            "Listing 0 jobs (fine if seasonal; check with `jobhunt check` if it persists): " + ", ".join(empty)
        )
    notifier.send_text("\n".join(lines))
    db.set_meta("summary_date", today)
    log.info("Pruned %d old jobs", db.prune())


def _guard(what: str, func, *args) -> None:
    try:
        func(*args)
    except Exception:
        log.exception("Failed %s", what)
