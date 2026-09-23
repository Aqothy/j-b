import argparse
import logging
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from jobhunt import notify, pipeline
from jobhunt.config import load_filters, load_sources
from jobhunt.db import Database
from jobhunt.filters import Filters
from jobhunt.identity import board_of
from jobhunt.models import Source
from jobhunt.sources import ADAPTERS, simplify, workday


def main() -> None:
    parser = argparse.ArgumentParser(prog="jobhunt", description="Get notified about new SWE jobs.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="poll every source once and send notifications")
    check = commands.add_parser("check", help="fetch sources and show what would be kept, without saving")
    check.add_argument("match", nargs="?", default="", help="only sources whose name or ident contains this")
    commands.add_parser("suggest", help="list boards from Simplify's feeds that aren't in sources.yaml yet")
    commands.add_parser("audit", help="show which of Simplify's curated software jobs the filters would drop")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    sources, filters = load_sources(), load_filters()

    if args.command == "run":
        db = Database(os.getenv("JOBHUNT_DB", "data/jobs.db"))
        tz = ZoneInfo(os.getenv("JOBHUNT_TZ", "America/Toronto"))
        if not pipeline.run(db, sources, filters, notify.from_env(), tz):
            raise SystemExit("Notifications couldn't be delivered (see the log above).")
    elif args.command == "check":
        check_sources(sources, filters, args.match.lower())
    elif args.command == "suggest":
        suggest_sources(sources, filters)
    elif args.command == "audit":
        audit_filters(sources, filters)


def check_sources(sources: list[Source], filters: Filters, match: str) -> None:
    """Verify config entries work and preview which listed titles pass the cheap filters."""
    selected = [s for s in sources if match in s.name.lower() or match in s.ident.lower()]

    def fetch(source: Source):
        start = time.monotonic()
        try:
            return ADAPTERS[source.kind].fetch_jobs(source), time.monotonic() - start
        except Exception as error:
            return error, time.monotonic() - start

    with ThreadPoolExecutor(pipeline.WORKERS) as pool:
        for source, (result, seconds) in zip(selected, pool.map(fetch, selected)):
            if isinstance(result, Exception):
                print(f"✗ {source.name} ({source.id}): {type(result).__name__}: {result}")
                continue
            kept = [j for j in result if not (filters.title_reason(j.title) or filters.location_reason(j.location))]
            print(f"✓ {source.name} ({source.id}): {len(result)} jobs, {len(kept)} pass title/location, {seconds:.1f}s")
            if match:  # a single company: show the titles too
                for job in kept:
                    print(f"    {job.title} — {job.location}")


def suggest_sources(sources: list[Source], filters: Filters, days: int = 90, limit: int = 40) -> None:
    """Rank ATS boards behind recent relevant Simplify postings that aren't monitored directly yet.

    Boards with the most Canadian postings come first, then by total postings.
    """
    configured = {(s.kind, _board_ident(s)) for s in sources}
    cutoff = (datetime.now(UTC) - timedelta(days=days)).timestamp()
    counts: Counter[tuple[str, str]] = Counter()
    canada: Counter[tuple[str, str]] = Counter()
    names: dict[tuple[str, str], str] = {}
    for feed in (s for s in sources if s.kind == "simplify"):
        for listing in simplify.fetch_listings(feed):
            board = board_of(listing["url"])
            if not board or listing["date_posted"] < cutoff or (board[0], board[1].lower()) in configured:
                continue
            verdict = filters.assess(simplify.to_job(listing))
            if verdict.keep:
                counts[board] += 1
                canada[board] += "🇨🇦" in verdict.notes
                names[board] = listing["company_name"].strip()

    print(f"# Boards with relevant Simplify postings in the last {days} days, not yet in sources.yaml.")
    print("# Paste the ones you want under the matching section. Comments: postings found (in Canada).")
    ranked = sorted(counts, key=lambda board: (canada[board], counts[board]), reverse=True)[:limit]
    for kind in ADAPTERS:
        boards = [board for board in ranked if board[0] == kind]
        if boards:
            print(f"\n{kind}:")
            for board in boards:
                entry = yaml.safe_dump({names[board]: board[1]}, allow_unicode=True).strip()
                print(f"  {entry}  # {counts[board]} ({canada[board]} in Canada)")


def audit_filters(sources: list[Source], filters: Filters) -> None:
    """Every job on Simplify's lists was picked by a human as a real software role, so any Canada/US one
    the filters drop is a candidate false negative. Run this after editing filters.yaml."""
    for feed in (s for s in sources if s.kind == "simplify"):
        listings = [x for x in simplify.fetch_listings(feed) if x.get("active") and "Software" in x.get("category", "")]
        jobs = [simplify.to_job(x) for x in listings]
        in_scope = [job for job in jobs if not filters.location_reason(job.location)]
        dropped = [(verdict.reason, job) for job in in_scope if not (verdict := filters.assess(job)).keep]
        kept = 100 * (1 - len(dropped) / max(len(in_scope), 1))
        print(f"\n{feed.name}: {len(in_scope)} active software jobs in Canada/US, {kept:.1f}% kept. Dropped:")
        for reason, job in sorted(dropped, key=lambda pair: pair[0]):
            print(f"  {reason:45} {job.company}: {job.title}")


def _board_ident(source: Source) -> str:
    if source.kind == "workday":
        host, _, site, _, _ = workday.parse_ident(source.ident)
        return f"{host}/{site}".lower()
    return source.ident.lower()
