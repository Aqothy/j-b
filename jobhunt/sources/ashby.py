"""Ashby job boards. Config ident: the board name, e.g. `wealthsimple` from jobs.ashbyhq.com/wealthsimple."""

from jobhunt.identity import normalize_url
from jobhunt.models import Job, Source
from jobhunt.web import get_json, parse_time


def fetch_jobs(source: Source) -> list[Job]:
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{source.ident}")
    return [
        Job(
            key=f"ashby:{job['id']}",
            url=normalize_url(job["jobUrl"]),
            company=source.name,
            title=job["title"].strip(),
            location=_location(job),
            published_at=parse_time(job.get("publishedAt")),
            description=job.get("descriptionPlain", ""),
        )
        for job in data["jobs"]
        if job.get("isListed", True)
    ]


def _location(job: dict) -> str:
    # Names like "Toronto Headquarters" are free text, so append the structured country when present.
    country = ((job.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
    names = [job.get("location") or "", *(s.get("location", "") for s in job.get("secondaryLocations", []))]
    location = "; ".join(filter(None, names))
    if country and country.lower() not in location.lower():
        location += f" ({country})"
    if job.get("isRemote") and "remote" not in location.lower():
        location += " · Remote"
    return location
