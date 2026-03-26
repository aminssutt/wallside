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
    "\u00c3\u00a9": "\u00e9",
    "\u00c3\u00a8": "\u00e8",
    "\u00c3\u00aa": "\u00ea",
    "\u00c3\u00ab": "\u00eb",
    "\u00c3\u00a0": "\u00e0",
    "\u00c3\u00a2": "\u00e2",
    "\u00c3\u00a4": "\u00e4",
    "\u00c3\u00ae": "\u00ee",
    "\u00c3\u00af": "\u00ef",
    "\u00c3\u00b4": "\u00f4",
    "\u00c3\u00b6": "\u00f6",
    "\u00c3\u00b9": "\u00f9",
    "\u00c3\u00bb": "\u00fb",
    "\u00c3\u00bc": "\u00fc",
    "\u00c3\u00a7": "\u00e7",
    "\u00e3\u00a9": "\u00e9",
    "\u00e3\u00a8": "\u00e8",
    "\u00e3\u00aa": "\u00ea",
    "\u00e3\u00ab": "\u00eb",
    "\u00e3\u00a0": "\u00e0",
    "\u00e3\u00a2": "\u00e2",
    "\u00e3\u00a4": "\u00e4",
    "\u00e3\u00ae": "\u00ee",
    "\u00e3\u00af": "\u00ef",
    "\u00e3\u00b4": "\u00f4",
    "\u00e3\u00b6": "\u00f6",
    "\u00e3\u00b9": "\u00f9",
    "\u00e3\u00bb": "\u00fb",
    "\u00e3\u00bc": "\u00fc",
    "\u00e3\u00a7": "\u00e7",
}
_CANONICAL_BRANDS = {
    "bmw": "BMW",
    "alfa romeo": "Alfa Romeo",
    "alfa rom\u00e9o": "Alfa Romeo",
}
_MANUAL_SLUG_SUFFIXES = (
    "infotainment-system",
    "multimedia-system",
    "easy-link-multimedia",
    "mbux-multimedia",
    "quick-reference-guide",
    "navigation-manual",
    "owner-manual",
    "owners-manual",
    "owner-s-manual",
)
_MANUAL_NAME_PATTERNS = (
    r"\binfotainment\s*system\b",
    r"\bmultimedia\s*system\b",
    r"\beasy[- ]?link\s*multimedia\b",
    r"\bmbux\s*multimedia\b",
    r"\bquick\s*reference\s*guide\b",
    r"\bnavigation\s*manual\b",
    r"\bowner'?s?\s*manual\b",
)


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


def _strip_manual_suffix(slug: str) -> str:
    for suffix in _MANUAL_SLUG_SUFFIXES:
        token = f"-{suffix}"
        if slug.endswith(token):
            return slug[: -len(token)]
    return slug


def _is_vehicle_like_slug(slug: str) -> bool:
    parts = [p for p in slug.split("-") if p]
    if len(parts) >= 3:
        return True
    return any(any(ch.isdigit() for ch in part) for part in parts)


def _canonical_vehicle_slug(slug: str, known_slugs: set[str]) -> str:
    candidate = _strip_manual_suffix(slug)
    if candidate == slug:
        return slug
    if candidate in known_slugs:
        return candidate
    if _is_vehicle_like_slug(candidate):
        return candidate
    return slug


def _is_manual_specific_slug(slug: str) -> bool:
    return _strip_manual_suffix(slug) != slug


def _clean_vehicle_name(name: str) -> str:
    cleaned = _clean_text(name)
    for pattern in _MANUAL_NAME_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" -:|/")


class Guide:
    """Represents a vehicle-level guide built from one or multiple manuals."""

    def __init__(
        self,
        slug: str,
        name: str,
        image: Optional[str] = None,
        brand: Optional[str] = None,
        segment: Optional[str] = None,
        source_slugs: Optional[List[str]] = None,
    ):
        self.slug = slug
        self.name = _clean_text(name, slug)
        self.image = _clean_text(image) or None
        self.brand = _normalize_brand(_clean_text(brand, "Autres"))
        self.segment = _clean_text(segment, "autre")
        self.source_slugs = list(dict.fromkeys(source_slugs or [slug]))

    @property
    def dir(self) -> Path:
        return GUIDES_DIR / self.slug

    @property
    def vector_store_dir(self) -> Path:
        # Backward-compatible fallback: first manual vector store.
        return self.vector_store_dirs[0] if self.vector_store_dirs else self.dir / "vector_store"

    @property
    def vector_store_dirs(self) -> List[Path]:
        return [GUIDES_DIR / source_slug / "vector_store" for source_slug in self.source_slugs]

    @property
    def is_indexed(self) -> bool:
        """Check if at least one source manual index exists (cached after first check)."""
        cached = getattr(self, "_is_indexed_cache", None)
        if cached is not None:
            return cached

        for vector_dir in self.vector_store_dirs:
            faiss_ok = (vector_dir / "index.faiss").exists()
            bm25_ok = (vector_dir / "bm25_index.pkl").exists()
            if faiss_ok or bm25_ok:
                self._is_indexed_cache = True
                return True

        return False

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "brand": self.brand,
            "image": self.image,
            "segment": self.segment,
            "indexed": self.is_indexed,
            "manual_count": len(self.source_slugs),
            "source_slugs": self.source_slugs,
        }


class GuideManager:
    """Discover and manage pre-indexed guides."""

    def __init__(self):
        self.guides: Dict[str, Guide] = {}
        self.slug_aliases: Dict[str, str] = {}
        self._load_guides()

    def _entry_priority(self, entry: dict, canonical_slug: str) -> int:
        score = 0
        if entry.get("slug") == canonical_slug:
            score += 100
        if entry.get("image"):
            score += 20
        if entry.get("segment"):
            score += 10
        if not _is_manual_specific_slug(entry.get("slug", "")):
            score += 5
        return score

    def _load_guides(self):
        """Load guides from the guides directory manifest and group by vehicle."""
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

        normalized_entries: List[dict] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slug = _clean_text(entry.get("slug", ""))
            if not slug or not re.match(r"^[a-z0-9-]+$", slug):
                continue
            normalized_entries.append(
                {
                    "slug": slug,
                    "name": _clean_text(entry.get("name"), slug),
                    "image": _clean_text(entry.get("image")) or None,
                    "brand": _clean_text(entry.get("brand"), "Autres"),
                    "segment": _clean_text(entry.get("segment"), "autre"),
                }
            )

        known_slugs = {entry["slug"] for entry in normalized_entries}
        groups: Dict[str, List[dict]] = {}

        for entry in normalized_entries:
            source_slug = entry["slug"]
            canonical_slug = _canonical_vehicle_slug(source_slug, known_slugs)
            groups.setdefault(canonical_slug, []).append(entry)
            self.slug_aliases[source_slug] = canonical_slug

        for canonical_slug, group_entries in groups.items():
            ranked = sorted(
                group_entries,
                key=lambda entry: self._entry_priority(entry, canonical_slug),
                reverse=True,
            )
            primary = ranked[0]

            display_name = primary["name"]
            if primary["slug"] != canonical_slug:
                display_name = _clean_vehicle_name(display_name) or display_name

            source_slugs = [entry["slug"] for entry in ranked]
            self.slug_aliases[canonical_slug] = canonical_slug

            self.guides[canonical_slug] = Guide(
                slug=canonical_slug,
                name=display_name,
                image=primary.get("image"),
                brand=primary.get("brand"),
                segment=primary.get("segment"),
                source_slugs=source_slugs,
            )

        log.info(
            "GuideManager: %d manuals grouped into %d vehicle chats",
            len(normalized_entries),
            len(self.guides),
        )

    def list_guides(self, brand: Optional[str] = None) -> List[dict]:
        """Return all indexed vehicle guides as dicts."""
        normalized_brand = _clean_text(brand).lower()

        guides = []
        for guide in sorted(self.guides.values(), key=lambda g: g.name.lower()):
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
        canonical_slug = self.slug_aliases.get(slug, slug)
        return self.guides.get(canonical_slug)

    def reload(self):
        """Re-read from disk."""
        self.guides.clear()
        self.slug_aliases.clear()
        self._load_guides()


guide_manager = GuideManager()
