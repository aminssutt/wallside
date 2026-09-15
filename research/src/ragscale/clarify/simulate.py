"""Clarification dialogues with a simulated user.

At each turn a *policy* decides whether to ask. If it asks, the system picks the vehicle attribute
(brand -> model -> version) that best splits its current candidate vehicles (largest entropy of retrieval
mass over the attribute's values, Aliannejadi et al. 2019 / information-gain style question selection),
renders a clarifying question with the top options, and a simulated user answers truthfully with the gold
vehicle's value for that attribute. The answer is appended to the query and retrieval is run again.

Policies:
  never       answer immediately (current chatbot behaviour in global search)
  always      ask at least once, then keep asking while the vehicle is not uniquely named
  name_rule   ask while the query does not name exactly one vehicle
  classifier  ask while P(needs clarification | signals) >= threshold (logistic regression trained on dev)
  oracle      ask exactly when the gold label says the current query needs clarification
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..corpus import Corpus
from ..metrics import Gold, query_metrics
from ..retrievers.base import Query, Ranking, Retriever
from .labels import VehicleCatalog
from .signals import FEATURES, SignalExtractor

ATTRIBUTES = ("brand", "model", "full")  # asked in this order of generality
FORM_LEVEL = {"plain": 0, "brand": 1, "model": 2, "full": 3}
QUESTION_TEMPLATES = {
    "fr": {"brand": "De quelle marque est votre véhicule ?", "model": "Quel modèle exactement ?",
           "full": "Quel est votre véhicule exactement (modèle et année) ?"},
    "en": {"brand": "Which brand is your vehicle?", "model": "Which model exactly?",
           "full": "Which vehicle exactly (model and year)?"},
}
ANSWER_PREFIX = {"fr": "Véhicule : ", "en": "Vehicle: "}


@dataclass
class Turn:
    question: str
    options: list[str]
    attribute: str
    user_answer: str
    signals: dict[str, float]
    p_needs: float | None


@dataclass
class Dialogue:
    qid: str
    variant: str
    policy: str
    initial_query: str
    final_query: str
    turns: list[Turn] = field(default_factory=list)
    first_turn_asked: bool = False
    gold_needs_clarification: bool = False
    metrics: dict[str, float] = field(default_factory=dict)
    top_manual: str = ""
    top_page: str = ""


class Detector:
    """Logistic regression over FEATURES (standardized), class-balanced."""

    def __init__(self):
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        self.model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=2000))

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Detector":
        self.model.fit(X, y)
        return self

    def proba(self, feats: dict[str, float]) -> float:
        return float(self.model.predict_proba(np.array([[feats[f] for f in FEATURES]]))[0, 1])

    def coefficients(self) -> dict[str, float]:
        lr = self.model[-1]
        return dict(zip(FEATURES, lr.coef_[0].round(3).tolist()))


class ClarificationSimulator:
    def __init__(self, corpus: Corpus, catalog: VehicleCatalog, retriever: Retriever,
                 signals: SignalExtractor, max_turns: int = 3, depth: int = 100, question_strategy: str = "direct"):
        if question_strategy not in ("direct", "hierarchical", "max_entropy"):
            raise ValueError(question_strategy)
        self.question_strategy = question_strategy
        self.corpus, self.catalog = corpus, catalog
        self.retriever = retriever
        self.signals, self.max_turns, self.depth = signals, max_turns, depth
        ch = corpus.chunks
        self._page_start = ch["page_start"].fillna(-1).to_numpy(np.int64)
        self._page_end = ch["page_end"].fillna(-1).to_numpy(np.int64)
        self._manual_vehicle = [corpus.manual_meta[m]["vehicle"] for m in corpus.manual_ids]
        self._manual_brand = [corpus.manual_meta[m]["brand_key"] for m in corpus.manual_ids]
        self._cache: dict = {}

    # ----------------------------------------------------------------- helpers
    def observe(self, question: Query, known: str) -> tuple[dict[str, float], list[tuple[str, float]], Ranking]:
        """Retrieve for the ORIGINAL question, restricted to the manuals named so far (question + user answers).

        User answers act as a metadata filter, not as extra query words: appending "Vehicle: Peugeot" to
        the text measurably hurt lexical passage retrieval in development runs."""
        key = (question.text, question.lang, known)
        if key not in self._cache:
            routing = Query(question.qid, f"{question.text} {known}".strip(), question.lang)
            manuals = self.signals.router.route(routing.text)
            mask = self.corpus.mask_for_manuals(manuals) if manuals else None
            search_q = Query(question.qid, self.signals.router.strip_names(question.text, manuals), question.lang) if manuals else question
            ranking = self.retriever.search([search_q], [[mask]], self.depth)[0][0]
            self._cache[key] = (self.signals.extract(routing, ranking), self.signals.vehicle_distribution(ranking), ranking)
        return self._cache[key]

    def choose_attribute(self, dist: list[tuple[str, float]], asked: set[str], known_level: int,
                         brand: str = "") -> tuple[str, list[str]]:
        """Pick what to ask and which options to show, following `self.question_strategy`:
          direct        ask for the vehicle itself; options = the 3 most likely vehicles (one question)
          hierarchical  the coarsest attribute that still splits the candidates (brand -> model -> version)
          max_entropy   the attribute whose values carry the most retrieval-mass entropy
        Candidates are the top vehicles of the retrieval, restricted to the brand the user already gave."""
        top = [(v, p) for v, p in dist if not brand or self.catalog.vehicle_display[v]["brand"] == brand][:10] or dist[:10]
        open_attrs = [a for lvl, a in enumerate(ATTRIBUTES, start=1) if a not in asked and lvl > known_level]
        if not open_attrs:
            open_attrs = [a for a in ATTRIBUTES if a not in asked] or ["full"]

        def split(attr: str) -> tuple[float, list[str]]:
            mass: dict[str, float] = defaultdict(float)
            for v, p in top:
                mass[self.catalog.vehicle_display[v][f"{attr}_display"]] += p
            total = sum(mass.values()) or 1.0
            h = -sum((m / total) * math.log(m / total) for m in mass.values() if m > 0)
            options = [k for k, _ in sorted(mass.items(), key=lambda kv: -kv[1])[:3]]
            if brand and len(options) < 3:  # few retrieved vehicles of that brand: complete from the catalog
                for k in sorted(self.catalog.vehicle_display.values(), key=lambda k: k["full_display"]):
                    if k["brand"] == brand and k[f"{attr}_display"] not in options:
                        options.append(k[f"{attr}_display"])
                    if len(options) == 3:
                        break
            return h, options

        if self.question_strategy == "direct":
            return "full", split("full")[1]
        if self.question_strategy == "hierarchical":
            for attr in open_attrs:
                h, opts = split(attr)
                if h > 1e-9:
                    return attr, opts
            return open_attrs[-1], split(open_attrs[-1])[1]
        best = max(open_attrs, key=lambda a: split(a)[0])
        return best, split(best)[1]

    def user_answer(self, gold_manual: str, attribute: str) -> str:
        keys = self.catalog.vehicle_display[self.catalog.vehicle_of(gold_manual)]
        if attribute == "brand":
            return keys["brand_display"]
        if attribute == "model":
            return f"{keys['brand_display']} {keys['model_display']}".strip()
        return keys["full_display"]

    def gold_needs(self, record: dict, level: int) -> bool:
        form = [f for f, lv in FORM_LEVEL.items() if lv == level][0]
        return len(self.catalog.candidates(record["manual"], form)) > 1 and record["specificity"] == "vehicle_specific"

    # ---------------------------------------------------------------- dialogue
    def run(self, record: dict, variant: str, query: Query, gold: Gold, policy: str,
            detector: Detector | None = None, threshold: float = 0.5) -> Dialogue:
        lang = query.lang
        form = variant.split("_", 1)[1]
        level = FORM_LEVEL[form]
        dlg = Dialogue(record["qid"], variant, policy if policy != "classifier" else f"classifier@{threshold:g}",
                       query.text, query.text, gold_needs_clarification=self.gold_needs(record, level))
        asked: set[str] = set()
        known = ""
        for turn in range(self.max_turns + 1):
            feats, dist, ranking = self.observe(query, known)
            p = detector.proba(feats) if detector is not None else None
            if policy == "never":
                ask = False
            elif policy == "always":
                ask = turn == 0 or feats["router_unique"] == 0
            elif policy == "name_rule":
                ask = feats["router_unique"] == 0
            elif policy == "classifier":
                ask = p is not None and p >= threshold
            elif policy == "oracle":
                ask = self.gold_needs(record, level)
            else:
                raise ValueError(policy)
            if turn == 0:
                dlg.first_turn_asked = ask
            if not ask or turn == self.max_turns or len(asked) == len(ATTRIBUTES):
                break
            brand_known = self.catalog.vehicle_display[self.catalog.vehicle_of(record["manual"])]["brand"] if level >= 1 else ""
            attr, options = self.choose_attribute(dist, asked, level, brand=brand_known)
            answer = self.user_answer(record["manual"], attr)
            dlg.turns.append(Turn(QUESTION_TEMPLATES[lang][attr], options, attr, answer, feats, p))
            asked.add(attr)
            level = max(level, ATTRIBUTES.index(attr) + 1)
            known = answer  # the most specific answer subsumes the previous ones
        dlg.final_query = f"{query.text} [{ANSWER_PREFIX[lang]}{known}]" if known else query.text
        ranking = Ranking(ranking.rows[:20], ranking.scores[:20])
        m = query_metrics(ranking.rows, gold, self.corpus.row_manual_idx, self._page_start, self._page_end,
                          self._manual_vehicle, self._manual_brand)
        dlg.metrics = {k: m[k] for k in ("doc_hit@1", "chunk_hit@5", "chunk_hit@5_lenient", "page_hit@5",
                                          "confusion_same_brand", "confusion_other_brand")}
        dlg.metrics["answer_found@5"] = max(m["chunk_hit@5_lenient"],
                                            self._semantic_hit(ranking.rows[:5], record) if record["specificity"] == "generic" else 0.0)
        if len(ranking.rows):
            top = int(ranking.rows[0])
            dlg.top_manual = str(self.corpus.chunks.at[top, "manual"])
            dlg.top_page = str(self.corpus.chunks.at[top, "page_label"])
        return dlg

    # gemini-embedding-001 cosine, measured on the corpus: random pairs median 0.75, adjacent chunks of the same
    # manual median 0.90 (p90 0.95), identical text ~1.0. 0.95 = "says the same thing", above most neighbours.
    SEMANTIC_MATCH = 0.95

    def _semantic_hit(self, rows: np.ndarray, record: dict) -> float:
        """Generic questions: a passage of another vehicle saying the same thing also answers the question."""
        if not len(rows):
            return 0.0
        vecs = np.asarray(self.signals.doc_vectors[list(rows)], dtype=np.float32)
        src = np.asarray(self.signals.doc_vectors[record["source_row"]], dtype=np.float32)
        return float((vecs @ src >= self.SEMANTIC_MATCH).any())

