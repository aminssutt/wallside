"""Tool dispatchers invoked by the agent orchestrator.

Each tool function takes a ``GuideChatbot`` context (to reach the vehicle
indices and the guide metadata) plus a dict of arguments produced by the
Gemini planner. Every tool returns a uniform ``ToolResult`` so the
orchestrator, responder and source-collector can treat results generically.

Design rules
------------
* Tools are pure functions: no global state, no hidden side effects.
* Every tool is defensive: a failing external call returns an empty result
  rather than raising, so the agent still produces an answer.
* Results expose ``citations`` so the responder can reference them in the
  final Sources block without re-running searches.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence, TYPE_CHECKING

from ..config import (
    ENRICHMENT_TIME_BUDGET_SECONDS,
    TOP_K_RESULTS,
    WEB_MAX_RESULTS,
)

if TYPE_CHECKING:  # pragma: no cover - type-only imports
    from ..guide_chatbot import GuideChatbot

log = logging.getLogger("auris.agent.tools")


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """Single citation that the responder can render in the Sources block."""

    kind: str            # "manual" | "web" | "youtube"
    label: str           # Human-readable label
    url: str = ""        # Optional URL (web / youtube)
    source_file: str = ""  # Manual file name (manual only)
    page: str = ""       # Manual page (manual only)


@dataclass
class ToolResult:
    """Uniform envelope returned by every tool."""

    name: str
    ok: bool
    summary: str                              # Natural-language summary for the responder
    payload: Dict[str, Any] = field(default_factory=dict)
    citations: List[Citation] = field(default_factory=list)
    error: str = ""

    def to_llm_content(self) -> Dict[str, Any]:
        """Serialise for the ``function_response`` turn sent back to Gemini."""
        return {
            "ok": self.ok,
            "summary": self.summary,
            "used_citations": [c.__dict__ for c in self.citations],
        }


# ---------------------------------------------------------------------------
# Individual tools
# ---------------------------------------------------------------------------

def _run_search_manual(chatbot: "GuideChatbot", args: Dict[str, Any]) -> ToolResult:
    """Hybrid FAISS + BM25 search scoped to the current guide."""
    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(
            name="search_manual",
            ok=False,
            summary="No query provided to search_manual.",
            error="empty_query",
        )

    try:
        result = chatbot._hybrid_search(query, k=TOP_K_RESULTS)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("search_manual failed for %s: %s", chatbot.guide.slug, exc)
        return ToolResult(
            name="search_manual",
            ok=False,
            summary="Internal error while searching the manual.",
            error=str(exc),
        )

    # _hybrid_search historically returned just the docs list; the current
    # implementation returns a (docs, quality_stats) tuple. Accept both so
    # the agent stays compatible across branches.
    if isinstance(result, tuple):
        docs = result[0] if result else []
    else:
        docs = result

    if not docs:
        return ToolResult(
            name="search_manual",
            ok=True,
            summary="Manual returned no passages for this query.",
            payload={"chunks": []},
        )

    chunks: List[Dict[str, str]] = []
    citations: List[Citation] = []
    seen: set = set()
    for doc in docs:
        source_file = str(doc.metadata.get("source_file", "manuel.pdf"))
        page = str(doc.metadata.get("page", "?"))
        chunks.append({
            "source_file": source_file,
            "page": page,
            "text": doc.page_content,
        })
        key = (source_file, page)
        if key in seen:
            continue
        seen.add(key)
        citations.append(Citation(
            kind="manual",
            label=f"{source_file}, page {page}",
            source_file=source_file,
            page=page,
        ))

    return ToolResult(
        name="search_manual",
        ok=True,
        summary=f"Found {len(chunks)} manual passages for: {query!r}.",
        payload={"chunks": chunks, "query": query},
        citations=citations,
    )


def _run_search_web(chatbot: "GuideChatbot", args: Dict[str, Any]) -> ToolResult:
    """DuckDuckGo-based web search using the existing helper."""
    from ..guide_chatbot import web_search_results  # avoid circular import at module load

    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(
            name="search_web",
            ok=False,
            summary="No query provided to search_web.",
            error="empty_query",
        )

    try:
        max_results = int(args.get("max_results") or WEB_MAX_RESULTS)
    except (TypeError, ValueError):
        max_results = WEB_MAX_RESULTS
    max_results = max(1, min(max_results, 8))

    try:
        results = web_search_results(
            query,
            max_results=max_results,
            time_budget_seconds=max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS),
        ) or []
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("search_web failed for %s: %s", query, exc)
        return ToolResult(
            name="search_web",
            ok=False,
            summary="Web search failed.",
            error=str(exc),
        )

    if not results:
        return ToolResult(
            name="search_web",
            ok=True,
            summary="Web search returned no usable results.",
            payload={"results": []},
        )

    citations: List[Citation] = []
    for item in results:
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        domain = str(item.get("domain", "")).strip()
        if not title or not url:
            continue
        citations.append(Citation(
            kind="web",
            label=f"{title} ({domain})" if domain else title,
            url=url,
        ))

    return ToolResult(
        name="search_web",
        ok=True,
        summary=f"Got {len(results)} web results for: {query!r}.",
        payload={"results": results, "query": query},
        citations=citations,
    )


def _run_search_youtube(chatbot: "GuideChatbot", args: Dict[str, Any]) -> ToolResult:
    """YouTube tutorial suggestion via the existing helper."""
    from ..guide_chatbot import youtube_video_suggestion  # avoid circular import

    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(
            name="search_youtube",
            ok=False,
            summary="No query provided to search_youtube.",
            error="empty_query",
        )

    try:
        video = youtube_video_suggestion(
            query,
            time_budget_seconds=max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS),
        ) or {}
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("search_youtube failed for %s: %s", query, exc)
        return ToolResult(
            name="search_youtube",
            ok=False,
            summary="YouTube search failed.",
            error=str(exc),
        )

    url = str(video.get("url", "")).strip()
    title = str(video.get("title", "")).strip() or "YouTube tutorial"
    if not url:
        return ToolResult(
            name="search_youtube",
            ok=True,
            summary="No relevant YouTube tutorial found.",
            payload={},
        )

    citation = Citation(kind="youtube", label=title, url=url)
    return ToolResult(
        name="search_youtube",
        ok=True,
        summary=f"Found YouTube tutorial: {title}.",
        payload={"video": video, "query": query},
        citations=[citation],
    )


_DISPATCH: Dict[str, Callable[["GuideChatbot", Dict[str, Any]], ToolResult]] = {
    "search_manual": _run_search_manual,
    "search_web": _run_search_web,
    "search_youtube": _run_search_youtube,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """Tool invocation requested by the planner."""

    name: str
    args: Dict[str, Any]


def run_tools_in_parallel(
    chatbot: "GuideChatbot",
    calls: Sequence[ToolCall],
    max_workers: int = 3,
) -> List[ToolResult]:
    """Execute a batch of tool calls concurrently.

    Unknown tool names produce a failed ``ToolResult`` rather than raising,
    so the agent can still hand off what succeeded to the responder.
    Results preserve the order of ``calls`` for deterministic citation
    numbering.
    """
    if not calls:
        return []

    results: List[ToolResult] = [None] * len(calls)  # type: ignore[assignment]
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(calls)))) as executor:
        future_to_index = {}
        for index, call in enumerate(calls):
            handler = _DISPATCH.get(call.name)
            if handler is None:
                results[index] = ToolResult(
                    name=call.name,
                    ok=False,
                    summary=f"Unknown tool: {call.name}",
                    error="unknown_tool",
                )
                continue
            future_to_index[executor.submit(handler, chatbot, call.args)] = index

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:  # pragma: no cover - defensive
                call = calls[index]
                log.exception("Tool %s crashed: %s", call.name, exc)
                results[index] = ToolResult(
                    name=call.name,
                    ok=False,
                    summary=f"Tool {call.name} crashed.",
                    error=str(exc),
                )

    return [r for r in results if r is not None]
