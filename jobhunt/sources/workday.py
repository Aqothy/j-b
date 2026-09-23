"""Workday career sites (most banks and large companies, especially in Canada).

Config ident: the career site URL as it appears in your browser, with or without https:// and
the locale, e.g. `td.wd3.myworkdayjobs.com/TD_Bank_Careers`. Filters in the URL are applied:
`?q=software` sets the search text, and any other parameter (e.g. `jobFamilyGroup=<id>`, which
Workday adds when you tick a filter on the site) is passed through as a facet. Large sites
should be narrowed this way, because every matching job is paged through on each poll.
"""

import re
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from jobhunt.models import Job, Source
from jobhunt.web import get_json, html_to_text, post_json

POLL_EVERY = timedelta(minutes=15)  # heavier than other sources (paged, unofficial API), so go easy on it
PAGE_SIZE = 20  # Workday rejects anything larger
MAX_PAGES = 100  # Workday caps results at 2000 anyway


def fetch_jobs(source: Source) -> list[Job]:
    host, tenant, site, search, facets = parse_ident(source.ident)
    api = f"https://{host}/wday/cxs/{tenant}/{site}"
    jobs: dict[str, Job] = {}
    # Results aren't reliably sorted by date, so page through all matches instead of stopping early.
    total = 0
    for page in range(MAX_PAGES):
        body = {"appliedFacets": facets, "limit": PAGE_SIZE, "offset": page * PAGE_SIZE, "searchText": search}
        data = post_json(f"{api}/jobs", body)
        if page == 0:
            total = data.get("total", 0)  # only the first page reports the real total
        postings = data.get("jobPostings") or []
        for posting in postings:
            path = posting["externalPath"]
            key = f"workday:{tenant}:{path.rsplit('/', 1)[-1]}".lower()
            jobs[key] = Job(
                key=key,
                url=f"https://{host}/{site}{path}",
                company=source.name,
                title=posting["title"].strip(),
                location=posting.get("locationsText", ""),  # e.g. "3 Locations"; load_details() resolves it
                details_url=f"{api}{path}",
            )
        if not postings or (page + 1) * PAGE_SIZE >= total:
            break
    return list(jobs.values())


def load_details(job: Job) -> None:
    info = get_json(job.details_url)["jobPostingInfo"]
    job.description = html_to_text(info.get("jobDescription", ""))
    locations = [info.get("location"), *info.get("additionalLocations", [])]
    job.location = "; ".join(filter(None, locations)) or job.location


def parse_ident(ident: str) -> tuple[str, str, str, str, dict[str, list[str]]]:
    url = urlsplit(ident if "://" in ident else f"https://{ident}")
    segments = [s for s in url.path.split("/") if s and not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", s)]
    facets = parse_qs(url.query)
    search = " ".join(facets.pop("q", []))
    return url.netloc, url.netloc.split(".")[0], segments[0], search, facets
