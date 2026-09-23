import pytest

from jobhunt.identity import board_of, job_key, normalize_url


@pytest.mark.parametrize(
    "url, key",
    [
        ("https://job-boards.greenhouse.io/figureai/jobs/4676467006", "greenhouse:4676467006"),
        ("https://boards.greenhouse.io/embed/job_app?for=toast&token=123", "greenhouse:123"),
        ("https://stripe.com/jobs/search?gh_jid=8172508", "greenhouse:8172508"),
        (
            "https://jobs.lever.co/palantir/ac978161-6f46-4f6b-ad9e-a258e642751c/apply",
            "lever:ac978161-6f46-4f6b-ad9e-a258e642751c",
        ),
        (
            "https://jobs.ashbyhq.com/wealthsimple/ca4434c0-9935-40aa-8bf9-5caaf0f2ce1b/application",
            "ashby:ca4434c0-9935-40aa-8bf9-5caaf0f2ce1b",
        ),
        (
            "https://td.wd3.myworkdayjobs.com/en-US/TD_Bank_Careers/job/Toronto-Ontario/Software-Engineer-I_R_123",
            "workday:td:software-engineer-i_r_123",
        ),
        ("https://example.com/careers/42?utm_source=Simplify&ref=Simplify", "url:https://example.com/careers/42"),
    ],
)
def test_job_key(url, key):
    assert job_key(url) == key


def test_workday_key_ignores_locale_and_site():
    # The same requisition posted on two career sites of one tenant is one job.
    a = "https://td.wd3.myworkdayjobs.com/en-US/TD_Bank_Careers/job/Toronto/SWE_R_1"
    b = "https://td.wd3.myworkdayjobs.com/Campus/job/Toronto/SWE_R_1"
    assert job_key(a) == job_key(b)


def test_similar_postings_are_not_merged():
    # Same company and title in two cities: separate postings, separate notifications.
    toronto = "https://job-boards.greenhouse.io/stripe/jobs/111"
    vancouver = "https://job-boards.greenhouse.io/stripe/jobs/222"
    assert job_key(toronto) != job_key(vancouver)


def test_normalize_url():
    assert (
        normalize_url("http://Jobs.Lever.co/acme/abc/apply/?utm_source=x&lever-source=y")
        == "https://jobs.lever.co/acme/abc"
    )
    assert normalize_url("https://acme.com/job?id=7&utm_medium=z") == "https://acme.com/job?id=7"


@pytest.mark.parametrize(
    "url, board",
    [
        ("https://job-boards.greenhouse.io/figureai/jobs/4676467006", ("greenhouse", "figureai")),
        ("https://jobs.lever.co/palantir/ac978161-6f46-4f6b-ad9e-a258e642751c", ("lever", "palantir")),
        ("https://jobs.ashbyhq.com/jerry.ai/ca4434c0-9935-40aa-8bf9-5caaf0f2ce1b", ("ashby", "jerry.ai")),
        (
            "https://td.wd3.myworkdayjobs.com/en-US/TD_Bank_Careers/job/Toronto/SWE_R_1",
            ("workday", "td.wd3.myworkdayjobs.com/TD_Bank_Careers"),
        ),
        ("https://careers.google.com/jobs/123", None),
    ],
)
def test_board_of(url, board):
    assert board_of(url) == board
