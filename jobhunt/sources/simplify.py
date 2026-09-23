"""SimplifyJobs GitHub lists, used as a backfill for companies not monitored directly.

Config ident: the GitHub repo, e.g. `SimplifyJobs/New-Grad-Positions`. Postings that were
already found through a direct source are recognized by URL (see identity.py) and not re-sent.
"""

from datetime import UTC, datetime, timedelta

from jobhunt.identity import job_key, normalize_url
from jobhunt.models import Job, Source
from jobhunt.web import get_json, parse_time

POLL_EVERY = timedelta(minutes=30)  # each feed is ~13MB, and it's a backfill, not the fast path
LOOKBACK = timedelta(days=7)


def fetch_listings(source: Source) -> list[dict]:
    return get_json(f"https://raw.githubusercontent.com/{source.ident}/dev/.github/scripts/listings.json")


def fetch_jobs(source: Source) -> list[Job]:
    cutoff = (datetime.now(UTC) - LOOKBACK).timestamp()
    return [
        to_job(listing)
        for listing in fetch_listings(source)
        if listing.get("active") and listing.get("is_visible", True) and listing["date_posted"] >= cutoff
    ]


def to_job(listing: dict) -> Job:
    url = normalize_url(listing["url"])
    return Job(
        key=job_key(url),
        url=url,
        company=listing["company_name"].strip(),
        title=listing["title"].strip(),
        location="; ".join(listing.get("locations") or []),
        published_at=parse_time(listing["date_posted"]),
        # Simplify has no description, but its sponsorship field feeds the same work-authorization rules.
        description=f"Sponsorship: {listing.get('sponsorship', '')}",
    )
