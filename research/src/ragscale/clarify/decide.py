"""Three-way decision for an incoming query: ANSWER, CLARIFY (with a question and options) or ABSTAIN.

Order of checks (cheap and deterministic first; mirrors the answer/clarify/abstain framing of
CRAG, Yan et al. 2024, and "Clarify, Abstain or Answer?", Baan et al. 2026):
  1. off-topic            -> abstain   (too few query words belong to the manuals' vocabulary)
  2. unknown brand named  -> abstain   (a car brand with no manual in the corpus)
  3. exactly one vehicle  -> answer    (search restricted to that vehicle's manuals)
  4. otherwise            -> clarify if the detector says the answer depends on the vehicle, else answer
The clarifying question asks the attribute that best splits the candidate vehicles, with options.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..corpus import Corpus
from ..retrievers.base import Query, Retriever
from ..text import content_tokens, normalize_for_match
from .labels import VehicleCatalog
from .signals import SignalExtractor
from .simulate import QUESTION_TEMPLATES, ClarificationSimulator, Detector

# Car brands without any manual in the corpus (FR/EN market). Brands present in the corpus are detected
# from the catalog, so this list only has to cover the absent ones.
ABSENT_BRANDS = frozenset(normalize_for_match(b) for b in """
Porsche|Skoda|Lexus|Mini|Smart|Lamborghini|Ferrari|Bentley|Rolls-Royce|Aston Martin|McLaren|Bugatti|Lotus|Infiniti|
Acura|Cadillac|Buick|GMC|Chrysler|Dodge|Ram|Lincoln|Rivian|Lucid|Polestar|BYD|MG|Lynk & Co|Isuzu|Daihatsu|SsangYong|
KGM|Saab|Rover|Talbot|Simca|Lada|Aiways|Xpeng|Nio|Ora|Leapmotor|Abarth|Iveco|Piaggio|Aixam|Ligier|Microcar|Chatenet""".replace("\n", "").split("|"))


@dataclass
class Decision:
    action: str                      # answer | clarify | abstain
    reason: str
    question: str = ""
    options: list[str] = field(default_factory=list)
    attribute: str = ""
    routed_manuals: list[str] = field(default_factory=list)
    p_needs_clarification: float | None = None
    top_manual: str = ""
    top_page: str = ""
    signals: dict[str, float] = field(default_factory=dict)


class ClarifyAgent:
    def __init__(self, corpus: Corpus, catalog: VehicleCatalog, retriever: Retriever, signals: SignalExtractor,
                 detector: Detector, threshold: float = 0.5, min_domain_coverage: float = 0.5, min_doc_freq: int = 30):
        self.corpus, self.catalog, self.detector, self.threshold = corpus, catalog, detector, threshold
        self.sim = ClarificationSimulator(corpus, catalog, retriever, signals)
        self.min_domain_coverage = min_domain_coverage
        self.vocabulary = self._domain_vocabulary(min_doc_freq)

    def _domain_vocabulary(self, min_doc_freq: int) -> set[str]:
        from collections import Counter

        df: Counter[str] = Counter()
        for text in self.corpus.chunks["text"]:
            df.update(set(content_tokens(text)))
        return {t for t, n in df.items() if n >= min_doc_freq}

    def domain_coverage(self, text: str) -> float:
        toks = content_tokens(text)
        return sum(t in self.vocabulary for t in toks) / len(toks) if toks else 0.0

    def decide(self, text: str, lang: str) -> Decision:
        q = Query("live", text, lang)
        norm = f" {normalize_for_match(text)} "
        coverage = self.domain_coverage(text)
        feats, dist, ranking = self.sim.observe(q, known="")
        routed = self.sim.signals.router.route(text)
        base = dict(signals={**feats, "domain_coverage": coverage}, routed_manuals=routed)
        if len(ranking.rows):
            top = int(ranking.rows[0])
            base.update(top_manual=str(self.corpus.chunks.at[top, "manual"]), top_page=str(self.corpus.chunks.at[top, "page_label"]))

        unknown = sorted(b for b in ABSENT_BRANDS if f" {b} " in norm)
        if unknown:
            return Decision("abstain", f"no manual for brand '{unknown[0]}'", **base)
        if coverage < self.min_domain_coverage and not routed and not feats["mentions_brand"]:
            return Decision("abstain", f"off-topic (domain coverage {coverage:.2f})", **base)
        p = self.detector.proba(feats)
        base["p_needs_clarification"] = p
        vehicles = sorted({self.catalog.vehicle_of(m) for m in routed})
        if len(vehicles) == 1:
            return Decision("answer", "one vehicle identified", **base)
        if len(vehicles) > 1:  # the named model exists in several versions: asking is one cheap question
            options = [self.catalog.vehicle_display[v]["full_display"] for v in vehicles][:4]
            return Decision("clarify", f"{len(vehicles)} versions match the name", question=QUESTION_TEMPLATES[lang]["full"],
                            options=options, attribute="full", **base)
        if p < self.threshold:
            return Decision("answer", f"answer does not seem vehicle-specific (p={p:.2f})", **base)
        brand = self._mentioned_brand(text)
        attr, options = self.sim.choose_attribute(dist, set(), 1 if brand else 0, brand=brand)
        return Decision("clarify", f"many candidate vehicles (p={p:.2f})", question=QUESTION_TEMPLATES[lang][attr],
                        options=options, attribute=attr, **base)

    def _mentioned_brand(self, text: str) -> str:
        q = set(normalize_for_match(text).split())
        for brand_key in {k["brand"] for k in self.catalog.vehicle_display.values()}:
            if brand_key and set(brand_key.split()) <= q:
                return brand_key
        return ""


def evaluate_examples(agent: ClarifyAgent, examples: list[dict]) -> list[dict]:
    rows = []
    for ex in examples:
        d = agent.decide(ex["query"], ex["lang"])
        manual_ok = None
        if d.action == "answer" and ex.get("expected_manual"):
            manual_ok = d.top_manual == ex["expected_manual"] or ex["expected_manual"] in d.routed_manuals
        rows.append({
            "id": ex["id"], "query": ex["query"], "expected": ex["expected"], "predicted": d.action,
            "correct_action": d.action == ex["expected"],
            "expected_attribute": ex.get("expected_attribute", ""), "asked_attribute": d.attribute,
            "question": d.question, "options": " | ".join(d.options), "reason": d.reason,
            "p_needs_clarification": None if d.p_needs_clarification is None else round(d.p_needs_clarification, 3),
            "top_manual": d.top_manual, "top_page": d.top_page, "manual_ok": manual_ok,
            "why_expected": ex["why"],
        })
    return rows
