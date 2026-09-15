"""Retrieval scopes: which manuals a query is searched against.

- manual:  only the gold manual (upper bound for passage retrieval)
- vehicle: every manual of the gold vehicle (what the Wallside app does after the user picks a car)
- global:  all 165 manuals (the chatbot must find the right document by itself)
- tier N:  the gold manual + N-1 distractor manuals, nested across N for a given seed so that accuracy
           curves are monotone in expectation:
             random -> distractors drawn uniformly
             hard   -> same-brand manuals first, then manuals whose mean embedding is closest to the gold's
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np

from ..corpus import Corpus

DEFAULT_TIERS = (1, 2, 5, 10, 20, 50, 100, 165)


@dataclass(frozen=True)
class Scope:
    kind: str           # manual | vehicle | global | tier
    n_manuals: int = 0  # tier size (0 for non-tier scopes)
    strategy: str = ""  # random | hard
    seed: int = -1

    @property
    def label(self) -> str:
        if self.kind != "tier":
            return self.kind
        return f"tier{self.n_manuals}-{self.strategy}-s{self.seed}"


class ScopeBuilder:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self.manuals = corpus.manual_ids

    @cached_property
    def centroid_similarity(self) -> np.ndarray:
        """[n_manuals, n_manuals] cosine similarity of mean gemini chunk embeddings."""
        emb = self.corpus.load_embeddings()
        idx = self.corpus.row_manual_idx
        cents = np.zeros((len(self.manuals), emb.shape[1]), dtype=np.float32)
        for m in range(len(self.manuals)):
            cents[m] = np.asarray(emb[idx == m], dtype=np.float32).mean(axis=0)
        cents /= np.linalg.norm(cents, axis=1, keepdims=True)
        return cents @ cents.T

    def distractor_order(self, gold: str, strategy: str, seed: int) -> list[str]:
        rng = np.random.default_rng([seed, self.corpus.manual_index[gold]])
        others = [m for m in self.manuals if m != gold]
        if strategy == "random":
            return [others[i] for i in rng.permutation(len(others))]
        if strategy == "hard":
            meta = self.corpus.manual_meta
            gi = self.corpus.manual_index[gold]
            sim = self.centroid_similarity[gi]
            same_brand = [m for m in others if meta[m]["brand_key"] == meta[gold]["brand_key"]]
            rest = [m for m in others if m not in set(same_brand)]
            same_brand = [same_brand[i] for i in rng.permutation(len(same_brand))]
            rest.sort(key=lambda m: -sim[self.corpus.manual_index[m]])
            return same_brand + rest
        raise ValueError(strategy)

    def manuals_for(self, scope: Scope, gold: str) -> list[str]:
        if scope.kind == "manual":
            return [gold]
        if scope.kind == "vehicle":
            vehicle = self.corpus.manual_meta[gold]["vehicle"]
            return [m for m in self.manuals if self.corpus.manual_meta[m]["vehicle"] == vehicle]
        if scope.kind == "global":
            return list(self.manuals)
        if scope.kind == "tier":
            return [gold] + self.distractor_order(gold, scope.strategy, scope.seed)[: scope.n_manuals - 1]
        raise ValueError(scope.kind)

    def mask(self, scope: Scope, gold: str) -> np.ndarray | None:
        if scope.kind == "global" or (scope.kind == "tier" and scope.n_manuals >= len(self.manuals)):
            return None
        return self.corpus.mask_for_manuals(self.manuals_for(scope, gold))


def tier_scopes(tiers=DEFAULT_TIERS, strategies=("random", "hard"), seeds=range(5)) -> list[Scope]:
    return [Scope("tier", n, s, seed) for s in strategies for n in tiers for seed in seeds]
