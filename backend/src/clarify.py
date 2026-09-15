"""Decide what to do with an incoming question before searching: answer, ask which vehicle, or abstain.

Measured on the research benchmark (research/): asking "which vehicle?" when the question names none
takes the right manual from 17% to 96% of questions, for 0.57 questions asked per query. Naming detection
alone drives the decision, so this module needs no index and no model - only the guide catalog.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Optional

from .guide_manager import guide_manager

# Vehicle-name words that describe the kind of manual rather than a model.
GENERIC_WORDS = frozenset(
    "infotainment system multimedia media nav navigation live guide quick reference manual owner owners "
    "easy link mbux carnet entretien et garanties toutes gen".split()
)
# Brand and model names that are also everyday FR/EN words: they only count when capitalized
# ("ma Seat Ibiza" yes, "my seat belt" no; "ranger le coffre" is not a Ford Ranger).
COMMON_WORDS = frozenset(
    "seat smart mini ram genesis alpine lotus jaguar ora nio rover ranger espace rafale focus swift partner "
    "spring leaf avenger puma panda jogger uno austral levante fiesta scenic civic colt mustang kangoo zoe "
    "leon ibiza tipo juke outback forester".split()
)
# Brands with no manual in the catalog: better to say so than to ask a question that leads nowhere.
ABSENT_BRANDS = frozenset(
    "porsche skoda lexus lamborghini ferrari bentley rolls royce aston martin mclaren bugatti infiniti acura "
    "cadillac buick gmc chrysler dodge lincoln rivian lucid polestar byd mg isuzu daihatsu ssangyong kgm saab "
    "talbot simca lada aiways xpeng leapmotor abarth iveco piaggio aixam ligier microcar chatenet".split()
)
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_PARENS_RE = re.compile(r"\([^)]*\)")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)

MAX_OPTIONS = 3


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def normalize(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(fold(text)))


def mentions(text: str, name_key: str) -> bool:
    """Is `name_key` (already normalized) mentioned in `text`? Everyday words need a capital letter."""
    if not name_key:
        return False
    if f" {name_key} " not in f" {normalize(text)} ":
        return False
    if not any(w in COMMON_WORDS for w in name_key.split()):
        return True
    words = _WORD_RE.findall(text)
    return any(fold(w) == name_key.split()[0] and w[:1].isupper() for w in words[1:])


@lru_cache(maxsize=1)
def vehicle_keys() -> List[Dict]:
    """One entry per vehicle chat: brand, model phrase, years and manual-kind words, all normalized."""
    keys = []
    for guide in guide_manager.guides.values():
        brand = normalize(guide.brand)
        name_words = normalize(guide.name).split()
        brand_words = set(brand.split())
        model_words = [
            w for w in normalize(_PARENS_RE.sub("", guide.name)).split()
            if w not in brand_words and w not in GENERIC_WORDS and not _YEAR_RE.match(w)
        ]
        model = " ".join(model_words)
        keys.append({
            "slug": guide.slug,
            "name": guide.name,
            "brand": brand,
            "brand_display": guide.brand,
            "model": model,
            # "Renault 5", "DS 4": a bare short number identifies the vehicle only with its brand.
            "needs_brand": len(model_words) == 1 and model_words[0].isdigit() and len(model_words[0]) <= 2,
            "years": {w for w in name_words if _YEAR_RE.match(w)},
            "generic_words": {w for w in name_words if w in GENERIC_WORDS},
        })
    return keys


def route(text: str) -> List[Dict]:
    """Vehicles named in the question, best match first (empty when the question names none)."""
    padded = f" {normalize(text)} "
    tokens = set(padded.split())
    best: List[Dict] = []
    best_score = 0.0
    for key in vehicle_keys():
        has_brand = bool(key["brand"]) and mentions(text, key["brand"])
        if key["model"]:
            # The model must appear as a contiguous phrase: "classe a" must not match "classe c ... a".
            if f" {key['model']} " not in padded or (key["needs_brand"] and not has_brand):
                continue
            if any(w in COMMON_WORDS for w in key["model"].split()) and not has_brand and not mentions(text, key["model"]):
                continue
            score = (len(key["model"].split()) + 0.5 * has_brand + 0.25 * len(key["years"] & tokens)
                     + 0.1 * len(key["generic_words"] & tokens))
        elif has_brand and key["generic_words"] & tokens:
            score = 0.5 + 0.1 * len(key["generic_words"] & tokens)
        else:
            continue
        if score > best_score + 1e-9:
            best, best_score = [key], score
        elif abs(score - best_score) <= 1e-9:
            best.append(key)
    return best


def mentioned_brand(text: str) -> str:
    """Normalized brand of the catalog mentioned in the question, longest name first ("alfa romeo")."""
    brands = sorted({k["brand"] for k in vehicle_keys() if k["brand"]}, key=len, reverse=True)
    for brand in brands:
        if mentions(text, brand):
            return brand
    return ""


def absent_brand(text: str) -> str:
    for brand in sorted(ABSENT_BRANDS, key=len, reverse=True):
        if mentions(text, brand):
            return brand
    return ""


def _options(brand: str, exclude: Optional[set] = None) -> List[Dict]:
    """Vehicles offered as quick answers: those of the mentioned brand, otherwise none (the UI searches)."""
    if not brand:
        return []
    picks = [k for k in vehicle_keys() if k["brand"] == brand and k["slug"] not in (exclude or set())]
    picks.sort(key=lambda k: k["name"])
    return [{"slug": k["slug"], "name": k["name"], "brand": k["brand_display"]} for k in picks[:MAX_OPTIONS]]


def decide(message: str, lang: str = "fr") -> Dict:
    """answer | clarify | abstain, with the vehicle(s) involved.

    Returned keys: action, reason, vehicle (answer), options (clarify), brand (clarify), message keys for i18n.
    """
    text = (message or "").strip()
    missing = absent_brand(text)
    if missing:
        return {"action": "abstain", "reason": "brand_not_in_catalog", "brand": missing.title(), "options": []}

    named = route(text)
    if len(named) == 1:
        v = named[0]
        return {"action": "answer", "reason": "vehicle_named", "vehicle": {"slug": v["slug"], "name": v["name"]}, "options": []}
    if len(named) > 1:
        return {
            "action": "clarify", "reason": "several_versions", "brand": named[0]["brand_display"],
            "options": [{"slug": k["slug"], "name": k["name"], "brand": k["brand_display"]} for k in named[:MAX_OPTIONS]],
        }

    brand = mentioned_brand(text)
    return {
        "action": "clarify",
        "reason": "brand_only" if brand else "no_vehicle",
        "brand": next((k["brand_display"] for k in vehicle_keys() if k["brand"] == brand), "") if brand else "",
        "options": _options(brand),
    }
