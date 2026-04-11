import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))

os.environ.setdefault("GOOGLE_API_KEY", "test-key")

from src.guide_chatbot import has_strong_manual_context  # noqa: E402


def _docs(n: int):
    return [object() for _ in range(n)]


def test_manual_context_strength_short_query_allows_single_strong_hit():
    assert has_strong_manual_context(
        True,
        _docs(1),
        quality_stats={
            "query_token_count": 2,
            "reliable_doc_count": 1,
            "best_overlap_count": 1,
            "top_rrf_score": 0.04,
        },
    )


def test_manual_context_strength_long_query_rejects_single_hit():
    assert not has_strong_manual_context(
        True,
        _docs(1),
        quality_stats={
            "query_token_count": 7,
            "reliable_doc_count": 1,
            "best_overlap_count": 1,
            "top_rrf_score": 0.06,
        },
    )


def test_manual_context_strength_requires_stronger_grounding_for_long_query():
    assert has_strong_manual_context(
        True,
        _docs(2),
        quality_stats={
            "query_token_count": 8,
            "reliable_doc_count": 2,
            "best_overlap_count": 2,
            "top_rrf_score": 0.031,
        },
    )


def test_manual_context_strength_rejects_missing_context():
    assert not has_strong_manual_context(
        False,
        _docs(3),
        quality_stats={
            "query_token_count": 6,
            "reliable_doc_count": 3,
            "best_overlap_count": 3,
            "top_rrf_score": 0.06,
        },
    )
