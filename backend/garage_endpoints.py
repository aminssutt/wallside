"""Flask routes for Auris Garage Beta.

Register via: register_garage_routes(app, limiter) in api.py.

Endpoints:
    GET  /api/garage/health            - status des corpus et counts
    GET  /api/garage/dtc/<code>        - lookup DTC (curated + structural decode)
    POST /api/garage/dtc-search        - recherche hybride dans corpus DTC
    POST /api/garage/recalls-search    - recherche hybride dans corpus rappels
    POST /api/garage/waitlist          - inscription waitlist B2B garage

Persistances : CSV thread-safe dans backend/data/waitlist/garage_waitlist.csv.
Rate limiting : reutilise le Limiter global d'api.py.
"""
from __future__ import annotations

import csv
import json
import logging
import pickle
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request

from garage_scraping.adapters.dtc_dictionary import (
    is_valid_dtc,
    lookup_curated,
    normalize_dtc,
    total_curated,
)

log = logging.getLogger("auris.garage")

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
DTC_DIR = DATA_DIR / "garage_dtc"
RECALLS_DIR = DATA_DIR / "garage_recalls"

GARAGE_WAITLIST_DIR = DATA_DIR / "waitlist"
GARAGE_WAITLIST_FILE = GARAGE_WAITLIST_DIR / "garage_waitlist.csv"
GARAGE_WAITLIST_COLUMNS = [
    "email",
    "garage_name",
    "country",
    "garage_type",
    "team_size",
    "lang",
    "source",
    "created_at",
]
_WAITLIST_LOCK = threading.Lock()

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_QUERY_LENGTH = 500
MAX_SEARCH_RESULTS = 10

# Simple in-memory cache for BM25 indexes (chargement paresseux).
_BM25_CACHE: dict[str, tuple[object, list[dict]]] = {}
_BM25_CACHE_LOCK = threading.Lock()


def _csv_safe(value: str) -> str:
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def _load_bm25(corpus_dir: Path) -> Optional[tuple[object, list[dict]]]:
    key = str(corpus_dir)
    with _BM25_CACHE_LOCK:
        if key in _BM25_CACHE:
            return _BM25_CACHE[key]
    path = corpus_dir / "bm25_index.pkl"
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            data = pickle.load(f)
        bundle = (data.get("bm25"), data.get("chunks") or [])
        if not bundle[0] or not bundle[1]:
            return None
        with _BM25_CACHE_LOCK:
            _BM25_CACHE[key] = bundle
        return bundle
    except Exception as exc:
        log.warning("BM25 load failed for %s: %s", corpus_dir, exc)
        return None


_TOKEN_RE = re.compile(r"[a-zA-Z0-9\u00c0-\u00ff]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _bm25_search(corpus_dir: Path, query: str, limit: int) -> list[dict]:
    bundle = _load_bm25(corpus_dir)
    if not bundle:
        return []
    bm25, chunks = bundle
    tokens = _tokenize(query)
    if not tokens:
        return []
    scores = bm25.get_scores(tokens)
    ranked = sorted(
        ((float(score), idx) for idx, score in enumerate(scores)),
        key=lambda x: x[0],
        reverse=True,
    )
    out: list[dict] = []
    for score, idx in ranked[:limit]:
        if score <= 0:
            break
        chunk = dict(chunks[idx])
        chunk["score"] = round(score, 4)
        out.append(chunk)
    return out


def _count_chunks(corpus_dir: Path) -> int:
    chunks_file = corpus_dir / "chunks.json"
    if not chunks_file.exists():
        return 0
    try:
        return len(json.loads(chunks_file.read_text(encoding="utf-8")))
    except Exception:
        return 0


def _count_docs(corpus_dir: Path) -> int:
    raw_file = corpus_dir / "raw_docs.json"
    if not raw_file.exists():
        return 0
    try:
        return len(json.loads(raw_file.read_text(encoding="utf-8")))
    except Exception:
        return 0


def _corpus_status(corpus_dir: Path) -> dict:
    return {
        "path": str(corpus_dir.relative_to(BACKEND_DIR)) if corpus_dir.exists() else None,
        "built": corpus_dir.exists() and (corpus_dir / "chunks.json").exists(),
        "faiss": (corpus_dir / "index.faiss").exists(),
        "bm25": (corpus_dir / "bm25_index.pkl").exists(),
        "documents": _count_docs(corpus_dir),
        "chunks": _count_chunks(corpus_dir),
    }


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_garage_routes(app: Flask, limiter) -> None:  # noqa: ANN001
    @app.route("/api/garage/health", methods=["GET"])
    def garage_health():
        return jsonify(
            {
                "status": "ok",
                "mode": "beta",
                "corpora": {
                    "dtc": _corpus_status(DTC_DIR),
                    "recalls": _corpus_status(RECALLS_DIR),
                },
                "curated_dtc_count": total_curated(),
            }
        )

    @app.route("/api/garage/dtc/<code>", methods=["GET"])
    @limiter.limit("60 per minute")
    def garage_dtc_lookup(code: str):
        code_norm = normalize_dtc(code)
        if not is_valid_dtc(code_norm):
            return (
                jsonify({"success": False, "error": "invalid_dtc_format", "code": code_norm}),
                400,
            )
        result = lookup_curated(code_norm)
        return jsonify({"success": True, **result})

    @app.route("/api/garage/dtc-search", methods=["POST"])
    @limiter.limit("30 per minute")
    def garage_dtc_search():
        data = request.get_json(silent=True) or {}
        query = str(data.get("query", "")).strip()
        limit = int(data.get("limit") or 5)
        if not query:
            return jsonify({"success": False, "error": "empty_query"}), 400
        if len(query) > MAX_QUERY_LENGTH:
            return jsonify({"success": False, "error": "query_too_long"}), 400
        limit = max(1, min(limit, MAX_SEARCH_RESULTS))
        hits = _bm25_search(DTC_DIR, query, limit)
        return jsonify({"success": True, "query": query, "count": len(hits), "results": hits})

    @app.route("/api/garage/recalls-search", methods=["POST"])
    @limiter.limit("30 per minute")
    def garage_recalls_search():
        data = request.get_json(silent=True) or {}
        query = str(data.get("query", "")).strip()
        brand = str(data.get("brand", "")).strip()
        limit = int(data.get("limit") or 5)
        if not query and not brand:
            return jsonify({"success": False, "error": "empty_query"}), 400
        if len(query) > MAX_QUERY_LENGTH:
            return jsonify({"success": False, "error": "query_too_long"}), 400
        limit = max(1, min(limit, MAX_SEARCH_RESULTS))
        composed = " ".join(p for p in [brand, query] if p)
        hits = _bm25_search(RECALLS_DIR, composed, limit)
        if brand:
            brand_lower = brand.lower()
            hits = [h for h in hits if (h.get("brand") or "").lower().find(brand_lower) >= 0] or hits
        return jsonify(
            {
                "success": True,
                "query": composed,
                "filters": {"brand": brand},
                "count": len(hits),
                "results": hits,
            }
        )

    @app.route("/api/garage/waitlist", methods=["POST"])
    @limiter.limit("5 per minute")
    def garage_waitlist_signup():
        data = request.get_json(silent=True) or {}
        raw_email = str(data.get("email", "")).strip().lower()
        garage_name = str(data.get("garage_name", "")).strip()[:120]
        country = str(data.get("country", "")).strip()[:60]
        garage_type = str(data.get("garage_type", "")).strip()[:60]
        team_size = str(data.get("team_size", "")).strip()[:30]
        lang = str(data.get("lang", "fr")).strip().lower()[:10]
        source = str(data.get("source", "")).strip()[:120]

        if not EMAIL_REGEX.match(raw_email):
            return jsonify({"success": False, "error": "invalid_email"}), 400

        try:
            GARAGE_WAITLIST_DIR.mkdir(parents=True, exist_ok=True)
            with _WAITLIST_LOCK:
                existing = set()
                if GARAGE_WAITLIST_FILE.exists():
                    with GARAGE_WAITLIST_FILE.open("r", encoding="utf-8", newline="") as f:
                        for row in csv.DictReader(f):
                            val = str(row.get("email", "")).strip().lower()
                            if val:
                                existing.add(val)
                if raw_email in existing:
                    return jsonify({"success": True, "already_exists": True}), 200

                write_header = (
                    not GARAGE_WAITLIST_FILE.exists()
                    or GARAGE_WAITLIST_FILE.stat().st_size == 0
                )
                with GARAGE_WAITLIST_FILE.open("a", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=GARAGE_WAITLIST_COLUMNS)
                    if write_header:
                        writer.writeheader()
                    writer.writerow(
                        {
                            "email": _csv_safe(raw_email),
                            "garage_name": _csv_safe(garage_name),
                            "country": _csv_safe(country),
                            "garage_type": _csv_safe(garage_type),
                            "team_size": _csv_safe(team_size),
                            "lang": _csv_safe(lang),
                            "source": _csv_safe(source),
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            return jsonify({"success": True, "already_exists": False}), 201
        except Exception:
            log.exception("garage waitlist write failed")
            return jsonify({"success": False, "error": "waitlist_write_failed"}), 500
