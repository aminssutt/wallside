"""Base types for garage scraping adapters."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha1
from typing import Iterable, Optional


@dataclass
class NormalizedDoc:
    """Unit of content fed into the indexing pipeline."""

    doc_id: str
    source: str
    title: str
    text: str
    url: str = ""
    lang: str = "fr"
    brand: str = ""
    model: str = ""
    year: str = ""
    category: str = ""
    license: str = "public-data"
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extra: dict = field(default_factory=dict)

    def checksum(self) -> str:
        payload = f"{self.source}|{self.doc_id}|{self.text}"
        return sha1(payload.encode("utf-8", errors="ignore")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


class SourceAdapter:
    """Abstract base for a data source."""

    name: str = "abstract"
    license: str = "public-data"

    def fetch(self) -> Iterable[NormalizedDoc]:  # pragma: no cover
        raise NotImplementedError

    def describe(self) -> dict:
        return {"name": self.name, "license": self.license}
