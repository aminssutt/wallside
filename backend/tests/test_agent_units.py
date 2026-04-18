"""Unit tests for the agent orchestration primitives.

These tests exercise every piece of the agent that does NOT require a live
Gemini API call: tool dispatch, citation aggregation, evidence rendering
and deterministic fallbacks. The LLM-bound pieces (planner, responder)
are exercised end-to-end in integration smoke scripts, not here.

Run with:

    python -m pytest backend/tests/test_agent_units.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.agent.responder import (
    build_evidence_block,
    collect_citations,
    render_sources_block,
)
from src.agent.tools import Citation, ToolCall, ToolResult, run_tools_in_parallel


# ---------------------------------------------------------------------------
# Fixtures (module-level factories — cheaper than pytest fixtures here)
# ---------------------------------------------------------------------------

def _manual_result() -> ToolResult:
    return ToolResult(
        name="search_manual",
        ok=True,
        summary="Found 2 passages",
        payload={"chunks": [
            {"source_file": "manual.pdf", "page": "42", "text": "Tire pressure: 2.3 bar front, 2.1 rear."},
            {"source_file": "manual.pdf", "page": "43", "text": "Check pressure cold before driving."},
        ]},
        citations=[
            Citation(kind="manual", label="manual.pdf, page 42", source_file="manual.pdf", page="42"),
        ],
    )


def _web_result() -> ToolResult:
    return ToolResult(
        name="search_web",
        ok=True,
        summary="2 results",
        payload={"results": [
            {
                "title": "Renault Clio recalls 2022",
                "url": "https://rappel.conso.gouv.fr/x",
                "domain": "rappel.conso.gouv.fr",
                "snippet": "Official recall list...",
            },
        ]},
        citations=[
            Citation(
                kind="web",
                label="Renault Clio recalls 2022 (rappel.conso.gouv.fr)",
                url="https://rappel.conso.gouv.fr/x",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Evidence block
# ---------------------------------------------------------------------------

def test_evidence_block_contains_each_tool_type():
    evidence = build_evidence_block([_manual_result(), _web_result()])
    assert "MANUAL EVIDENCE" in evidence
    assert "WEB EVIDENCE" in evidence
    assert "Tire pressure" in evidence
    assert "rappel.conso.gouv.fr" in evidence


def test_evidence_block_when_every_tool_failed():
    evidence = build_evidence_block([])
    assert "EVIDENCE: none" in evidence


def test_failed_tool_is_excluded_from_evidence():
    broken = ToolResult(
        name="search_web",
        ok=False,
        summary="web boom",
        error="timeout",
    )
    evidence = build_evidence_block([_manual_result(), broken])
    assert "WEB EVIDENCE" not in evidence
    assert "MANUAL EVIDENCE" in evidence


# ---------------------------------------------------------------------------
# Citation pipeline
# ---------------------------------------------------------------------------

def test_collect_citations_dedupes_across_results():
    double = ToolResult(
        name="search_manual",
        ok=True,
        summary="",
        citations=[Citation(kind="manual", label="m.pdf, p.1", source_file="m.pdf", page="1")] * 3,
    )
    assert len(collect_citations([double])) == 1


def test_collect_citations_skips_failed_tools():
    bad = ToolResult(
        name="search_web",
        ok=False,
        summary="",
        error="boom",
        citations=[Citation(kind="web", label="x", url="u")],
    )
    assert collect_citations([bad]) == []


def test_render_sources_block_is_empty_when_no_citations():
    assert render_sources_block([]) == ""


def test_render_sources_block_formats_all_kinds():
    citations = [
        Citation(kind="manual", label="m.pdf, page 12", source_file="m.pdf", page="12"),
        Citation(kind="web", label="Title", url="https://example.com"),
        Citation(kind="youtube", label="Tutorial", url="https://youtu.be/abc"),
    ]
    block = render_sources_block(citations)
    assert "Manual: m.pdf, page 12" in block
    assert "Web: Title - https://example.com" in block
    assert "YouTube: Tutorial - https://youtu.be/abc" in block


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def test_unknown_tool_returns_failed_result_without_raising():
    calls = [ToolCall(name="does_not_exist", args={})]
    results = run_tools_in_parallel(None, calls)  # type: ignore[arg-type]
    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error == "unknown_tool"


def test_empty_call_list_returns_empty_results():
    assert run_tools_in_parallel(None, []) == []  # type: ignore[arg-type]
