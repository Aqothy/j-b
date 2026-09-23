import pytest

from jobhunt.config import load_filters
from jobhunt.filters import min_years_experience
from jobhunt.models import Job

filters = load_filters()


def job(title="Software Engineer", location="Toronto, ON", description="") -> Job:
    return Job(key="k", url="u", company="Acme", title=title, location=location, description=description)


@pytest.mark.parametrize(
    "title",
    [
        "Software Engineer",
        "Software Developer I",
        "Associate Software Engineer",
        "Junior Developer",
        "Technology Analyst",
        "iOS Engineer",
        "Full-Stack Developer (React)",
        "Software Engineer Intern/Co-op (Winter 2027)",
        "2027 Summer Analyst - Software Engineering Rotational Program (Toronto)",
        "Member of Technical Staff (Software Engineer, Monetization)",
        "Software Engineer III",
        "Software Engineer New Grad - Hardware Tools and Methodology",
        "FPGA Software Tool Developer Co-op",
        "Software Engineer / Principal Software Engineer - New Grad",
        "Member of Technical Staff New Grad",
        "AI Intern",
        "Engineering Fellow",
    ],
)
def test_relevant_titles_are_kept(title):
    assert filters.title_reason(title) is None


@pytest.mark.parametrize(
    "title",
    [
        "Senior Software Engineer",
        "Sr. Software Developer",
        "Staff Engineer, Platform",
        "Engineering Manager",
        "Principal Architect",
        "Software Engineer IV",
        "Hardware Engineer",
        "Electrical Engineering Intern",
        "Sales Engineer",
        "Product Designer",
        "Account Executive",
        "Recruiter, Engineering",
        "Hardware Engineer II",
        "Data Scientist",
        "Personal Banking Associate",
    ],
)
def test_irrelevant_titles_are_dropped(title):
    assert filters.title_reason(title) is not None


@pytest.mark.parametrize(
    "location, kept",
    [
        ("Toronto, ON", True),
        ("London, ON", True),
        ("Remote", True),
        ("3 Locations", True),
        ("", True),
        ("New York, NY; London, UK", True),
        ("US, CA, Santa Clara", True),
        ("London", False),
        ("Bengaluru, India", False),
        ("Belgrade; London; Berlin (Serbia)", False),
    ],
)
def test_location(location, kept):
    assert filters.assess(job(location=location)).keep is kept


def test_canada_is_flagged():
    assert "🇨🇦" in filters.assess(job(location="Remote (Canada)")).notes


@pytest.mark.parametrize(
    "text, years",
    [
        ("5+ years of professional software development experience", 5),
        ("3-5 years' relevant experience", 3),
        ("at least two years of industry experience", 2),
        ("Requirements: 7 years of experience. Nice to have: 2+ years experience with Go", 2),
        ("We've been in business for 40 years of experience serving customers", None),
        ("Graduating in 2027 with experience in Python", None),
        ("No experience required", None),
    ],
)
def test_min_years_experience(text, years):
    assert min_years_experience(text) == years


def test_experience_threshold():
    assert not filters.assess(job(description="Requires 5+ years of experience building APIs.")).keep
    verdict = filters.assess(job(description="2+ years of experience with React."))
    assert verdict.keep and "asks 2+ yrs" in verdict.notes


def test_work_authorization():
    assert not filters.assess(job(description="Sponsorship: U.S. Citizenship is Required")).keep
    itar = "ITAR REQUIREMENTS: To conform to U.S. export regulations, applicant must be a (i) U.S. citizen or national"
    assert not filters.assess(job(description=itar)).keep
    verdict = filters.assess(job(description="We do not offer visa sponsorship for this role."))
    assert verdict.keep and "no visa sponsorship" in verdict.notes


def test_early_career():
    assert filters.assess(job(title="Software Engineer, New Grad")).early_career
    assert filters.assess(job(description="0-2 years of experience")).early_career
    assert not filters.assess(job(title="Software Engineer")).early_career
