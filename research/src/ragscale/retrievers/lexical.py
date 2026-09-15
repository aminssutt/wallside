"""BM25 over the global corpus (bm25s, Lucene variant)."""
from __future__ import annotations

import logging

import bm25s
import numpy as np

from .. import paths
from ..corpus import Corpus, corpus_fingerprint
from ..text import content_tokens, stem_tokens
from .base import Query, ScoringRetriever

log = logging.getLogger(__name__)


class BM25(ScoringRetriever):
    """stem=False: accent-folded tokens minus FR/EN stopwords. stem=True: plus Snowball stemming in the
    manual's language (documents) / the query's language (queries)."""

    def __init__(self, corpus: Corpus, stem: bool = False, k1: float = 1.2, b: float = 0.75):
        super().__init__(corpus)
        self.stem = stem
        self.name = "bm25_stem" if stem else "bm25"
        self.k1, self.b = k1, b
        self.index = self._load_or_build()

    def _tokens(self, text: str, lang: str) -> list[str]:
        toks = content_tokens(text)
        return stem_tokens(toks, lang) if self.stem else toks

    def _load_or_build(self) -> bm25s.BM25:
        fp = corpus_fingerprint(self.corpus.chunks)
        index_dir = paths.DATA_DIR / "indexes" / f"{self.name}-k{self.k1}-b{self.b}-{fp}"
        if (index_dir / "params.index.json").exists():
            return bm25s.BM25.load(str(index_dir))
        log.info("Building %s index over %d chunks", self.name, len(self.corpus))
        langs = self.corpus.chunks["manual"].map(lambda m: self.corpus.manual_meta[m]["lang"])
        tokens = [self._tokens(t, lang) for t, lang in zip(self.corpus.chunks["text"], langs)]
        index = bm25s.BM25(k1=self.k1, b=self.b, method="lucene")
        index.index(tokens, show_progress=False)
        index_dir.mkdir(parents=True, exist_ok=True)
        index.save(str(index_dir))
        return index

    def score_batch(self, queries: list[Query]) -> np.ndarray:
        return np.stack([self.index.get_scores(self._tokens(q.text, q.lang)).astype(np.float32) for q in queries])
