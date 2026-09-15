"""Retriever interface.

A retrieval *condition* is a (query, allowed-rows mask) pair: the same query is searched against many
sub-corpora (e.g. 5, 25, 165 manuals) by masking a single global index. Scoring retrievers score the
whole corpus once per query and take a top-k inside each mask, so adding corpus-size conditions is
almost free. For lexical retrieval this means collection statistics (IDF) come from the full corpus;
this is documented as a methodological choice in the protocol.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from ..corpus import Corpus


@dataclass(frozen=True)
class Query:
    qid: str
    text: str
    lang: str  # "fr" | "en"


@dataclass
class Ranking:
    rows: np.ndarray    # int64 corpus rows, best first
    scores: np.ndarray  # float32, same order


def topk_in_mask(scores: np.ndarray, mask: np.ndarray | None, k: int) -> Ranking:
    if mask is not None:
        scores = np.where(mask, scores, -np.inf)
    k = min(k, scores.shape[0])
    part = np.argpartition(-scores, k - 1)[:k]
    order = part[np.argsort(-scores[part], kind="stable")]
    keep = np.isfinite(scores[order])
    order = order[keep]
    return Ranking(order.astype(np.int64), scores[order].astype(np.float32))


class Retriever(ABC):
    name: str

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

    @abstractmethod
    def search(self, queries: list[Query], masks: list[list[np.ndarray | None]], k: int) -> list[list[Ranking]]:
        """For each query i and each mask j in masks[i], return the top-k Ranking."""


class ScoringRetriever(Retriever):
    """Retriever that can score every corpus row for a query."""

    batch_size = 32

    @abstractmethod
    def score_batch(self, queries: list[Query]) -> np.ndarray:
        """float32 [len(queries), n_rows] scores; higher is better."""

    def search(self, queries, masks, k):
        out: list[list[Ranking]] = []
        for start in range(0, len(queries), self.batch_size):
            batch = queries[start : start + self.batch_size]
            scores = self.score_batch(batch)
            for i in range(len(batch)):
                out.append([topk_in_mask(scores[i], m, k) for m in masks[start + i]])
        return out
