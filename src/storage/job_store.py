import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Job:
    company: str
    title: str
    location: str
    link: str
    source: str
    date_added: Optional[str] = None

    @property
    def id(self) -> str:
        """Generate unique ID from company + title + link."""
        raw = f"{self.company}{self.title}{self.link}".lower().strip()
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)


class JobStore:
    def __init__(self, data_path: str = "data/seen_jobs.json"):
        self.data_path = Path(data_path)
        self._ensure_file_exists()
        self._data = self._load()

    def _ensure_file_exists(self) -> None:
        if not self.data_path.exists():
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            self._save({"seen_ids": [], "last_updated": None})

    def _load(self) -> dict:
        with open(self.data_path, "r") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        with open(self.data_path, "w") as f:
            json.dump(data, f, indent=2)

    @property
    def seen_ids(self) -> set[str]:
        return set(self._data.get("seen_ids", []))

    def filter_new_jobs(self, jobs: list[Job]) -> list[Job]:
        """Return only jobs we haven't seen before."""
        seen = self.seen_ids
        return [job for job in jobs if job.id not in seen]

    def mark_as_seen(self, jobs: list[Job]) -> None:
        """Add job IDs to the seen list and persist."""
        new_ids = [job.id for job in jobs]
        self._data["seen_ids"] = list(self.seen_ids | set(new_ids))
        self._data["last_updated"] = datetime.now().isoformat()
        self._save(self._data)
