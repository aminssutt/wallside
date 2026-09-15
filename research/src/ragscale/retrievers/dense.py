"""Dense bi-encoder retrieval: Gemini API embeddings and local sentence-transformers models."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .. import paths
from ..corpus import GEMINI_DOC_MODEL, Corpus, corpus_fingerprint
from .base import Query, Ranking, Retriever, ScoringRetriever

log = logging.getLogger(__name__)

RETRIEVAL_INSTRUCTION = "Given a car owner's question, retrieve the passage of the vehicle's owner manual that answers it"


@dataclass(frozen=True)
class LocalModelSpec:
    hf_id: str
    query_prefix: str = ""
    doc_prefix: str = ""
    max_seq_length: int = 512
    batch_size: int = 32
    half: bool = True  # fp16 on MPS: ~3x faster, cosine to fp32 >= 0.9995 (measured)


LOCAL_MODELS: dict[str, LocalModelSpec] = {
    "bge-m3": LocalModelSpec("BAAI/bge-m3"),
    "multilingual-e5-large-instruct": LocalModelSpec(
        "intfloat/multilingual-e5-large-instruct",
        query_prefix=f"Instruct: {RETRIEVAL_INSTRUCTION}\nQuery: ",
    ),
    "qwen3-embedding-0.6b": LocalModelSpec(
        "Qwen/Qwen3-Embedding-0.6B",
        query_prefix=f"Instruct: {RETRIEVAL_INSTRUCTION}\nQuery:",
        batch_size=16,
    ),
}


def _device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=2)
def load_st_model(name: str):
    from sentence_transformers import SentenceTransformer

    spec = LOCAL_MODELS[name]
    model = SentenceTransformer(spec.hf_id, device=_device())
    model.max_seq_length = spec.max_seq_length
    if spec.half and _device() != "cpu":
        model.half()
    return model


CONTEXTUAL_SUFFIX = "+ctx"


def base_model(name: str) -> str:
    """'bge-m3+ctx' -> 'bge-m3' (same encoder, chunks indexed with contextual headers)."""
    return name[: -len(CONTEXTUAL_SUFFIX)] if name.endswith(CONTEXTUAL_SUFFIX) else name


def build_local_embeddings(corpus: Corpus, name: str, limit: int | None = None) -> np.ndarray:
    """Encode every chunk with a local model; resumable via per-shard files.
    A '+ctx' suffix encodes the chunks with their document header (see lexical.contextual_texts)."""
    spec = LOCAL_MODELS[base_model(name)]
    model = load_st_model(base_model(name))
    out_dir = paths.EMBEDDINGS_DIR / name
    shard_dir = out_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    if name.endswith(CONTEXTUAL_SUFFIX):
        from .lexical import contextual_texts

        texts = contextual_texts(corpus)[:limit]
    else:
        texts = corpus.chunks["text"].tolist()[:limit]
    # Sort by length so batches have similar padding (large speed-up); restore order at the end.
    order = np.argsort([len(t) for t in texts], kind="stable")
    shard = 4096
    parts = []
    from tqdm import tqdm

    for s in tqdm(range(0, len(order), shard), desc=f"encode {name}"):
        f = shard_dir / f"{s:07d}.npy"
        if f.exists():
            parts.append(np.load(f))
            continue
        idx = order[s : s + shard]
        vecs = model.encode(
            [spec.doc_prefix + texts[i] for i in idx],
            batch_size=spec.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float16)
        np.save(f, vecs)
        parts.append(vecs)
    sorted_vecs = np.concatenate(parts)
    matrix = np.empty_like(sorted_vecs)
    matrix[order] = sorted_vecs
    if limit is None:
        np.save(out_dir / "chunks.npy", matrix)
        (out_dir / "meta.json").write_text(
            json.dumps(
                {"model": spec.hf_id, "dim": int(matrix.shape[1]), "n": int(matrix.shape[0]), "dtype": "float16",
                 "contextual_headers": name.endswith(CONTEXTUAL_SUFFIX), "max_seq_length": spec.max_seq_length,
                 "corpus_fingerprint": corpus_fingerprint(corpus.chunks)},
                indent=2,
            )
        )
    return matrix


class DenseRetriever(ScoringRetriever):
    batch_size = 64

    def __init__(self, corpus: Corpus, model: str, gemini=None):
        super().__init__(corpus)
        self.model = model
        self.name = f"dense:{model}"
        self.gemini = gemini
        if model != GEMINI_DOC_MODEL and base_model(model) not in LOCAL_MODELS:
            raise ValueError(f"unknown dense model {model}")
        log.info("Loading %s document matrix", model)
        self.doc_matrix = np.ascontiguousarray(corpus.load_embeddings(model), dtype=np.float32)
        self._query_cache: dict[str, np.ndarray] = {}

    def encode_queries(self, queries: list[Query]) -> np.ndarray:
        todo = [q.text for q in queries if q.text not in self._query_cache]
        todo = list(dict.fromkeys(todo))
        if todo:
            if self.model == GEMINI_DOC_MODEL:
                if self.gemini is None:
                    from ..llm import Gemini

                    self.gemini = Gemini()
                vecs = self.gemini.embed(todo, GEMINI_DOC_MODEL, task_type="RETRIEVAL_QUERY")
            else:
                spec = LOCAL_MODELS[base_model(self.model)]
                vecs = load_st_model(base_model(self.model)).encode(
                    [spec.query_prefix + t for t in todo], batch_size=spec.batch_size,
                    normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False,
                ).astype(np.float32)
            self._query_cache.update(zip(todo, vecs))
        return np.stack([self._query_cache[q.text] for q in queries])

    def prepare(self, queries: list[Query]) -> None:
        """Encode all queries up front (one parallel API pass instead of per-batch calls)."""
        self.encode_queries(queries)

    def score_batch(self, queries: list[Query]) -> np.ndarray:
        return self.encode_queries(queries) @ self.doc_matrix.T


class FilteredANN(Retriever):
    """Approximate search (FAISS HNSW, inner product) restricted to the scope with an ID bitmap during graph
    traversal, as a filtered vector database would do. Compared with the exact DenseRetriever it measures
    how much recall approximate indexing loses as the corpus grows."""

    def __init__(self, corpus: Corpus, dense: DenseRetriever, m: int = 32, ef_construction: int = 200, ef_search: int = 64):
        super().__init__(corpus)
        self.dense, self.ef_search = dense, ef_search
        self.name = f"hnsw{m}-ef{ef_search}({dense.name})"
        self.index = self._load_or_build(m, ef_construction)

    def _load_or_build(self, m: int, ef_construction: int):
        import faiss

        path = paths.DATA_DIR / "indexes" / f"hnsw{m}-efc{ef_construction}-{self.dense.model}-{corpus_fingerprint(self.corpus.chunks)}.faiss"
        if path.exists():
            return faiss.read_index(str(path))
        log.info("Building HNSW index for %s", self.dense.model)
        index = faiss.IndexHNSWFlat(self.dense.doc_matrix.shape[1], m, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = ef_construction
        index.add(self.dense.doc_matrix)
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(path))
        return index

    def search(self, queries, masks, k):
        import faiss

        qv = self.dense.encode_queries(queries)
        out = []
        for i in range(len(queries)):
            row = []
            for mask in masks[i]:
                params = faiss.SearchParametersHNSW(efSearch=max(self.ef_search, k))
                if mask is not None:
                    params.sel = faiss.IDSelectorBitmap(np.packbits(mask, bitorder="little"))
                scores, ids = self.index.search(qv[i : i + 1], k, params=params)
                keep = ids[0] >= 0
                row.append(Ranking(ids[0][keep].astype(np.int64), scores[0][keep].astype(np.float32)))
            out.append(row)
        return out
