"""Filesystem layout and environment loading. Every path can be overridden by env var (used in Docker)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RESEARCH_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = RESEARCH_DIR.parent

load_dotenv(REPO_ROOT / ".env")


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    return Path(raw).expanduser().resolve() if raw else default


GUIDES_DIR = _env_path("RAGSCALE_GUIDES_DIR", REPO_ROOT / "backend" / "data" / "guides")
DATA_DIR = _env_path("RAGSCALE_DATA_DIR", RESEARCH_DIR / "data")
CORPUS_DIR = DATA_DIR / "corpus"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
CACHE_DIR = DATA_DIR / "cache"
RUNS_DIR = DATA_DIR / "runs"
DATASETS_DIR = _env_path("RAGSCALE_DATASETS_DIR", RESEARCH_DIR / "datasets")
RESULTS_DIR = _env_path("RAGSCALE_RESULTS_DIR", RESEARCH_DIR / "results")
CONFIGS_DIR = RESEARCH_DIR / "configs"

CHUNKS_PATH = CORPUS_DIR / "chunks.parquet"
MANUALS_PATH = CORPUS_DIR / "manuals.parquet"


def ensure_dirs() -> None:
    for d in (CORPUS_DIR, EMBEDDINGS_DIR, CACHE_DIR, RUNS_DIR, DATASETS_DIR, RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
