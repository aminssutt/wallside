import os
import sys
import time
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))

os.environ.setdefault("GOOGLE_API_KEY", "test-key")

from src import guide_chatbot  # noqa: E402


def test_run_with_hard_timeout_returns_fallback_fast():
    started = time.perf_counter()
    result = guide_chatbot._run_with_hard_timeout(
        lambda: (time.sleep(0.5), ["ok"])[1],
        timeout_seconds=0.08,
        fallback=[],
        label="unit-timeout",
    )
    elapsed = time.perf_counter() - started

    assert result == []
    assert elapsed < 0.3


def test_bounded_web_search_respects_hard_timeout(monkeypatch):
    def _slow_search(query, max_results=3, time_budget_seconds=1.0):
        time.sleep(0.5)
        return [{"title": "X", "url": "https://example.com", "domain": "example.com"}]

    monkeypatch.setattr(guide_chatbot, "web_search_results", _slow_search)

    started = time.perf_counter()
    result = guide_chatbot._bounded_web_search_results(
        "bmw speed limiter",
        max_results=3,
        time_budget_seconds=0.2,
        hard_timeout_seconds=0.1,
        label="unit-bounded-search",
    )
    elapsed = time.perf_counter() - started

    assert result == []
    assert elapsed < 0.35
