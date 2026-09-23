from types import SimpleNamespace

from jobhunt import notify
from jobhunt.db import Database
from jobhunt.models import Job


def pending_job(title="Software Engineer, New Grad", company="Acme", early_career=True):
    db = Database(":memory:")
    job = Job(key="k", url="https://jobs.example.com/1", company=company, title=title, location="Toronto, ON")
    db.add_job(job, "greenhouse:acme", "pending", "🇨🇦", early_career=early_career)
    return db.pending()[0]


def test_format_job():
    text = notify.format_job(pending_job())
    assert text.startswith("🟢 **Acme** · [Software Engineer, New Grad](<https://jobs.example.com/1>)")
    assert "📍 Toronto, ON" in text and "📝 🇨🇦" in text


def test_format_job_escapes_markdown():
    text = notify.format_job(pending_job(title="Engineer [C++] *Remote*", company="R_D"))
    assert "**R\\_D**" in text and "[Engineer \\[C++\\] \\*Remote\\*]" in text


def test_possible_fits_are_silent_and_rate_limits_are_retried(monkeypatch):
    responses = [
        SimpleNamespace(status_code=429, ok=False, json=lambda: {"retry_after": 0}),
        SimpleNamespace(status_code=204, ok=True),
    ]
    sent = []

    def post(url, json, timeout):
        sent.append(json)
        return responses.pop(0)

    monkeypatch.setattr(notify.requests, "post", post)
    monkeypatch.setattr(notify.Discord, "SEND_INTERVAL", 0)
    notify.Discord("https://discord.test/webhook").send_job(pending_job(early_career=False))
    assert len(sent) == 2
    assert sent[-1]["flags"] & notify.SUPPRESS_NOTIFICATIONS
    assert sent[-1]["allowed_mentions"] == {"parse": []}
