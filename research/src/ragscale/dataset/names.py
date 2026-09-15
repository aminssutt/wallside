"""Vehicle name forms used to build query variants with different levels of document identification."""
from __future__ import annotations

import re

from ..text import fold

_PARENS_RE = re.compile(r"\([^)]*\)")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\+?\b")
_MANUAL_WORDS_RE = re.compile(
    r"\b(infotainment system|multimedia system|easy link multimedia|mbux multimedia|quick reference guide|"
    r"navigation manual|media nav live guide|carnet entretien et garanties)\b",
    re.IGNORECASE,
)


def name_forms(name: str, brand: str) -> dict[str, str]:
    """full: 'Peugeot 208 (2023)'; model: '208'; brand: 'Peugeot'."""
    full = re.sub(r"\s+", " ", name).strip()
    brand_tokens = fold(brand).replace("-", " ").split()
    words = _MANUAL_WORDS_RE.sub("", _PARENS_RE.sub("", full)).split()
    # Drop leading brand words ("Mercedes Classe A" for brand "Mercedes-Benz"; "Range Rover" stays for "Land Rover").
    while words and fold(words[0]) in brand_tokens:
        words = words[1:]
    # Years are dropped unless they are the model itself ("Peugeot 2008").
    without_years = [w for w in words if not _YEAR_RE.fullmatch(w)]
    words = without_years or words
    model = " ".join(words).strip(" -")
    if not model:
        model = full
    elif model.isdigit() and len(model) <= 2:  # "Renault 5", "DS 4": the bare digit is not a usable name
        model = f"{brand.strip()} {model}"
    return {"full": full, "model": model, "brand": brand.strip()}


def fill(template: str, vehicle: str) -> str:
    return re.sub(r"\s+", " ", template.replace("{VEHICLE}", vehicle)).strip()
