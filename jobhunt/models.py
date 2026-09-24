from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Source:
    """One entry in config/sources.yaml: a company's job board or a backfill feed."""

    kind: str  # adapter name: greenhouse, lever, ashby, workday, simplify
    name: str  # display name, e.g. "Stripe"
    ident: str  # board token, URL or repo, exactly as written in the config

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.ident}"


@dataclass
class Job:
    key: str  # stable identity, e.g. "greenhouse:12345" (see identity.py)
    url: str  # normalized posting URL, also used for dedupe
    company: str
    title: str
    location: str = ""
    published_at: datetime | None = None
    description: str | None = None  # None means "not fetched"; see details_url
    details_url: str | None = None  # fetched lazily by the adapter's load_details()
    internship: bool = False  # known to be an internship whatever the title says (Simplify's internship list)
