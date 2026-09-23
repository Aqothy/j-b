from pathlib import Path

import yaml

from jobhunt.filters import Filters
from jobhunt.models import Source
from jobhunt.sources import ADAPTERS

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_sources(path: Path = CONFIG_DIR / "sources.yaml") -> list[Source]:
    """Read sources.yaml: `kind: {Display Name: ident}`, where ident may also be a list of idents."""
    data = yaml.safe_load(path.read_text()) or {}
    if unknown := set(data) - set(ADAPTERS):
        raise ValueError(f"{path.name}: unknown source kind(s) {sorted(unknown)}; expected {list(ADAPTERS)}")
    sources = []
    for kind in ADAPTERS:  # ADAPTERS order, not file order: direct sources before backfills
        for name, idents in (data.get(kind) or {}).items():
            for ident in idents if isinstance(idents, list) else [idents]:
                sources.append(Source(kind, str(name), str(ident).strip()))
    return sources


def load_filters(path: Path = CONFIG_DIR / "filters.yaml") -> Filters:
    return Filters(yaml.safe_load(path.read_text()))
