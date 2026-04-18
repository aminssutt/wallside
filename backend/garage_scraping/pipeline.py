"""Pipeline d'ingestion pour Auris Garage Beta.

Transforme les documents normalises des adapters en :
- chunks.json : liste des chunks textuels avec metadata
- FAISS index : vecteurs Gemini (si GOOGLE_API_KEY disponible)
- BM25 index : fallback lexical toujours construit

La structure de sortie mimique `backend/data/guides/{slug}/` pour
rester compatible avec le loader existant du chatbot.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .base import NormalizedDoc, SourceAdapter

log = logging.getLogger("auris.garage.pipeline")

# Chunking simple : la plupart des fiches DTC / rappels sont courtes.
# On garde des chunks generement dimensionnes et on coupe sur paragraphes.
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 120


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-zA-Z0-9\u00c0-\u00ff]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _split_paragraphs(text: str, chunk_size: int, overlap: int) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    pieces: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            window = text[start:end]
            for sep in ["\n\n", "\n", ". ", "! ", "? ", ", ", " "]:
                cut = window.rfind(sep)
                if cut > chunk_size // 3:
                    end = start + cut + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= text_len:
            break
        start = max(end - overlap, start + 1)
    return pieces


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class IngestionReport:
    def __init__(self, corpus: str) -> None:
        self.corpus = corpus
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str = ""
        self.sources: list[dict] = []
        self.total_docs = 0
        self.total_chunks = 0
        self.faiss_built = False
        self.bm25_built = False
        self.errors: list[str] = []

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "corpus": self.corpus,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "sources": self.sources,
            "total_docs": self.total_docs,
            "total_chunks": self.total_chunks,
            "faiss_built": self.faiss_built,
            "bm25_built": self.bm25_built,
            "errors": self.errors,
        }


def _build_bm25(chunks: list[dict]) -> tuple[object, list[dict]] | None:
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        log.warning("rank_bm25 manquant, BM25 ignore")
        return None

    tokenized = [_tokenize(c["text"]) for c in chunks]
    tokenized = [toks if toks else ["_"] for toks in tokenized]
    bm25 = BM25Okapi(tokenized)
    return bm25, chunks


def _build_faiss(chunks: list[dict], out_dir: Path) -> bool:
    """Build FAISS index. Return True on success, False on skip/failure."""
    if not os.getenv("GOOGLE_API_KEY"):
        log.info("GOOGLE_API_KEY manquante, FAISS ignore pour %s", out_dir.name)
        return False

    try:
        from langchain_core.documents import Document
        from src.vector_store import create_vector_store  # type: ignore
    except Exception as exc:
        log.warning("FAISS/embeddings indisponibles : %s", exc)
        return False

    docs = [
        Document(
            page_content=c["text"],
            metadata={k: v for k, v in c.items() if k != "text"},
        )
        for c in chunks
    ]

    try:
        create_vector_store(docs, persist_directory=str(out_dir))
        return True
    except Exception as exc:
        log.exception("Echec construction FAISS : %s", exc)
        return False


def run_ingestion(
    corpus_name: str,
    adapters: Iterable[SourceAdapter],
    output_dir: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> IngestionReport:
    """Execute pipeline for a corpus (group of adapters sharing an index)."""
    report = IngestionReport(corpus_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict] = []
    raw_docs: list[dict] = []

    for adapter in adapters:
        source_stats = {"source": adapter.name, "docs": 0, "chunks": 0, "error": None}
        try:
            count = 0
            for doc in adapter.fetch():
                count += 1
                raw_docs.append(doc.to_dict())
                for idx, chunk_text in enumerate(
                    _split_paragraphs(doc.text, chunk_size, chunk_overlap)
                ):
                    chunk = {
                        "text": chunk_text,
                        "doc_id": doc.doc_id,
                        "source": doc.source,
                        "title": doc.title,
                        "url": doc.url,
                        "brand": doc.brand,
                        "model": doc.model,
                        "year": doc.year,
                        "category": doc.category,
                        "license": doc.license,
                        "chunk_index": idx,
                    }
                    all_chunks.append(chunk)
                    source_stats["chunks"] += 1
            source_stats["docs"] = count
        except Exception as exc:
            log.exception("Adapter %s failed", adapter.name)
            source_stats["error"] = str(exc)
            report.errors.append(f"{adapter.name}: {exc}")
        report.sources.append(source_stats)

    report.total_docs = len(raw_docs)
    report.total_chunks = len(all_chunks)

    # Persist raw + chunks
    raw_path = output_dir / "raw_docs.json"
    chunks_path = output_dir / "chunks.json"
    raw_path.write_text(
        json.dumps(raw_docs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    chunks_path.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # BM25
    if all_chunks:
        bm25_bundle = _build_bm25(all_chunks)
        if bm25_bundle:
            bm25, used_chunks = bm25_bundle
            bm25_path = output_dir / "bm25_index.pkl"
            with bm25_path.open("wb") as f:
                pickle.dump({"bm25": bm25, "chunks": used_chunks}, f)
            report.bm25_built = True

    # FAISS (optional, best effort)
    if all_chunks:
        report.faiss_built = _build_faiss(all_chunks, output_dir)

    report.finish()
    report_path = output_dir / "ingestion_report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
