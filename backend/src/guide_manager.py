"""
Guide manager for pre-indexed vehicle manuals.
Each guide lives under data/guides/<slug>/ with FAISS + BM25 indexes.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR

log = logging.getLogger("auris")

GUIDES_DIR = DATA_DIR / "guides"
GUIDES_DIR.mkdir(parents=True, exist_ok=True)

_MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e3", "\ufffd")
_COMMON_MOJIBAKE_REPLACEMENTS = {
    "Ã©": "é",
    "Ã¨": "è",
    "Ãª": "ê",
    "Ã«": "ë",
    "Ã ": "à",
    "Ã¢": "â",
    "Ã¤": "ä",
    "Ã®": "î",
    "Ã¯": "ï",
    "Ã´": "ô",
    "Ã¶": "ö",
    "Ã¹": "ù",
    "Ã»": "û",
    "Ã¼": "ü",
    "Ã§": "ç",
    "ã©": "é",
    "ã¨": "è",
    "ãª": "ê",
    "ã«": "ë",
    "ã ": "à",
    "ã¢": "â",
    "ã¤": "ä",
    "ã®": "î",
    "ã¯": "ï",
    "ã´": "ô",
    "ã¶": "ö",
    "ã¹": "ù",
    "ã»": "û",
    "ã¼": "ü",
    "ã§": "ç",
}
_CANONICAL_BRANDS = {
    "bmw": "BMW",
    "alfa romeo": "Alfa Romeo",
    "alfa roméo": "Alfa Romeo",
}


def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in _MOJIBAKE_MARKERS)


def _replace_common_mojibake(text: str) -> str:
    repaired = text
    for broken, fixed in _COMMON_MOJIBAKE_REPLACEMENTS.items():
        repaired = repaired.replace(broken, fixed)
    return repaired


def _repair_mojibake(text: str) -> str:
    """Best-effort fix for strings decoded with the wrong codec."""
    if not text:
        return ""

    best = _replace_common_mojibake(text)
    best_score = _mojibake_score(best)
    candidate = text

    # Try one or two latin1->utf8 repair passes for double-decoding cases.
    for _ in range(2):
        try:
            candidate = candidate.encode("latin1").decode("utf-8")
        except UnicodeError:
            break

        candidate = _replace_common_mojibake(candidate)
        score = _mojibake_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score

    return best


def _clean_text(value: Optional[str], default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    text = _repair_mojibake(text)
    return text or default


def _normalize_brand(brand: str) -> str:
    key = (brand or "").casefold()
    return _CANONICAL_BRANDS.get(key, brand)


def slugify(name: str) -> str:
    """Convert a guide name to a filesystem-safe slug."""
    s = _clean_text(name).lower()
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "guide"


class Guide:
    """Represents a pre-indexed vehicle guide."""

    def __init__(
        self,
        slug: str,
        name: str,
        image: Optional[str] = None,
        brand: Optional[str] = None,
        segment: Optional[str] = None,
    ):
        self.slug = slug
        self.name = _clean_text(name, slug)
        self.image = _clean_text(image) or None  # filename like "clio-4.png"
        self.brand = _normalize_brand(_clean_text(brand, "Autres"))
        self.segment = _clean_text(segment, "autre")

    @property
    def dir(self) -> Path:
        return GUIDES_DIR / self.slug

    @property
    def vector_store_dir(self) -> Path:
        return self.dir / "vector_store"

    @property
    def is_indexed(self) -> bool:
        """Check if FAISS or BM25 index exists (cached after first check)."""
        cached = getattr(self, "_is_indexed_cache", None)
        if cached is not None:
            return cached
        faiss_ok = (self.vector_store_dir / "index.faiss").exists()
        bm25_ok = (self.vector_store_dir / "bm25_index.pkl").exists()
        result = faiss_ok or bm25_ok
        if result:
            self._is_indexed_cache = True
        return result

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "brand": self.brand,
            "image": self.image,
            "segment": self.segment,
            "indexed": self.is_indexed,
        }


class GuideManager:
    """Discover and manage pre-indexed guides."""

    def __init__(self):
        self.guides: Dict[str, Guide] = {}
        self._load_guides()

    def _load_guides(self):
        """Load guides from the guides directory manifest."""
        manifest_path = GUIDES_DIR / "manifest.json"
        if not manifest_path.exists():
            return

        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to load manifest.json: %s", exc)
            return

        if not isinstance(entries, list):
            log.error("Invalid manifest format: expected list, got %s", type(entries).__name__)
            return

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slug = _clean_text(entry.get("slug", ""))
            if not slug or not re.match(r"^[a-z0-9-]+$", slug):
                continue
            self.guides[slug] = Guide(
                slug=slug,
                name=_clean_text(entry.get("name"), slug),
                image=entry.get("image"),
                brand=entry.get("brand"),
                segment=entry.get("segment"),
            )

        log.info("GuideManager: %d guides loaded", len(self.guides))

    def list_guides(self, brand: Optional[str] = None) -> List[dict]:
        """Return all indexed guides as dicts."""
        normalized_brand = _clean_text(brand).lower()

        guides = []
        for guide in self.guides.values():
            if not guide.is_indexed:
                continue
            if normalized_brand and guide.brand.lower() != normalized_brand:
                continue
            guides.append(guide.to_dict())
        return guides

    def list_brands(self) -> List[str]:
        """Return available brands among indexed guides."""
        brands = {
            guide.brand
            for guide in self.guides.values()
            if guide.is_indexed and guide.brand
        }
        return sorted(brands, key=str.lower)

    def get_guide(self, slug: str) -> Optional[Guide]:
        return self.guides.get(slug)

    def reload(self):
        """Re-read from disk."""
        self.guides.clear()
        self._load_guides()


guide_manager = GuideManager()
