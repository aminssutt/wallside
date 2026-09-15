"""Model-free signals of document-level underspecification, computed from the query and a first-stage retrieval.

Retrieval-distribution signals are query-performance-prediction style features lifted from chunks to
vehicles: if the best evidence is spread over many vehicles with similar scores, the query probably does
not identify its document. The passage-agreement signal separates the two reasons for such a spread:
different vehicles saying the same thing (generic answer, no need to ask) vs saying different things.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from ..corpus import Corpus
from ..retrievers.base import Query, Ranking
from ..retrievers.composite import NameRouter
from ..text import content_tokens, mentions_name
from .labels import VehicleCatalog

FEATURES = [
    "router_n_vehicles",     # vehicles whose name appears in the query (0 = none named)
    "router_unique",         # exactly one vehicle named
    "mentions_brand",        # a brand name appears in the query
    "vehicle_entropy",       # normalized entropy of retrieval mass over vehicles
    "top1_vehicle_share",    # retrieval mass of the best vehicle
    "vehicle_margin",        # (best - second) / best vehicle mass
    "n_vehicles_top10",      # distinct vehicles among the 10 best chunks
    "n_brands_top10",        # distinct brands among the 10 best chunks
    "passage_agreement",     # mean cosine between the best passages of the top-5 vehicles
    "query_tokens",          # content tokens in the query
]
RRF_K = 60


class SignalExtractor:
    def __init__(self, corpus: Corpus, catalog: VehicleCatalog, doc_vectors: np.ndarray | None = None):
        self.corpus, self.catalog = corpus, catalog
        self.router = NameRouter(corpus, base=_NoRetrieval())
        self.row_vehicle = np.array([catalog.vehicle_of(m) for m in corpus.chunks["manual"]])
        self.row_brand = np.array([catalog.manual_keys[m]["brand"] for m in corpus.chunks["manual"]])
        self.brand_tokens = {b: set(b.split()) for b in set(self.row_brand) if b}
        self.doc_vectors = doc_vectors if doc_vectors is not None else corpus.load_embeddings()

    def vehicle_distribution(self, ranking: Ranking) -> list[tuple[str, float]]:
        mass: dict[str, float] = defaultdict(float)
        for rank, row in enumerate(ranking.rows):
            mass[self.row_vehicle[row]] += 1.0 / (RRF_K + rank + 1)
        total = sum(mass.values()) or 1.0
        return sorted(((v, s / total) for v, s in mass.items()), key=lambda kv: -kv[1])

    def extract(self, query: Query, ranking: Ranking) -> dict[str, float]:
        routed = self.router.route(query.text)
        routed_vehicles = {self.catalog.vehicle_of(m) for m in routed}
        dist = self.vehicle_distribution(ranking)
        probs = np.array([p for _, p in dist]) if dist else np.array([1.0])
        entropy = float(-(probs * np.log(probs)).sum() / math.log(len(probs))) if len(probs) > 1 else 0.0
        top10 = ranking.rows[:10]

        best_rows = {}
        for row in ranking.rows:
            v = self.row_vehicle[row]
            if v not in best_rows:
                best_rows[v] = row
            if len(best_rows) == 5:
                break
        agreement = 1.0
        if len(best_rows) > 1:
            vecs = np.asarray(self.doc_vectors[list(best_rows.values())], dtype=np.float32)
            sims = vecs @ vecs.T
            n = len(vecs)
            agreement = float((sims.sum() - n) / (n * (n - 1)))

        return {
            "router_n_vehicles": float(len(routed_vehicles)),
            "router_unique": float(len(routed_vehicles) == 1),
            "mentions_brand": float(any(mentions_name(query.text, b) for b in self.brand_tokens)),
            "vehicle_entropy": entropy,
            "top1_vehicle_share": float(probs[0]),
            "vehicle_margin": float((probs[0] - probs[1]) / probs[0]) if len(probs) > 1 else 1.0,
            "n_vehicles_top10": float(len(set(self.row_vehicle[top10]))),
            "n_brands_top10": float(len(set(self.row_brand[top10]))),
            "passage_agreement": agreement,
            "query_tokens": float(len(content_tokens(query.text))),
        }


class _NoRetrieval:
    name = "none"
