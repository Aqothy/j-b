"""Greenhouse job boards. Config ident: the board token, e.g. `stripe` from boards.greenhouse.io/stripe."""

import html

from jobhunt.identity import normalize_url
from jobhunt.models import Job, Source
from jobhunt.web import get_json, html_to_text, parse_time

API = "https://boards-api.greenhouse.io/v1/boards"


def fetch_jobs(source: Source) -> list[Job]:
    # The list endpoint omits descriptions; load_details() fetches them only for jobs that pass the title filter.
    data = get_json(f"{API}/{source.ident}/jobs")
    return [
        Job(
            key=f"greenhouse:{job['id']}",
            url=normalize_url(job["absolute_url"]),
            company=source.name,
            title=job["title"].strip(),
            location=(job.get("location") or {}).get("name") or "",
            published_at=parse_time(job.get("first_published") or job.get("updated_at")),
            details_url=f"{API}/{source.ident}/jobs/{job['id']}",
        )
        for job in data["jobs"]
    ]


def load_details(job: Job) -> None:
    job.description = html_to_text(html.unescape(get_json(job.details_url)["content"]))  # content is escaped HTML
