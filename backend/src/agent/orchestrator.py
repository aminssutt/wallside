"""High-level orchestration: ties planner, tools and responder together.

Public entry points
-------------------
* ``run_agent`` — synchronous end-to-end run. Returns ``AgentAnswer``.
* ``stream_agent`` — generator of streaming events
  (``{'type': 'status' | 'chunk' | 'end', ...}``) for SSE endpoints.

Both are thin: they delegate to ``planner.plan_tool_calls``,
``tools.run_tools_in_parallel`` and ``responder.*``. Keep this file small.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, TYPE_CHECKING

from .planner import plan_tool_calls
from .responder import (
    collect_citations,
    compose_answer,
    render_sources_block,
    stream_answer,
)
from .safety import SafetyVerdict, assess_input_safety
from .tools import Citation, ToolCall, ToolResult, run_tools_in_parallel

if TYPE_CHECKING:  # pragma: no cover
    from ..guide_chatbot import GuideChatbot

log = logging.getLogger("auris.agent.orchestrator")


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AgentAnswer:
    """Final bundle returned to the API layer."""

    answer: str
    sources_block: str
    citations: List[Citation]
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    timings_ms: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources_block": self.sources_block,
            "sources": [c.__dict__ for c in self.citations],
            "tool_calls": [{"name": c.name, "args": c.args} for c in self.tool_calls],
            "timings_ms": self.timings_ms,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_history_block(history: List[dict], max_messages: int = 6) -> str:
    if not history:
        return ""
    recent = history[-max_messages:]
    lines: List[str] = []
    for message in recent:
        role_raw = str(message.get("role", "user")).lower()
        role = "User" if role_raw == "user" else "Assistant"
        content = str(message.get("content", "")).strip().replace("\n", " ")
        if content:
            lines.append(f"{role}: {content[:400]}")
    return "\n".join(lines)


def _save_history(chatbot: "GuideChatbot", session_id: str, question: str, answer: str) -> None:
    history = chatbot._get_session_history(session_id)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    chatbot._trim_session_history(session_id)


# ---------------------------------------------------------------------------
# Synchronous flow
# ---------------------------------------------------------------------------

def run_agent(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> AgentAnswer:
    """End-to-end run: safety triage → plan → tools → answer."""
    timings: dict = {}
    t0 = time.perf_counter()

    history = chatbot._get_session_history(session_id)
    history_block = _build_history_block(history)

    # --- Stage 0: safety triage --------------------------------------------
    verdict = assess_input_safety(
        question,
        vehicle_name=chatbot.guide.name,
        lang=lang,
    )
    if verdict.refused:
        log.info(
            "agent refusal slug=%s reason=%s",
            chatbot.guide.slug,
            verdict.reason,
        )
        timings["total_ms"] = int((time.perf_counter() - t0) * 1000)
        _save_history(chatbot, session_id, question, verdict.refusal_message)
        return AgentAnswer(
            answer=verdict.refusal_message,
            sources_block="",
            citations=[],
            tool_calls=[],
            tool_results=[],
            timings_ms=timings,
        )

    # --- Stage 1: planner ---------------------------------------------------
    plan_started = time.perf_counter()
    tool_calls = plan_tool_calls(
        chatbot.client,
        question=question,
        vehicle_name=chatbot.guide.name,
        lang=lang,
        history_block=history_block,
        default_model=chatbot.model_name,
        safety_notice=verdict.soft_notice,
    )
    timings["plan_ms"] = int((time.perf_counter() - plan_started) * 1000)

    # --- Stage 2: tools in parallel -----------------------------------------
    tools_started = time.perf_counter()
    tool_results = run_tools_in_parallel(chatbot, tool_calls)
    timings["tools_ms"] = int((time.perf_counter() - tools_started) * 1000)

    # --- Stage 3: responder -------------------------------------------------
    respond_started = time.perf_counter()
    try:
        answer = compose_answer(
            chatbot.client,
            model=chatbot.model_name,
            vehicle_name=chatbot.guide.name,
            lang=lang,
            question=question,
            history_block=history_block,
            tool_results=tool_results,
            safety_notice=verdict.soft_notice,
        )
    except Exception as exc:
        log.error("Responder failed for %s: %s", chatbot.guide.slug, exc)
        answer = ""
    timings["respond_ms"] = int((time.perf_counter() - respond_started) * 1000)

    if not answer.strip():
        answer = "Je n'ai pas pu generer de reponse. Veuillez reessayer."

    citations = collect_citations(tool_results)
    sources_block = render_sources_block(citations)

    timings["total_ms"] = int((time.perf_counter() - t0) * 1000)
    log.info(
        "agent run slug=%s plan=%sms tools=%sms respond=%sms total=%sms tools=%s",
        chatbot.guide.slug,
        timings["plan_ms"],
        timings["tools_ms"],
        timings["respond_ms"],
        timings["total_ms"],
        [call.name for call in tool_calls],
    )

    _save_history(chatbot, session_id, question, answer)

    return AgentAnswer(
        answer=answer,
        sources_block=sources_block,
        citations=citations,
        tool_calls=tool_calls,
        tool_results=tool_results,
        timings_ms=timings,
    )


# ---------------------------------------------------------------------------
# Streaming flow
# ---------------------------------------------------------------------------

def stream_agent(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> Iterator[dict]:
    """Yield SSE-friendly events as the agent progresses.

    Event types:
    * ``{"type": "status", "step": "planning" | "searching" | "generating"}``
    * ``{"type": "chunk", "text": "..."}``
    * ``{"type": "end", "answer": "...", "sources_block": "...",
         "sources": [...], "tool_calls": [...], "timings_ms": {...}}``
    """
    history = chatbot._get_session_history(session_id)
    history_block = _build_history_block(history)
    timings: dict = {}
    t0 = time.perf_counter()

    # --- Safety triage first ---------------------------------------------
    verdict = assess_input_safety(
        question,
        vehicle_name=chatbot.guide.name,
        lang=lang,
    )
    if verdict.refused:
        log.info(
            "agent stream refusal slug=%s reason=%s",
            chatbot.guide.slug,
            verdict.reason,
        )
        yield {"type": "chunk", "text": verdict.refusal_message}
        _save_history(chatbot, session_id, question, verdict.refusal_message)
        yield {
            "type": "end",
            "answer": verdict.refusal_message,
            "sources_block": "",
            "sources": [],
            "tool_calls": [],
            "timings_ms": {"total_ms": int((time.perf_counter() - t0) * 1000)},
            "refusal_reason": verdict.reason,
        }
        return

    slug = chatbot.guide.slug
    log.info("[AGENT %s] START question=%r lang=%s", slug, question[:80], lang)

    yield {"type": "status", "step": "planning"}
    plan_started = time.perf_counter()
    log.info("[AGENT %s] planner CALL model=%s", slug, chatbot.model_name)
    tool_calls = plan_tool_calls(
        chatbot.client,
        question=question,
        vehicle_name=chatbot.guide.name,
        lang=lang,
        history_block=history_block,
        default_model=chatbot.model_name,
        safety_notice=verdict.soft_notice,
    )
    timings["plan_ms"] = int((time.perf_counter() - plan_started) * 1000)
    log.info(
        "[AGENT %s] planner DONE %dms -> %d calls: %s",
        slug,
        timings["plan_ms"],
        len(tool_calls),
        [c.name for c in tool_calls],
    )

    yield {
        "type": "status",
        "step": "searching",
        "tool_calls": [{"name": call.name, "args": call.args} for call in tool_calls],
    }
    tools_started = time.perf_counter()
    log.info("[AGENT %s] tools CALL %s", slug, [c.name for c in tool_calls])
    tool_results = run_tools_in_parallel(chatbot, tool_calls)
    timings["tools_ms"] = int((time.perf_counter() - tools_started) * 1000)
    log.info(
        "[AGENT %s] tools DONE %dms -> %s",
        slug,
        timings["tools_ms"],
        [f"{r.name}:ok={r.ok}" for r in tool_results],
    )

    yield {"type": "status", "step": "generating"}

    pieces: List[str] = []
    respond_started = time.perf_counter()
    log.info("[AGENT %s] responder CALL model=%s", slug, chatbot.model_name)
    try:
        first_chunk_at = None
        chunk_count = 0
        for delta in stream_answer(
            chatbot.client,
            model=chatbot.model_name,
            vehicle_name=chatbot.guide.name,
            lang=lang,
            question=question,
            history_block=history_block,
            tool_results=tool_results,
            safety_notice=verdict.soft_notice,
        ):
            if first_chunk_at is None:
                first_chunk_at = time.perf_counter() - respond_started
                log.info(
                    "[AGENT %s] responder FIRST-CHUNK %dms",
                    slug,
                    int(first_chunk_at * 1000),
                )
            chunk_count += 1
            pieces.append(delta)
            yield {"type": "chunk", "text": delta}
        log.info(
            "[AGENT %s] responder STREAM-END %d chunks", slug, chunk_count,
        )
    except Exception as exc:
        log.error("[AGENT %s] responder CRASH: %s", slug, exc)
    timings["respond_ms"] = int((time.perf_counter() - respond_started) * 1000)
    log.info("[AGENT %s] responder DONE %dms", slug, timings["respond_ms"])

    answer = "".join(pieces).strip()
    if not answer:
        fallback = "Je n'ai pas pu generer de reponse. Veuillez reessayer."
        yield {"type": "chunk", "text": fallback}
        answer = fallback

    citations = collect_citations(tool_results)
    sources_block = render_sources_block(citations)
    timings["total_ms"] = int((time.perf_counter() - t0) * 1000)

    _save_history(chatbot, session_id, question, answer)

    log.info(
        "agent stream slug=%s plan=%sms tools=%sms respond=%sms total=%sms tools=%s",
        chatbot.guide.slug,
        timings["plan_ms"],
        timings["tools_ms"],
        timings["respond_ms"],
        timings["total_ms"],
        [call.name for call in tool_calls],
    )

    yield {
        "type": "end",
        "answer": answer,
        "sources_block": sources_block,
        "sources": [c.__dict__ for c in citations],
        "tool_calls": [{"name": call.name, "args": call.args} for call in tool_calls],
        "timings_ms": timings,
    }
