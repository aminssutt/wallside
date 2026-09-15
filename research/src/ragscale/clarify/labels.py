"""Gold labels for document-level underspecification.

A query is *underspecified* when the information it contains still leaves several vehicles possible.
It *needs clarification* when, in addition, the answer depends on the vehicle: "how do I fasten the seat
belt?" is generic (answer without asking), "where is the 12 V battery?" is not.

Candidate vehicles are derived from what the query variant reveals about the gold manual:
  plain  -> nothing              -> every vehicle            (ambiguity type: vehicle)
  brand  -> "Peugeot"            -> vehicles of that brand   (ambiguity type: model)
  model  -> "208", "Civic"       -> vehicles with that model (ambiguity type: version, e.g. Civic 1972-2021 vs 2022-2025)
  full   -> "Peugeot 508 (2019)" -> vehicles with that name  (ambiguity type: version; two 508 manuals share it)
Manuals of the same vehicle (owner's manual + infotainment guide) count as one vehicle: the system can
search both without asking.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from ..corpus import Corpus
from ..dataset.names import name_forms
from ..text import normalize_for_match

AMBIGUITY_BY_FORM = {"plain": "vehicle", "brand": "model", "model": "version", "full": "version"}


@dataclass(frozen=True)
class ClarificationLabel:
    qid: str
    variant: str
    candidate_vehicles: tuple[str, ...]
    ambiguity_type: str        # none | vehicle | model | version
    answer_depends_on_vehicle: bool
    needs_clarification: bool


class VehicleCatalog:
    """Vehicle-level view of the corpus: brand, model and full-name keys per vehicle."""

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

    @cached_property
    def manual_keys(self) -> dict[str, dict[str, str]]:
        keys = {}
        for m, meta in self.corpus.manual_meta.items():
            forms = name_forms(meta["name"], meta["brand"])
            keys[m] = {
                "vehicle": meta["vehicle"],
                "brand": meta["brand_key"],
                "model": normalize_for_match(forms["model"]),
                "full": normalize_for_match(forms["full"]),
                "brand_display": meta["brand"],
                "model_display": forms["model"],
                "full_display": forms["full"],
            }
        return keys

    @cached_property
    def vehicles(self) -> list[str]:
        return sorted({k["vehicle"] for k in self.manual_keys.values()})

    def vehicle_of(self, manual: str) -> str:
        return self.manual_keys[manual]["vehicle"]

    def candidates(self, gold_manual: str, form: str) -> tuple[str, ...]:
        if form == "plain":
            return tuple(self.vehicles)
        gold = self.manual_keys[gold_manual]
        return tuple(sorted({k["vehicle"] for k in self.manual_keys.values() if k[form] == gold[form]}))

    @cached_property
    def vehicle_display(self) -> dict[str, dict[str, str]]:
        """Display names of a vehicle, taken from its owner's manual (the manual whose slug is the vehicle slug)."""
        out: dict[str, dict[str, str]] = {}
        for m, k in sorted(self.manual_keys.items(), key=lambda kv: kv[0] != kv[1]["vehicle"]):
            out.setdefault(k["vehicle"], k)
        return out


def label_query(catalog: VehicleCatalog, record: dict, variant: str) -> ClarificationLabel:
    form = variant.split("_", 1)[1]
    cands = catalog.candidates(record["manual"], form)
    depends = record["specificity"] == "vehicle_specific"
    ambiguous = len(cands) > 1
    return ClarificationLabel(
        qid=record["qid"],
        variant=variant,
        candidate_vehicles=cands,
        ambiguity_type=AMBIGUITY_BY_FORM[form] if ambiguous else "none",
        answer_depends_on_vehicle=depends,
        needs_clarification=ambiguous and depends,
    )
