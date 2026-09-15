"""Retrievers built on top of other retrievers: fusion, routing, name boosting."""
from __future__ import annotations

import re
from functools import cached_property

import numpy as np

from ..corpus import Corpus
from ..dataset.names import name_forms
from ..text import COMMON_WORD_MODELS, mentions_name, normalize_for_match
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

    def __init__(self, corpus: Corpus, base: Retriever, strip: bool = False):
        super().__init__(corpus)
        self.base, self.strip = base, strip
        self.name = f"name_router{'_strip' if strip else ''}({base.name})"

    # Words that name a kind of manual, not a vehicle ("Alfa Romeo Infotainment System" must not capture every
    # question about an infotainment system).
    GENERIC_WORDS = frozenset("infotainment system multimedia media nav navigation live guide quick reference manual "
                              "owner owners easy link mbux carnet entretien et garanties toutes gen".split())

    @cached_property
    def _manual_keys(self) -> list[dict]:
        keys = []
        for m in self.corpus.manual_ids:
            meta = self.corpus.manual_meta[m]
            brand = set(normalize_for_match(meta["brand"]).split())
            name_words = normalize_for_match(meta["name"]).split()
            model_words = normalize_for_match(name_forms(meta["name"], meta["brand"])["model"]).split()
            model = [w for w in model_words if w not in brand and w not in self.GENERIC_WORDS]
            keys.append({
                "manual": m,
                "brand": brand,
                "model": " ".join(model),
                # "Renault 5", "DS 4": a bare short number only identifies the vehicle together with the brand
                "needs_brand": len(model) == 1 and model[0].isdigit() and len(model[0]) <= 2,
                "years": {w for w in name_words if re.fullmatch(r"(19|20)\d{2}", w) and w not in model},
                "generic_words": {w for w in name_words if w in self.GENERIC_WORDS},
            })
        return keys

    def route(self, text: str) -> list[str]:
        padded = f" {normalize_for_match(text)} "
        q = set(padded.split())
        best, best_score = [], 0.0
        for key in self._manual_keys:
            has_brand = bool(key["brand"]) and key["brand"] <= q
            if key["model"]:
                # Contiguous phrase: "classe a" must not match "classe c ... a".
                if f" {key['model']} " not in padded or (key["needs_brand"] and not has_brand):
                    continue
                if key["model"] in COMMON_WORD_MODELS and not has_brand and not mentions_name(text, key["model"]):
                    continue  # "ranger le coffre" is not a Ford Ranger
                score = (len(key["model"].split()) + 0.5 * has_brand + 0.25 * len(key["years"] & q)
                         + 0.1 * len(key["generic_words"] & q))  # "Palisade ... Infotainment System" -> that manual
            elif has_brand and key["generic_words"] & q:
                # Brand-level manual (infotainment system, maintenance booklet): weaker than any model match.
                score = 0.5 + 0.1 * len(key["generic_words"] & q)
            else:
                continue
            if score > best_score + 1e-9:
                best, best_score = [key["manual"]], score
            elif abs(score - best_score) <= 1e-9:
                best.append(key["manual"])
        return best

    def strip_names(self, text: str, manuals: list[str]) -> str:
        """Remove the words that named the vehicle once the search is restricted to it: inside the right
        manual, "Peugeot 208 (2023)" only dilutes the passage-matching part of the query."""
        drop: set[str] = set()
        for key in self._manual_keys:
            if key["manual"] in manuals:
                drop |= key["brand"] | set(key["model"].split()) | key["years"] | key["generic_words"]
        kept = [w for w in re.findall(r"\S+", text) if not (set(normalize_for_match(w).split()) and set(normalize_for_match(w).split()) <= drop)]
        stripped = " ".join(kept).strip()
        return stripped if len(stripped) >= 8 else text

    def search(self, queries, masks, k):
        routed_masks, routed_queries = [], []
        for q, qmasks in zip(queries, masks):
            manuals = self.route(q.text)
            routed_queries.append(Query(q.qid, self.strip_names(q.text, manuals), q.lang) if (manuals and self.strip) else q)
            if not manuals:
                routed_masks.append(qmasks)
                continue
            route_mask = self.corpus.mask_for_manuals(manuals)
            routed = []
            for m in qmasks:
                combined = route_mask if m is None else (route_mask & m)
                routed.append(combined if combined.any() else m)  # route outside the scope: fall back
            routed_masks.append(routed)
        return self.base.search(routed_queries, routed_masks, k)


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


class ScoreFusion(Retriever):
    """Score-level fusion of component rankings inside the same mask (Fox & Shaw 1994; Bruch et al. 2023).

    Each component's top-`depth` scores are normalized per query and mask ("minmax" or "zscore"); a chunk
    missing from a component's list gets that component's minimum normalized score.
      method="wsum"    sum of weight * normalized score (convex combination when weights sum to 1)
      method="combmnz" wsum multiplied by the number of components that retrieved the chunk"""

    def __init__(self, corpus: Corpus, components: list[Retriever], weights: list[float] | None = None,
                 norm: str = "minmax", method: str = "wsum", depth: int = 100):
        super().__init__(corpus)
        if norm not in ("minmax", "zscore") or method not in ("wsum", "combmnz"):
            raise ValueError(f"bad fusion config norm={norm} method={method}")
        self.components, self.norm, self.method, self.depth = components, norm, method, depth
        self.weights = weights or [1.0 / len(components)] * len(components)
        if len(self.weights) != len(components):
            raise ValueError("one weight per component")
        w = "|".join(f"{x:g}" for x in self.weights)
        self.name = f"{method}[{norm};w={w}](" + "+".join(c.name for c in components) + ")"

    def _normalize(self, scores: np.ndarray) -> np.ndarray:
        if scores.size == 0:
            return scores
        if self.norm == "minmax":
            span = scores.max() - scores.min()
            return (scores - scores.min()) / span if span > 0 else np.ones_like(scores)
        std = scores.std()
        return (scores - scores.mean()) / std if std > 0 else np.zeros_like(scores)

    def fuse(self, rankings: list[Ranking], k: int) -> Ranking:
        normalized = [(r.rows, self._normalize(r.scores.astype(np.float64))) for r in rankings]
        candidates = np.unique(np.concatenate([rows for rows, _ in normalized])) if normalized else np.empty(0, np.int64)
        if candidates.size == 0:
            return Ranking(np.empty(0, np.int64), np.empty(0, np.float32))
        total = np.zeros(candidates.size)
        hits = np.zeros(candidates.size)
        for (rows, norm_scores), w in zip(normalized, self.weights):
            floor = norm_scores.min() if norm_scores.size else 0.0
            filled = np.full(candidates.size, floor)
            pos = np.searchsorted(candidates, rows)
            filled[pos] = norm_scores
            hits[pos] += 1
            total += w * filled
        if self.method == "combmnz":
            total *= hits
        order = np.argsort(-total, kind="stable")[:k]
        return Ranking(candidates[order].astype(np.int64), total[order].astype(np.float32))

    def search(self, queries, masks, k):
        per_component = [c.search(queries, masks, self.depth) for c in self.components]
        return [[self.fuse([comp[qi][mi] for comp in per_component], k) for mi in range(len(masks[qi]))]
                for qi in range(len(queries))]
