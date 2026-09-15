"""Build the research corpus from the production indexes (backend/data/guides/<slug>/vector_store).

The BM25 pickles hold the exact chunk texts used in production, and the FAISS indexes hold their
gemini-embedding-001 vectors in the same order, so the corpus is reproduced byte-for-byte and the
document embeddings never have to be recomputed.
"""
from __future__ import annotations

import json
import logging
import pickle
import re
import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths
from .text import STOPWORDS, content_hash, detect_lang, normalize_for_match, raw_tokens

log = logging.getLogger(__name__)

GEMINI_DOC_MODEL = "gemini-embedding-001"
GARBLED_STOPWORD_RATIO = 0.05
_PAGE_NUM_RE = re.compile(r"\d+")


def stopword_ratio(text: str) -> float:
    toks = raw_tokens(text)
    if len(toks) < 20:
        return 1.0  # too short to judge; short chunks are tracked separately via n_chars
    return sum(t in STOPWORDS for t in toks) / len(toks)


def parse_pages(label: str) -> tuple[int | None, int | None]:
    nums = [int(n) for n in _PAGE_NUM_RE.findall(str(label or ""))]
    if not nums:
        return None, None
    return min(nums), max(nums)


def _vehicle_groups() -> dict[str, str]:
    """Map manual slug -> vehicle slug using the app's own grouping (GuideManager)."""
    backend_dir = paths.REPO_ROOT / "backend"
    sys.path.insert(0, str(backend_dir))
    try:
        from src.guide_manager import GuideManager  # type: ignore

        mapping: dict[str, str] = {}
        for guide in GuideManager().guides.values():
            for source in guide.source_slugs:
                mapping[source] = guide.slug
        return mapping
    except Exception as exc:  # grouping is metadata only; never block corpus build on it
        log.warning("Vehicle grouping unavailable (%s); using manual slug as vehicle", exc)
        return {}
    finally:
        sys.path.remove(str(backend_dir))


def _load_chunks(vs_dir: Path) -> list:
    with (vs_dir / "bm25_index.pkl").open("rb") as f:
        return pickle.load(f)["chunks"]


def build_corpus(guides_dir: Path | None = None, with_embeddings: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    import faiss

    guides_dir = guides_dir or paths.GUIDES_DIR
    paths.ensure_dirs()
    manifest = json.loads((guides_dir / "manifest.json").read_text(encoding="utf-8"))
    vehicles = _vehicle_groups()

    first_by_hash: dict[str, str] = {}
    manual_rows, chunk_rows, vectors = [], [], []
    for entry in sorted(manifest, key=lambda e: e["slug"]):
        slug = entry["slug"]
        vs_dir = guides_dir / slug / "vector_store"
        chunks = _load_chunks(vs_dir)
        index = faiss.read_index(str(vs_dir / "index.faiss"))
        if index.ntotal != len(chunks):
            raise ValueError(f"{slug}: FAISS has {index.ntotal} vectors but BM25 has {len(chunks)} chunks")
        if with_embeddings:
            vectors.append(index.reconstruct_n(0, index.ntotal).astype(np.float16))

        sample = " ".join(c.page_content for c in chunks[:300])
        source_hash = entry.get("source_hash", "")
        duplicate_of = first_by_hash.get(source_hash) if source_hash else None
        if source_hash and duplicate_of is None:
            first_by_hash[source_hash] = slug
        manual_rows.append(
            {
                "manual": slug,
                "name": entry.get("name", slug),
                "brand": entry.get("brand", ""),
                "brand_key": normalize_for_match(entry.get("brand", "")),
                "vehicle": vehicles.get(slug, slug),
                "segment": entry.get("segment", ""),
                "lang": detect_lang(sample),
                "extraction_mode": entry.get("extraction_mode", ""),
                "page_count": int(entry.get("page_count") or 0),
                "n_chunks": len(chunks),
                "source_hash": source_hash,
                "duplicate_of": duplicate_of,
            }
        )
        for i, doc in enumerate(chunks):
            label = str(doc.metadata.get("page", "?"))
            start, end = parse_pages(label)
            chunk_rows.append(
                {
                    "chunk_id": f"{slug}::{i:05d}",
                    "manual": slug,
                    "chunk_index": i,
                    "page_label": label,
                    "page_start": start,
                    "page_end": end,
                    "text": doc.page_content,
                    "n_chars": len(doc.page_content),
                    "norm_hash": content_hash(doc.page_content),
                }
            )

    manuals = pd.DataFrame(manual_rows)
    chunks_df = pd.DataFrame(chunk_rows)
    chunks_df.insert(0, "row", np.arange(len(chunks_df), dtype=np.int64))
    by_hash = chunks_df.groupby("norm_hash")["manual"]
    chunks_df["dup_count"] = by_hash.transform("size").astype(np.int32)
    chunks_df["dup_manuals"] = by_hash.transform("nunique").astype(np.int32)
    chunks_df["stopword_ratio"] = chunks_df["text"].map(stopword_ratio).astype(np.float32)
    # Font-encoding failures in PDF extraction produce shifted-alphabet text ("UUIFPDDVQBOU" = "theoccupant")
    # with almost no stopwords; real FR/EN prose is ~30-40% stopwords.
    chunks_df["garbled"] = chunks_df["stopword_ratio"] < GARBLED_STOPWORD_RATIO
    manuals["garbled_share"] = manuals["manual"].map(chunks_df.groupby("manual")["garbled"].mean()).astype(np.float32)

    manuals.to_parquet(paths.MANUALS_PATH, index=False)
    chunks_df.to_parquet(paths.CHUNKS_PATH, index=False)
    if with_embeddings:
        matrix = np.concatenate(vectors)
        out_dir = paths.EMBEDDINGS_DIR / GEMINI_DOC_MODEL
        out_dir.mkdir(parents=True, exist_ok=True)
        np.save(out_dir / "chunks.npy", matrix)
        (out_dir / "meta.json").write_text(
            json.dumps(
                {
                    "model": GEMINI_DOC_MODEL,
                    "dim": int(matrix.shape[1]),
                    "n": int(matrix.shape[0]),
                    "dtype": "float16",
                    "task_type": "RETRIEVAL_DOCUMENT",
                    "source": "extracted from production FAISS indexes",
                    "corpus_fingerprint": corpus_fingerprint(chunks_df),
                },
                indent=2,
            )
        )
    return manuals, chunks_df


def corpus_fingerprint(chunks_df: pd.DataFrame) -> str:
    import hashlib

    digest = hashlib.sha1()
    for cid, h in zip(chunks_df["chunk_id"], chunks_df["norm_hash"]):
        digest.update(f"{cid}:{h}\n".encode())
    return digest.hexdigest()[:16]


@dataclass
class Corpus:
    """Loaded corpus with fast manual <-> row lookups."""

    chunks: pd.DataFrame
    manuals: pd.DataFrame

    @classmethod
    def load(cls) -> "Corpus":
        if not paths.CHUNKS_PATH.exists():
            raise FileNotFoundError(f"{paths.CHUNKS_PATH} missing: run `ragscale corpus` first")
        return cls(pd.read_parquet(paths.CHUNKS_PATH), pd.read_parquet(paths.MANUALS_PATH))

    def __len__(self) -> int:
        return len(self.chunks)

    @cached_property
    def manual_ids(self) -> list[str]:
        return self.manuals["manual"].tolist()

    @cached_property
    def manual_index(self) -> dict[str, int]:
        return {m: i for i, m in enumerate(self.manual_ids)}

    @cached_property
    def row_manual_idx(self) -> np.ndarray:
        """int16 array: manual index of every chunk row."""
        return self.chunks["manual"].map(self.manual_index).to_numpy(np.int16)

    @cached_property
    def manual_meta(self) -> dict[str, dict]:
        return self.manuals.set_index("manual").to_dict("index")

    @cached_property
    def chunk_ids(self) -> np.ndarray:
        return self.chunks["chunk_id"].to_numpy()

    def mask_for_manuals(self, manuals: list[str] | set[str]) -> np.ndarray:
        wanted = np.zeros(len(self.manual_ids), dtype=bool)
        for m in manuals:
            wanted[self.manual_index[m]] = True
        return wanted[self.row_manual_idx]

    def load_embeddings(self, model: str = GEMINI_DOC_MODEL) -> np.ndarray:
        path = paths.EMBEDDINGS_DIR / model / "chunks.npy"
        matrix = np.load(path, mmap_mode="r")
        if matrix.shape[0] != len(self):
            raise ValueError(f"{path} has {matrix.shape[0]} rows, corpus has {len(self)}")
        return matrix
