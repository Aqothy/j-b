from datetime import UTC, timedelta
from types import SimpleNamespace

import pytest

from jobhunt import pipeline
from jobhunt.config import load_filters
from jobhunt.db import Database
from jobhunt.models import Job, Source

ATS = Source("fake", "Acme", "acme")
FEED = Source("feed", "Feed", "feed")


class RecordingNotifier:
    def __init__(self):
        self.jobs, self.texts = [], []

    def send_job(self, job):
        self.jobs.append(job["title"])

    def send_text(self, text):
        self.texts.append(text)


@pytest.fixture
def world(monkeypatch):
    """Two fake adapters whose listings each test controls."""
    listings = {ATS: [], FEED: []}
    fake = SimpleNamespace(fetch_jobs=lambda source: list(listings[source]))
    monkeypatch.setattr(pipeline, "ADAPTERS", {"fake": fake, "feed": fake})
    monkeypatch.setattr(pipeline, "SUMMARY_HOUR", 24)  # never send the daily summary in tests
    db, notifier = Database(":memory:"), RecordingNotifier()

    def run():
        pipeline.run(db, [ATS, FEED], load_filters(), notifier, UTC)

    return SimpleNamespace(listings=listings, db=db, notifier=notifier, run=run)


def posting(n: int, title: str = "Software Engineer, New Grad", url: str | None = None) -> Job:
    return Job(
        key=f"fake:{n}",
        url=url or f"https://jobs.example.com/{n}",
        company="Acme",
        title=title,
        location="Toronto, ON",
        description="",
    )


def test_first_poll_seeds_without_notifying(world):
    world.listings[ATS] = [posting(1), posting(2)]
    world.run()
    assert world.notifier.jobs == []


def test_new_relevant_job_notifies_once(world):
    world.listings[ATS] = [posting(1)]
    world.run()
    world.listings[ATS] = [posting(1), posting(2, "Software Developer"), posting(3, "Senior Software Engineer")]
    world.run()
    world.run()
    assert world.notifier.jobs == ["Software Developer"]


def test_same_job_from_backfill_is_not_renotified(world):
    world.run()  # seed both sources while empty
    world.listings[ATS] = [posting(1, url="https://job-boards.greenhouse.io/acme/jobs/1")]
    world.run()
    # The backfill finds the same posting later under a different key; the URL still matches.
    world.listings[FEED] = [posting(99, url="https://job-boards.greenhouse.io/acme/jobs/1")]
    world.run()
    assert world.notifier.jobs == ["Software Engineer, New Grad"]


def test_failing_source_does_not_block_others(world, monkeypatch):
    def fetch(source):
        if source is ATS:
            raise ConnectionError("down")
        return list(world.listings[source])

    monkeypatch.setattr(
        pipeline, "ADAPTERS", {"fake": SimpleNamespace(fetch_jobs=fetch), "feed": SimpleNamespace(fetch_jobs=fetch)}
    )
    world.run()
    world.listings[FEED] = [posting(5)]
    world.run()
    assert world.notifier.jobs == ["Software Engineer, New Grad"]
    assert world.db.failing_sources() == [ATS.id]


def test_failed_notification_is_retried(world):
    world.run()
    world.listings[ATS] = [posting(1)]
    sent = world.notifier.send_job
    world.notifier.send_job = lambda job: (_ for _ in ()).throw(RuntimeError("discord down"))
    world.run()
    world.notifier.send_job = sent
    world.run()
    assert world.notifier.jobs == ["Software Engineer, New Grad"]


def test_undeliverable_notifications_fail_the_run(world):
    world.run()
    world.listings[ATS] = [posting(1)]
    world.notifier.send_job = lambda job: (_ for _ in ()).throw(RuntimeError("webhook deleted"))
    assert pipeline.run(world.db, [ATS, FEED], load_filters(), world.notifier, UTC) is False


def test_empty_boards_are_reported(world):
    world.listings[FEED] = [posting(1)]
    world.run()
    assert world.db.empty_sources() == [ATS.id]


def test_slow_sources_wait_between_polls(world, monkeypatch):
    calls = []
    slow = SimpleNamespace(POLL_EVERY=timedelta(minutes=15), fetch_jobs=lambda source: calls.append(source) or [])
    monkeypatch.setattr(pipeline, "ADAPTERS", {"fake": slow, "feed": slow})
    world.run()
    world.run()
    assert calls == [ATS, FEED]  # the second run was within 15 minutes, so nothing was fetched
