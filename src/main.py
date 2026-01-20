import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.scrapers import scrape_all_sources
from src.storage.job_store import JobStore
from src.notifiers.email import send_job_email


def main():
    # Load environment variables
    load_dotenv()

    email_to = os.getenv("EMAIL_TO")
    if not email_to:
        print("EMAIL_TO environment variable not set")
        sys.exit(1)

    # Initialize job store
    data_path = os.getenv("DATA_PATH", "data/seen_jobs.json")
    store = JobStore(data_path)

    print("Starting job scraper...")

    # Scrape all sources
    all_jobs = scrape_all_sources()
    print(f"Total jobs scraped: {len(all_jobs)}")

    if not all_jobs:
        print("No jobs found from any source")
        return

    # Filter to only new jobs
    new_jobs = store.filter_new_jobs(all_jobs)
    print(f"New jobs found: {len(new_jobs)}")

    if not new_jobs:
        print("No new jobs to report")
        return

    # Send email notification
    success = send_job_email(new_jobs, email_to)

    if success:
        # Mark jobs as seen only if email was sent successfully
        store.mark_as_seen(new_jobs)
        print(f"Marked {len(new_jobs)} jobs as seen")
    else:
        print("Email failed, not marking jobs as seen")
        sys.exit(1)

    print("Job scraper completed successfully!")


if __name__ == "__main__":
    main()
