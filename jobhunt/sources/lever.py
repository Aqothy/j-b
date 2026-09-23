"""Lever job boards. Config ident: the company slug, e.g. `palantir` from jobs.lever.co/palantir."""

from jobhunt.identity import normalize_url
from jobhunt.models import Job, Source
from jobhunt.web import get_json, html_to_text, parse_time


def fetch_jobs(source: Source) -> list[Job]:
    postings = get_json(f"https://api.lever.co/v0/postings/{source.ident}", mode="json")
    jobs = []
    for posting in postings:
        categories = posting.get("categories") or {}
        locations = categories.get("allLocations") or [categories.get("location")]
        # Requirements usually live in "lists" rather than the main description.
        sections = [f"{s.get('text', '')}\n{html_to_text(s.get('content', ''))}" for s in posting.get("lists", [])]
        jobs.append(
            Job(
                key=f"lever:{posting['id']}",
                url=normalize_url(posting["hostedUrl"]),
                company=source.name,
                title=posting["text"].strip(),
                location="; ".join(filter(None, locations)),
                published_at=parse_time(posting.get("createdAt")),
                description="\n".join(
                    [posting.get("descriptionPlain", ""), *sections, posting.get("additionalPlain", "")]
                ),
            )
        )
    return jobs
