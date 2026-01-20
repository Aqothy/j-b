import os

from src.scrapers.github_repos import scrape_all_sources as scrape_github
from src.storage.job_store import Job


def scrape_all_sources(use_ai_filter: bool = True) -> list[Job]:
    """Scrape all job sources and return combined list.

    Args:
        use_ai_filter: If True and GEMINI_API_KEY is set, use AI to filter
                       ambiguous job titles. Defaults to True.
    """
    all_jobs = []

    # GitHub repos (community-maintained lists)
    print("\n=== Scraping GitHub Repos ===")
    github_jobs = scrape_github()
    all_jobs.extend(github_jobs)

    print(f"\n=== Total: {len(all_jobs)} jobs from all sources ===")

    return all_jobs
