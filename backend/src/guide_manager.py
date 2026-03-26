"""
Guide manager for pre-indexed vehicle manuals.
Each guide lives under data/guides/<slug>/ with FAISS + BM25 indexes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR

GUIDES_DIR = DATA_DIR / "guides"
GUIDES_DIR.mkdir(parents=True, exist_ok=True)


def slugify(name: str) -> str:
    """Convert a guide name to a filesystem-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[àâä]", "a", s)
    s = re.sub(r"[éèêë]", "e", s)
    s = re.sub(r"[îï]", "i", s)
    s = re.sub(r"[ôö]", "o", s)
    s = re.sub(r"[ùûü]", "u", s)
    s = re.sub(r"[ç]", "c", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


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
        self.name = name
        self.image = image  # filename like "clio-4.png"
        self.brand = (brand or "").strip() or "Autres"
        self.segment = (segment or "").strip() or "autre"

    @property
    def dir(self) -> Path:
        return GUIDES_DIR / self.slug

    @property
    def vector_store_dir(self) -> Path:
        return self.dir / "vector_store"

    @property
    def is_indexed(self) -> bool:
        """Check if FAISS or BM25 index exists."""
        faiss_ok = (self.vector_store_dir / "index.faiss").exists()
        bm25_ok = (self.vector_store_dir / "bm25_index.pkl").exists()
        return faiss_ok or bm25_ok

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

        with manifest_path.open("r", encoding="utf-8") as f:
            entries = json.load(f)

        for entry in entries:
            slug = entry["slug"]
            self.guides[slug] = Guide(
                slug=slug,
                name=entry["name"],
                image=entry.get("image"),
                brand=entry.get("brand"),
                segment=entry.get("segment"),
            )

        print(f"GuideManager: {len(self.guides)} guides loaded")

    def list_guides(self, brand: Optional[str] = None) -> List[dict]:
        """Return all indexed guides as dicts."""
        normalized_brand = (brand or "").strip().lower()

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
