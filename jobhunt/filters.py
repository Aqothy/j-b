"""Deterministic relevance rules, driven by config/filters.yaml."""

import re
from dataclasses import dataclass, field

from jobhunt.models import Job

_NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
_NUMBER = r"(\d{1,2}|" + "|".join(_NUMBER_WORDS) + ")"
# "5+ years of experience", "3-5 years' relevant experience", "at least two years of professional experience"
_YEARS = re.compile(
    rf"(?<![\d.]){_NUMBER}\s*(?:\+|plus)?\s*(?:(?:-|–|to|or more)\s*\d{{0,2}}\s*)?\+?\s*years?(?:'s|')?(?=[^.;\n]{{0,60}}\bexperience)",
    re.I,
)
_MAX_PLAUSIBLE_YEARS = 15  # anything above this is company boilerplate ("40 years of experience serving...")


def _any_of(patterns: list[str]) -> re.Pattern | None:
    if not patterns:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(f"(?:{p})" for p in patterns) + r")(?!\w)", re.I)


def _search(pattern: re.Pattern | None, text: str) -> str | None:
    match = pattern.search(text) if pattern else None
    return match.group(0) if match else None


def min_years_experience(description: str) -> int | None:
    years = []
    for match in _YEARS.finditer(description):
        word = match.group(1).lower()
        value = int(word) if word.isdigit() else _NUMBER_WORDS.index(word)
        if value <= _MAX_PLAUSIBLE_YEARS:
            years.append(value)
    return min(years) if years else None


@dataclass
class Verdict:
    keep: bool
    reason: str = ""  # why it was dropped
    early_career: bool = False
    notes: list[str] = field(default_factory=list)  # shown on the notification


class Filters:
    def __init__(self, config: dict):
        title, location, description = config["title"], config["location"], config["description"]
        self.title_include = _any_of(title["include"])
        self.title_exclude = _any_of(title["exclude"])
        self.senior = _any_of(title["senior"])
        self.other_disciplines = _any_of(title["other_disciplines"])
        self.clearly_software = _any_of(title["clearly_software"])
        self.early_career = _any_of(title["early_career"])
        self.canada = _any_of(location["canada"])
        self.us = _any_of(location["us"])
        self.elsewhere = _any_of(location["elsewhere"])
        self.description_exclude = _any_of(description["exclude"])
        self.flags = [(_any_of([pattern]), note) for pattern, note in description.get("flags", {}).items()]
        self.drop_at_years = description["drop_at_years"]

    def title_reason(self, title: str) -> str | None:
        """Why this title is irrelevant, or None if it should be kept. Cheap: runs before fetching details."""
        if excluded := _search(self.title_exclude, title):
            return f"title has '{excluded}'"
        if (senior := _search(self.senior, title)) and not _search(self.early_career, title):
            return f"title has '{senior}'"
        if (other := _search(self.other_disciplines, title)) and not _search(self.clearly_software, title):
            return f"title has '{other}'"
        if not _search(self.title_include, title):
            return "title isn't software-related"
        return None

    def location_reason(self, location: str) -> str | None:
        """Why this location rules the job out, or None. Only clearly non-Canada/US locations are ruled out."""
        if _search(self.canada, location) or _search(self.us, location):
            return None
        if place := _search(self.elsewhere, location):
            return f"located outside Canada/US ({place})"
        return None

    def assess(self, job: Job) -> Verdict:
        if reason := self.title_reason(job.title):
            return Verdict(False, reason)

        if reason := self.location_reason(job.location):
            return Verdict(False, reason)
        notes = ["🇨🇦"] if _search(self.canada, job.location) else []

        description = job.description or ""
        if excluded := _search(self.description_exclude, description):
            return Verdict(False, f"description has '{excluded}'")
        years = min_years_experience(description)
        if years is not None and years >= self.drop_at_years:
            return Verdict(False, f"asks {years}+ years of experience")
        if years:
            notes.append(f"asks {years}+ yrs")
        notes += [note for pattern, note in self.flags if _search(pattern, description)]

        early = bool(_search(self.early_career, job.title)) or (years is not None and years <= 1)
        return Verdict(True, early_career=early, notes=notes)
