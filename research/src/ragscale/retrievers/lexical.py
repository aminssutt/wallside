"""Lexical retrieval over the global corpus: BM25 (bm25s, Lucene variant), contextual headers, RM3 expansion."""
from __future__ import annotations

import logging
from collections import Counter

import bm25s
import numpy as np

from .. import paths
from ..corpus import Corpus, corpus_fingerprint
from ..text import content_tokens, stem_tokens
from .base import Query, ScoringRetriever

log = logging.getLogger(__name__)


def contextual_texts(corpus: Corpus) -> list[str]:
    """Chunk text prefixed with its document identity: 'Peugeot 208 (2023) | Peugeot | page 157'.

    Rule-based version of contextual chunk headers (Anthropic, "Contextual Retrieval", 2024): production
    chunks carry no vehicle name, so near-identical passages of sibling manuals are indistinguishable."""
    meta = corpus.manual_meta
    return [
        f"{meta[m]['name']} | {meta[m]['brand']} | page {p}\n{t}"
        for m, p, t in zip(corpus.chunks["manual"], corpus.chunks["page_label"], corpus.chunks["text"])
    ]


class BM25(ScoringRetriever):
    """stem=False: accent-folded tokens minus FR/EN stopwords. stem=True: plus Snowball stemming in the
    manual's language (documents) / the query's language (queries). contextual=True: index chunks with
    their document header (see `contextual_texts`)."""

    def __init__(self, corpus: Corpus, stem: bool = False, contextual: bool = False, k1: float = 1.2, b: float = 0.75):
        super().__init__(corpus)
        self.stem, self.contextual = stem, contextual
        self.name = ("bm25_stem" if stem else "bm25") + ("+ctx" if contextual else "")
        self.k1, self.b = k1, b
        self._doc_langs = corpus.chunks["manual"].map(lambda m: corpus.manual_meta[m]["lang"]).tolist()
        self.index = self._load_or_build()

    def tokens(self, text: str, lang: str) -> list[str]:
        toks = content_tokens(text)
        return stem_tokens(toks, lang) if self.stem else toks

    def doc_tokens(self, row: int) -> list[str]:
        return self.tokens(self._texts()[row], self._doc_langs[row])

    def _texts(self) -> list[str]:
        if not hasattr(self, "_text_cache"):
            self._text_cache = contextual_texts(self.corpus) if self.contextual else self.corpus.chunks["text"].tolist()
        return self._text_cache

    def _load_or_build(self) -> bm25s.BM25:
        fp = corpus_fingerprint(self.corpus.chunks)
        index_dir = paths.DATA_DIR / "indexes" / f"{self.name}-k{self.k1}-b{self.b}-{fp}"
        if (index_dir / "params.index.json").exists():
            return bm25s.BM25.load(str(index_dir))
        log.info("Building %s index over %d chunks", self.name, len(self.corpus))
        tokens = [self.tokens(t, lang) for t, lang in zip(self._texts(), self._doc_langs)]
        index = bm25s.BM25(k1=self.k1, b=self.b, method="lucene")
        index.index(tokens, show_progress=False)
        index_dir.mkdir(parents=True, exist_ok=True)
        index.save(str(index_dir))
        return index

    def score_tokens(self, tokens: list[str], weights: list[float] | None = None) -> np.ndarray:
        if weights is None:
            return self.index.get_scores(tokens).astype(np.float32)
        # Weighted query: sum of per-term scores (bm25s scores are additive over query terms).
        total = np.zeros(len(self.corpus), dtype=np.float32)
        for tok, w in zip(tokens, weights):
            total += w * self.index.get_scores([tok]).astype(np.float32)
        return total

    def score_batch(self, queries: list[Query]) -> np.ndarray:
        return np.stack([self.score_tokens(self.tokens(q.text, q.lang)) for q in queries])


class RM3(ScoringRetriever):
    """BM25 with RM3 pseudo-relevance feedback (Lavrenko & Croft 2001; Abdul-Jaleel et al. 2004).

    The top `fb_docs` chunks of a first BM25 pass (inside the whole corpus) give an expansion term
    distribution; the final query mixes the original terms (weight `orig_weight`) with the `fb_terms`
    best expansion terms. Feedback is taken over the global corpus, independently of the scope mask."""

    def __init__(self, corpus: Corpus, base: BM25, fb_docs: int = 10, fb_terms: int = 10, orig_weight: float = 0.5):
        super().__init__(corpus)
        self.base, self.fb_docs, self.fb_terms, self.orig_weight = base, fb_docs, fb_terms, orig_weight
        self.name = f"rm3({base.name})"

    def expand(self, query: Query) -> tuple[list[str], list[float]]:
        q_tokens = self.base.tokens(query.text, query.lang)
        if not q_tokens:
            return [], []
        first = self.base.score_tokens(q_tokens)
        top = np.argpartition(-first, self.fb_docs)[: self.fb_docs]
        top = top[first[top] > 0]
        if top.size == 0:
            return q_tokens, [1.0] * len(q_tokens)
        doc_weights = first[top] / first[top].sum()
        expansion: Counter[str] = Counter()
        for row, w in zip(top, doc_weights):
            toks = self.base.doc_tokens(int(row))
            if not toks:
                continue
            for tok, c in Counter(toks).items():
                expansion[tok] += float(w) * c / len(toks)
        best = expansion.most_common(self.fb_terms)
        norm = sum(v for _, v in best) or 1.0
        weights: Counter[str] = Counter()
        for tok in q_tokens:
            weights[tok] += self.orig_weight / len(q_tokens)
        for tok, v in best:
            weights[tok] += (1 - self.orig_weight) * v / norm
        return list(weights), list(weights.values())

    def score_batch(self, queries: list[Query]) -> np.ndarray:
        out = []
        for q in queries:
            toks, w = self.expand(q)
            out.append(self.base.score_tokens(toks, w) if toks else np.zeros(len(self.corpus), dtype=np.float32))
        return np.stack(out)
