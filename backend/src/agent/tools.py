"""Agent tool data types and localisation helpers.

Historically this module hosted the tool dispatchers (manual/web/youtube)
behind a ``run_tools_in_parallel`` ThreadPoolExecutor. That implementation
has been replaced by the asyncio pipeline in ``async_pipeline.py``; only
the data classes and the language / brand-to-domain lookup tables remain.
They are imported by the async pipeline and re-exported through the
package ``__init__``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Localisation + official-domain boost
# ---------------------------------------------------------------------------

# Language -> DDGS region. ``wt-wt`` means worldwide (no bias), which we keep
# as a sane fallback so niche languages still reach global content.
_LANG_TO_REGION: Dict[str, str] = {
    "fr": "fr-fr",
    "en": "us-en",
    "ko": "kr-kr",
    "de": "de-de",
    "es": "es-es",
    "it": "it-it",
}


def _region_for_lang(lang: Optional[str]) -> str:
    if not lang:
        return "wt-wt"
    return _LANG_TO_REGION.get(lang.lower().strip(), "wt-wt")


# Best-effort mapping from a guide's brand slug to official manufacturer
# domains. When a match exists, the web search fires an additional
# ``site:<domain>`` query sequence after the planner's generic query so
# answers get anchored on official sources (audi.fr, bmw.com, hyundai.co.kr,
# ...) instead of random aggregators.
_OFFICIAL_DOMAINS: Dict[str, List[str]] = {
    "alfa-romeo": ["alfaromeo.com", "alfaromeo.fr", "alfaromeousa.com"],
    "alpine": ["alpinecars.com", "alpine.cars"],
    "audi": ["audi.com", "audi.fr", "audiusa.com", "audi.co.uk", "audi.co.kr"],
    "bmw": ["bmw.com", "bmw.fr", "bmwusa.com", "bmw.co.uk", "bmw.co.kr"],
    "chevrolet": ["chevrolet.com", "chevrolet.fr", "chevrolet.co.kr"],
    "citroen": ["citroen.com", "citroen.fr", "citroen.co.uk"],
    "cupra": ["cupraofficial.com", "cupraofficial.fr"],
    "dacia": ["dacia.com", "dacia.fr", "dacia.co.uk"],
    "ds": ["dsautomobiles.com", "dsautomobiles.fr"],
    "fiat": ["fiat.com", "fiat.fr", "fiatusa.com"],
    "ford": ["ford.com", "ford.fr", "ford.co.uk"],
    "genesis": ["genesis.com", "genesis.fr", "genesis.co.kr"],
    "honda": ["honda.com", "honda.fr", "honda.co.uk", "honda.co.kr"],
    "hyundai": ["hyundai.com", "hyundai.fr", "hyundai.co.kr", "hyundaiusa.com"],
    "jaguar": ["jaguar.com", "jaguar.fr", "jaguar.co.uk"],
    "jeep": ["jeep.com", "jeep.fr"],
    "kia": ["kia.com", "kia.fr", "kia.com/us", "kia.com/kr"],
    "land-rover": ["landrover.com", "landrover.fr", "landrover.co.uk"],
    "lexus": ["lexus.com", "lexus.fr", "lexus.eu", "lexus.co.kr"],
    "maserati": ["maserati.com", "maserati.fr"],
    "mazda": ["mazda.com", "mazda.fr", "mazdausa.com"],
    "mercedes": ["mercedes-benz.com", "mercedes-benz.fr", "mbusa.com"],
    "mini": ["mini.com", "mini.fr", "miniusa.com"],
    "mitsubishi": ["mitsubishi-motors.com", "mitsubishi-motors.fr"],
    "nissan": ["nissan.com", "nissan.fr", "nissanusa.com", "nissan.co.uk"],
    "opel": ["opel.com", "opel.fr"],
    "peugeot": ["peugeot.com", "peugeot.fr"],
    "renault": ["renault.com", "renault.fr", "renault.co.uk"],
    "seat": ["seat.com", "seat.fr"],
    "skoda": ["skoda.com", "skoda.fr", "skoda-auto.com"],
    "subaru": ["subaru.com", "subaru.fr", "subaru-global.com"],
    "suzuki": ["suzuki.com", "suzuki.fr", "globalsuzuki.com"],
    "tesla": ["tesla.com", "tesla.com/fr", "tesla.com/ko_kr"],
    "toyota": ["toyota.com", "toyota.fr", "toyota.co.uk", "toyota.co.kr"],
    "volkswagen": ["volkswagen.com", "volkswagen.fr", "vw.com"],
    "volvo": ["volvocars.com", "volvocars.fr"],
}


def _slugify_brand(brand: str) -> str:
    """Cheap slug for dict lookup. Matches the keys above."""
    text = (brand or "").strip().lower()
    for ch in (" ", "_", "."):
        text = text.replace(ch, "-")
    return "".join(c for c in text if c.isalpha() or c == "-")


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """Single citation that the responder can render in the Sources block."""

    kind: str            # "manual" | "web" | "youtube"
    label: str           # Human-readable label
    url: str = ""        # Optional URL (web / youtube)
    source_file: str = ""  # Manual file name (manual only)
    page: str = ""       # Manual page (manual only)


@dataclass
class ToolResult:
    """Uniform envelope returned by every tool."""

    name: str
    ok: bool
    summary: str                              # Natural-language summary for the responder
    payload: Dict[str, Any] = field(default_factory=dict)
    citations: List[Citation] = field(default_factory=list)
    error: str = ""

    def to_llm_content(self) -> Dict[str, Any]:
        """Serialise for a ``function_response`` turn when needed."""
        return {
            "ok": self.ok,
            "summary": self.summary,
            "used_citations": [c.__dict__ for c in self.citations],
        }


@dataclass
class ToolCall:
    """Tool invocation requested by the planner."""

    name: str
    args: Dict[str, Any]


__all__ = [
    "Citation",
    "ToolCall",
    "ToolResult",
    "_LANG_TO_REGION",
    "_OFFICIAL_DOMAINS",
    "_region_for_lang",
    "_slugify_brand",
]
