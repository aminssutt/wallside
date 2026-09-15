"""Second-stage reranking of a first-stage candidate list, with a persistent (query, chunk) score cache.

Candidates of all scope masks of a query are scored once (their union), then each mask's list is
re-sorted, so adding corpus-size conditions does not multiply model calls.
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
from abc import abstractmethod

import numpy as np

from .. import paths
from ..corpus import Corpus
from .base import Query, Ranking, Retriever

log = logging.getLogger(__name__)

RERANKERS = {
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
}


def _device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


class PairReranker(Retriever):
    cache_name: str

    def __init__(self, corpus: Corpus, base: Retriever, depth: int):
        super().__init__(corpus)
        self.base, self.depth = base, depth
        self._texts = corpus.chunks["text"].to_numpy()
        db = paths.CACHE_DIR / f"rerank-{self.cache_name}.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS s (q TEXT, r INTEGER, v REAL, PRIMARY KEY (q, r))")
        self._lock = threading.Lock()

    @abstractmethod
    def predict(self, query: str, passages: list[str]) -> list[float]:
        """Relevance score of each passage for the query (higher is better)."""

    def scores(self, query: Query, rows: list[int]) -> dict[int, float]:
        if not rows:
            return {}
        qkey = hashlib.sha1(query.text.encode()).hexdigest()
        with self._lock:
            cached = dict(self._db.execute(
                f"SELECT r, v FROM s WHERE q = ? AND r IN ({','.join('?' * len(rows))})", (qkey, *rows)
            ).fetchall())
        missing = [r for r in rows if r not in cached]
        if missing:
            values = self.predict(query.text, [self._texts[r] for r in missing])
            with self._lock:
                self._db.executemany("INSERT OR REPLACE INTO s VALUES (?, ?, ?)",
                                     [(qkey, int(r), float(v)) for r, v in zip(missing, values)])
            cached.update({int(r): float(v) for r, v in zip(missing, values)})
        return cached

    def search(self, queries, masks, k):
        from tqdm import tqdm

        first = self.base.search(queries, masks, self.depth)
        out = []
        for qi, q in enumerate(tqdm(queries, desc=self.name, leave=False)):
            union = sorted({int(r) for ranking in first[qi] for r in ranking.rows})
            s = self.scores(q, union)
            row = []
            for ranking in first[qi]:
                cand = sorted((int(r) for r in ranking.rows), key=lambda r: -s[r])[:k]
                row.append(Ranking(np.array(cand, dtype=np.int64), np.array([s[r] for r in cand], dtype=np.float32)))
            out.append(row)
        return out


class CrossEncoderRerank(PairReranker):
    """Cross-encoder (query and passage read jointly), e.g. BAAI/bge-reranker-v2-m3 (multilingual)."""

    def __init__(self, corpus: Corpus, base: Retriever, model: str = "bge-reranker-v2-m3", depth: int = 30,
                 batch_size: int = 32, max_length: int = 512):
        self.model_name, self.batch_size, self.max_length = model, batch_size, max_length
        self.cache_name = model
        super().__init__(corpus, base, depth)
        self.name = f"rerank:{model}@{depth}({base.name})"
        self._model = None

    def predict(self, query, passages):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            device = _device()
            self._model = CrossEncoder(RERANKERS[self.model_name], device=device, max_length=self.max_length)
            if device != "cpu":
                self._model.model.half()
        return self._model.predict([(query, p) for p in passages], batch_size=self.batch_size,
                                   show_progress_bar=False).tolist()


class M3Rerank(PairReranker):
    """BGE-M3 multi-functionality scoring (Chen et al. 2024, FlagOpen/FlagEmbedding): weighted sum of dense,
    sparse (lexical weights) and multi-vector (ColBERT late-interaction) similarities of the same model."""

    def __init__(self, corpus: Corpus, base: Retriever, depth: int = 30, weights: list[float] | None = None,
                 max_length: int = 512):
        self.weights = weights or [0.4, 0.2, 0.4]  # dense, sparse, colbert: FlagEmbedding's recommended default
        self.max_length = max_length
        self.cache_name = "bge-m3-all-" + "-".join(f"{w:g}" for w in self.weights)
        super().__init__(corpus, base, depth)
        self.name = f"m3rerank@{depth}({base.name})"
        self._model = None

    def predict(self, query, passages):
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel

            self._model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=_device() != "cpu", devices=_device())
        out = self._model.compute_score([(query, p) for p in passages], batch_size=16,
                                        max_passage_length=self.max_length,
                                        weights_for_different_modes=self.weights)
        return list(out["colbert+sparse+dense"])
