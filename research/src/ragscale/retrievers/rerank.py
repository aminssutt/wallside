"""Cross-encoder reranking of a first-stage candidate list, with a persistent (query, chunk) score cache."""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading

import numpy as np

from .. import paths
from ..corpus import Corpus
from .base import Query, Ranking, Retriever

log = logging.getLogger(__name__)

RERANKERS = {
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
}


class CrossEncoderRerank(Retriever):
    def __init__(self, corpus: Corpus, base: Retriever, model: str = "bge-reranker-v2-m3", depth: int = 30,
                 batch_size: int = 32, max_length: int = 512):
        super().__init__(corpus)
        self.base, self.model_name, self.depth = base, model, depth
        self.batch_size, self.max_length = batch_size, max_length
        self.name = f"rerank:{model}@{depth}({base.name})"
        self._model = None
        db = paths.CACHE_DIR / f"rerank-{model}.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS s (q TEXT, r INTEGER, v REAL, PRIMARY KEY (q, r))")
        self._lock = threading.Lock()

    @property
    def model(self):
        if self._model is None:
            import torch
            from sentence_transformers import CrossEncoder

            device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
            self._model = CrossEncoder(RERANKERS[self.model_name], device=device, max_length=self.max_length)
            if device != "cpu":
                self._model.model.half()
        return self._model

    def _scores(self, query: Query, rows: list[int]) -> dict[int, float]:
        qkey = hashlib.sha1(query.text.encode()).hexdigest()
        with self._lock:
            cached = dict(self._db.execute(
                f"SELECT r, v FROM s WHERE q = ? AND r IN ({','.join('?' * len(rows))})", (qkey, *rows)
            ).fetchall()) if rows else {}
        missing = [r for r in rows if r not in cached]
        if missing:
            texts = self.corpus.chunks["text"].to_numpy()
            pairs = [(query.text, texts[r]) for r in missing]
            values = self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)
            with self._lock:
                self._db.executemany("INSERT OR REPLACE INTO s VALUES (?, ?, ?)",
                                     [(qkey, int(r), float(v)) for r, v in zip(missing, values)])
            cached.update({int(r): float(v) for r, v in zip(missing, values)})
        return cached

    def search(self, queries, masks, k):
        first = self.base.search(queries, masks, self.depth)
        out = []
        from tqdm import tqdm

        for qi, q in enumerate(tqdm(queries, desc=f"rerank {self.model_name}", leave=False)):
            union = sorted({int(r) for ranking in first[qi] for r in ranking.rows})
            scores = self._scores(q, union)
            row = []
            for ranking in first[qi]:
                cand = [int(r) for r in ranking.rows]
                cand.sort(key=lambda r: -scores[r])
                cand = cand[:k]
                row.append(Ranking(np.array(cand, dtype=np.int64), np.array([scores[r] for r in cand], dtype=np.float32)))
            out.append(row)
        return out
