import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import requests

from src.storage.job_store import Job


@dataclass
class RepoConfig:
    owner: str
    repo: str
    branch: str
    readme_path: str
    parser: str  # "html_table", "markdown_table", "markdown_emoji"
    section_pattern: Optional[str] = None  # Optional section to extract


REPOS = [
    # SimplifyJobs Summer 2026 Internships - HTML table with Age column
    RepoConfig(
        owner="SimplifyJobs",
        repo="Summer2026-Internships",
        branch="dev",
        readme_path="README.md",
        parser="html_table",
        section_pattern=None,  # Use entire file
    ),
    # vanshb03 Summer 2026 - Markdown table with HTML links and Date Posted column
    RepoConfig(
        owner="vanshb03",
        repo="Summer2026-Internships",
        branch="dev",
        readme_path="README.md",
        parser="html_in_markdown",
        section_pattern=None,
    ),
    # Canadian Tech Internships - Markdown table with Date Posted column
    RepoConfig(
        owner="negarprh",
        repo="Canadian-Tech-Internships-2026",
        branch="main",
        readme_path="README.md",
        parser="markdown_date",
        section_pattern=None,
    ),
    # Canada SDE Intern - Markdown table with 🆕 emoji
    RepoConfig(
        owner="hanzili",
        repo="canada_sde_intern_position",
        branch="main",
        readme_path="README.md",
        parser="markdown_emoji",
        section_pattern=None,
    ),
]


def fetch_readme(config: RepoConfig) -> str:
    """Fetch raw README content from GitHub."""
    url = f"https://raw.githubusercontent.com/{config.owner}/{config.repo}/{config.branch}/{config.readme_path}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def is_recent_age(age: str) -> bool:
    """Check if age indicates posted today or yesterday (0d or 1d)."""
    age = age.strip().lower()
    return age in ("0d", "1d")


def is_recent_date(date_str: str) -> bool:
    """Check if date string is today or yesterday."""
    today = datetime.now()
    yesterday = today - timedelta(days=1)

    date_str = date_str.strip()

    # Format: "Jan 15" or "Jan 15, 2026"
    for fmt in ("%b %d", "%b %d, %Y", "%B %d", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(date_str, fmt)
            # If no year in format, assume current year
            if "%Y" not in fmt:
                parsed = parsed.replace(year=today.year)
                # If parsed date is in the future, it's from last year
                if parsed.date() > today.date():
                    parsed = parsed.replace(year=today.year - 1)
            return parsed.date() >= yesterday.date()
        except ValueError:
            continue

    return False


def parse_html_in_markdown_table(content: str, source: str) -> list[Job]:
    """Parse markdown table with HTML links (vanshb03 format)."""
    jobs = []
    last_company = None

    lines = content.split("\n")

    for line in lines:
        if not line.strip().startswith("|"):
            continue

        # Skip header and separator rows
        if "---" in line or ("Company" in line and "Role" in line):
            continue

        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]

        if len(cells) < 5:
            continue

        # Format: Company | Role | Location | Application/Link | Date Posted
        company_cell = cells[0]
        title = cells[1] if len(cells) > 1 else ""
        location = cells[2] if len(cells) > 2 else ""
        link_cell = cells[3] if len(cells) > 3 else ""
        date_posted = cells[4] if len(cells) > 4 else ""

        # Only include recent jobs
        if not is_recent_date(date_posted):
            continue

        # Skip closed positions
        if "🔒" in line:
            continue

        # Extract company name (may have HTML link or ↳)
        company_match = re.search(r">([^<]+)</a>", company_cell)
        if company_match:
            company = company_match.group(1).strip()
            last_company = company
        elif "↳" in company_cell:
            if last_company:
                company = last_company
            else:
                continue
        else:
            company = re.sub(r"<[^>]+>", "", company_cell).strip()
            if company:
                last_company = company

        # Clean title (remove HTML)
        title = re.sub(r"<[^>]+>", "", title).strip()

        # Clean location (remove HTML and </br>)
        location = re.sub(
            r"<details>.*?</details>", "Multiple locations", location, flags=re.DOTALL
        )
        location = re.sub(r"<[^>]+>", "", location).strip()
        location = location.replace("</br>", ", ")

        # Extract link from HTML <a> tag
        link_match = re.search(r'href="([^"]+)"', link_cell)
        if link_match:
            link = link_match.group(1)
        else:
            continue

        if not company or not title or not link:
            continue

        jobs.append(
            Job(
                company=company,
                title=title,
                location=location if location else "Not specified",
                link=link,
                source=source,
                date_added=date_posted,
            )
        )

    return jobs


def extract_section(content: str, section_pattern: Optional[str]) -> str:
    """Extract a specific section from content, or return full content."""
    if not section_pattern:
        return content

    section_start = content.find(section_pattern.replace(r"\\", "\\"))
    if section_start == -1:
        # Try regex
        match = re.search(section_pattern, content)
        if match:
            section_start = match.start()
        else:
            return content

    # Find next ## heading or end of file
    next_section = re.search(r"\n## ", content[section_start + 10 :])
    if next_section:
        section_end = section_start + 10 + next_section.start()
    else:
        section_end = len(content)

    return content[section_start:section_end]


def parse_html_table(content: str, source: str) -> list[Job]:
    """Parse HTML table format used by SimplifyJobs repos."""
    jobs = []
    last_company = None

    # Find all table rows
    row_pattern = re.compile(
        r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>",
        re.DOTALL,
    )

    for match in row_pattern.finditer(content):
        company_cell = match.group(1).strip()
        title = match.group(2).strip()
        location = match.group(3).strip()
        link_cell = match.group(4).strip()
        age = match.group(5).strip()

        # Only include recent jobs (today or yesterday)
        if not is_recent_age(age):
            continue

        # Skip closed positions
        if "🔒" in link_cell:
            continue

        # Extract company name from link or plain text
        company_match = re.search(r">([^<]+)</a>", company_cell)
        if company_match:
            company = company_match.group(1).strip()
            last_company = company
        elif "↳" in company_cell:
            # Continuation row - use previous company
            if last_company:
                company = last_company
            else:
                continue
        else:
            company = re.sub(r"<[^>]+>", "", company_cell).strip()
            if company:
                last_company = company

        # Clean up title (remove HTML tags)
        title = re.sub(r"<[^>]+>", "", title).strip()

        # Clean up location (remove HTML tags and details)
        location = re.sub(
            r"<details>.*?</details>", "Multiple locations", location, flags=re.DOTALL
        )
        location = re.sub(r"<[^>]+>", "", location).strip()
        location = location.replace("</br>", ", ")

        # Extract application link
        link_match = re.search(r'href="([^"]+)"', link_cell)
        if link_match:
            link = link_match.group(1)
            # Remove tracking parameters
            link = re.sub(r"\?utm_source=Simplify.*", "", link)
        else:
            continue

        # Skip if essential fields are missing
        if not company or not title or not link:
            continue

        jobs.append(
            Job(
                company=company,
                title=title,
                location=location if location else "Not specified",
                link=link,
                source=source,
                date_added=age,
            )
        )

    return jobs


def parse_markdown_table_with_date(content: str, source: str) -> list[Job]:
    """Parse Markdown table with Date Posted column."""
    jobs = []
    last_company = None

    # Find table rows (lines starting with |)
    lines = content.split("\n")

    for line in lines:
        if not line.strip().startswith("|"):
            continue

        # Skip header and separator rows
        if "---" in line or "Company" in line and "Role" in line:
            continue

        cells = [c.strip() for c in line.split("|")]
        # Remove empty first/last cells from split
        cells = [c for c in cells if c]

        if len(cells) < 4:
            continue

        # Detect format based on column count
        # vanshb03: Company | Role | Location | Application/Link | Date Posted
        # negarprh: Company | Role | Location | Apply | Date Posted
        company_cell = cells[0]
        title = cells[1] if len(cells) > 1 else ""
        location = cells[2] if len(cells) > 2 else ""
        link_cell = cells[3] if len(cells) > 3 else ""
        date_posted = cells[4] if len(cells) > 4 else cells[-1]

        # Only include recent jobs
        if not is_recent_date(date_posted):
            continue

        # Skip closed positions
        if "🔒" in line:
            continue

        # Extract company name
        company_match = re.search(r"\[([^\]]+)\]", company_cell)
        if company_match:
            company = company_match.group(1).strip()
            last_company = company
        elif "↳" in company_cell:
            if last_company:
                company = last_company
            else:
                continue
        else:
            company = re.sub(r"[*_`]", "", company_cell).strip()
            if company:
                last_company = company

        # Clean title
        title = re.sub(r"[*_`]", "", title).strip()

        # Clean location
        location = re.sub(r"[*_`]", "", location).strip()

        # Extract link
        link_match = re.search(r"\[.*?\]\((https?://[^)]+)\)", link_cell)
        if not link_match:
            # Try finding link in any cell
            link_match = re.search(r"\[.*?\]\((https?://[^)]+)\)", line)
        if link_match:
            link = link_match.group(1)
        else:
            continue

        if not company or not title or not link:
            continue

        jobs.append(
            Job(
                company=company,
                title=title,
                location=location if location else "Not specified",
                link=link,
                source=source,
                date_added=date_posted,
            )
        )

    return jobs


def parse_markdown_table_with_emoji(content: str, source: str) -> list[Job]:
    """Parse Markdown table that uses 🆕 emoji for new jobs (hanzili format)."""
    jobs = []

    # hanzili format: Title | Company | Role | Company Info | Details | Location | Apply
    # The 🆕 emoji appears in the Title column for new jobs

    lines = content.split("\n")

    for line in lines:
        if not line.strip().startswith("|"):
            continue

        # Only include rows with 🆕 emoji (new jobs)
        if "🆕" not in line:
            continue

        # Skip header rows
        if "---" in line or ("Title" in line and "Company" in line and "Apply" in line):
            continue

        # Skip closed positions
        if "🔒" in line:
            continue

        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]

        if len(cells) < 6:
            continue

        # Format: Title | Company | Role | Company Info | Details | Location | Apply
        title_cell = cells[0]
        company = cells[1] if len(cells) > 1 else ""
        role = cells[2] if len(cells) > 2 else ""
        # company_info = cells[3]  # Not needed
        # details = cells[4]  # Not needed
        location = cells[5] if len(cells) > 5 else ""
        link_cell = cells[6] if len(cells) > 6 else ""

        # Clean title (remove emoji and HTML comments)
        title = title_cell.replace("🆕", "").replace("🔥", "").replace("💤", "").strip()
        title = re.sub(r"<!--.*?-->", "", title).strip()
        title = re.sub(r"[*_`]", "", title).strip()

        # Use role if title is empty
        if not title and role:
            title = re.sub(r"[*_`]", "", role).strip()

        # Clean company
        company = re.sub(r"[*_`]", "", company).strip()

        # Clean location
        location = re.sub(r"[*_`]", "", location).strip()

        # Extract link - hanzili uses [Apply](<url>) format with angle brackets
        link_match = re.search(r"\[.*?\]\(<?(https?://[^>)]+)>?\)", link_cell)
        if not link_match:
            link_match = re.search(r"\[.*?\]\(<?(https?://[^>)]+)>?\)", line)
        if link_match:
            link = link_match.group(1)
        else:
            continue

        if not company or not title or not link:
            continue

        jobs.append(
            Job(
                company=company,
                title=title,
                location=location if location else "Not specified",
                link=link,
                source=source,
                date_added="New",
            )
        )

    return jobs


def scrape_repo(config: RepoConfig) -> list[Job]:
    """Scrape a single repository based on its config."""
    source = f"{config.owner}/{config.repo}"

    try:
        content = fetch_readme(config)
        content = extract_section(content, config.section_pattern)

        if config.parser == "html_table":
            return parse_html_table(content, source)
        elif config.parser == "html_in_markdown":
            return parse_html_in_markdown_table(content, source)
        elif config.parser == "markdown_date":
            return parse_markdown_table_with_date(content, source)
        elif config.parser == "markdown_emoji":
            return parse_markdown_table_with_emoji(content, source)
        else:
            print(f"Unknown parser: {config.parser}")
            return []
    except Exception as e:
        print(f"Error scraping {source}: {e}")
        return []


def scrape_all_sources() -> list[Job]:
    """Scrape all configured GitHub sources."""
    all_jobs = []

    for config in REPOS:
        source = f"{config.owner}/{config.repo}"
        jobs = scrape_repo(config)
        all_jobs.extend(jobs)
        print(f"Scraped {len(jobs)} recent jobs from {source}")

    return all_jobs
