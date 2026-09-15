"""Retrievers built on top of other retrievers: fusion, routing, name boosting."""
from __future__ import annotations

from functools import cached_property

import numpy as np

from ..corpus import Corpus
from ..dataset.names import name_forms
from ..text import normalize_for_match
from .base import Query, Ranking, Retriever, ScoringRetriever, topk_in_mask


class RRFFusion(Retriever):
    """Reciprocal Rank Fusion (Cormack et al., 2009) of component rankings computed inside the same mask."""

    def __init__(self, corpus: Corpus, components: list[Retriever], k_rrf: int = 60, depth: int = 100,
                 weights: list[float] | None = None):
        super().__init__(corpus)
        self.components = components
        self.k_rrf, self.depth = k_rrf, depth
        self.weights = weights or [1.0] * len(components)
        self.name = "rrf(" + "+".join(c.name for c in components) + ")"

    def search(self, queries, masks, k):
        per_component = [c.search(queries, masks, self.depth) for c in self.components]
        out = []
        for qi in range(len(queries)):
            row = []
            for mi in range(len(masks[qi])):
                fused: dict[int, float] = {}
                for comp, w in zip(per_component, self.weights):
                    for rank, r in enumerate(comp[qi][mi].rows):
                        fused[int(r)] = fused.get(int(r), 0.0) + w / (self.k_rrf + rank + 1)
                ordered = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
                row.append(Ranking(np.array([r for r, _ in ordered], dtype=np.int64),
                                   np.array([s for _, s in ordered], dtype=np.float32)))
            out.append(row)
        return out


class NameRouter(Retriever):
    """Metadata routing: if the query names a vehicle (brand + model tokens), restrict the search to the
    manuals whose name matches best; otherwise search the whole scope. Deterministic, no model."""

    def __init__(self, corpus: Corpus, base: Retriever):
        super().__init__(corpus)
        self.base = base
        self.name = f"name_router({base.name})"

    @cached_property
    def _manual_keys(self) -> list[tuple[str, set[str], str]]:
        keys = []
        for m in self.corpus.manual_ids:
            meta = self.corpus.manual_meta[m]
            forms = name_forms(meta["name"], meta["brand"])
            brand_tokens = set(normalize_for_match(forms["brand"]).split())
            model_words = [w for w in normalize_for_match(forms["model"]).split() if w not in brand_tokens]
            keys.append((m, brand_tokens, " ".join(model_words)))
        return keys

    def route(self, text: str) -> list[str]:
        padded = f" {normalize_for_match(text)} "
        q = set(padded.split())
        best, best_score = [], 0.0
        for manual, brand, model in self._manual_keys:
            # The model name must appear as a contiguous phrase: "classe a" must not match "classe c ... a".
            if not model or f" {model} " not in padded:
                continue
            score = len(model.split()) + (0.5 if brand & q else 0.0)
            if score > best_score:
                best, best_score = [manual], score
            elif score == best_score:
                best.append(manual)
        return best

    def search(self, queries, masks, k):
        routed_masks = []
        for q, qmasks in zip(queries, masks):
            manuals = self.route(q.text)
            if not manuals:
                routed_masks.append(qmasks)
                continue
            route_mask = self.corpus.mask_for_manuals(manuals)
            routed = []
            for m in qmasks:
                combined = route_mask if m is None else (route_mask & m)
                routed.append(combined if combined.any() else m)  # route outside the scope: fall back
            routed_masks.append(routed)
        return self.base.search(queries, routed_masks, k)


class DocRouter(Retriever):
    """Two-stage retrieval: rank manuals by the mean of their top-`agg` chunk scores, keep the best
    `n_docs` manuals, then rank chunks only inside them (hierarchical doc -> chunk retrieval)."""

    def __init__(self, corpus: Corpus, base: ScoringRetriever, n_docs: int = 3, agg: int = 3):
        super().__init__(corpus)
        self.base, self.n_docs, self.agg = base, n_docs, agg
        self.name = f"doc_router{n_docs}({base.name})"
        self._starts = np.flatnonzero(np.r_[True, np.diff(corpus.row_manual_idx) != 0])

    def _manual_scores(self, scores: np.ndarray) -> np.ndarray:
        """Mean of the top-`agg` chunk scores of every manual (scopes mask whole manuals, so this is mask-independent)."""
        out = np.empty(len(self._starts), dtype=np.float32)
        for i, seg in enumerate(np.split(scores, self._starts[1:])):
            a = min(self.agg, seg.size)
            out[i] = np.partition(seg, -a)[-a:].mean()
        return out

    def search(self, queries, masks, k):
        out = []
        bs = self.base.batch_size
        for start in range(0, len(queries), bs):
            batch = queries[start : start + bs]
            scores = self.base.score_batch(batch)
            for i in range(len(batch)):
                manual_scores = self._manual_scores(scores[i])
                row = []
                for m in masks[start + i]:
                    ms = manual_scores if m is None else np.where(m[self._starts], manual_scores, -np.inf)
                    keep = np.argsort(-ms)[: self.n_docs]
                    keep = keep[np.isfinite(ms[keep])]
                    doc_mask = np.isin(self.corpus.row_manual_idx, keep)
                    row.append(topk_in_mask(scores[i], doc_mask, k))
                out.append(row)
        return out


class NameBoost(ScoringRetriever):
    """Dense score + lambda * cos(query, embedding of the chunk's manual name): gives every chunk a
    document identity without re-embedding the corpus (a cheap proxy for contextual chunk headers)."""

    def __init__(self, corpus: Corpus, dense, lam: float = 0.5):
        super().__init__(corpus)
        self.dense, self.lam = dense, lam
        self.name = f"name_boost{lam}({dense.name})"
        self.batch_size = dense.batch_size

    @cached_property
    def _name_matrix(self) -> np.ndarray:
        titles = [Query(f"name::{m}", self.corpus.manual_meta[m]["name"], "fr") for m in self.corpus.manual_ids]
        return self.dense.encode_queries(titles)  # manual names embedded like short queries (symmetric match)

    def score_batch(self, queries):
        qv = self.dense.encode_queries(queries)
        name_sim = qv @ self._name_matrix.T                      # [q, n_manuals]
        return qv @ self.dense.doc_matrix.T + self.lam * name_sim[:, self.corpus.row_manual_idx]
