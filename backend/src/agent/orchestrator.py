"""Public orchestrator surface — thin sync bridge over the async pipeline.

The actual orchestration lives in :mod:`.async_pipeline`. This module
re-exports the blocking + generator entry points that the rest of the
codebase expects:

* ``run_agent`` — end-to-end run returning :class:`AgentAnswer`.
* ``stream_agent`` — generator of SSE-friendly event dicts.

Both are implemented by calling the async pipeline under the hood:
``run_agent`` via :func:`asyncio.run`, ``stream_agent`` via a single
bridge thread that drives an event loop and republishes events.
"""
from __future__ import annotations

from typing import Iterator, TYPE_CHECKING

from .async_pipeline import (
    AgentAnswer,
    run_agent_sync,
    stream_agent_sync,
)
# Re-export the support classes that external callers still reach for
# (``from .agent import Citation, ToolCall, ToolResult, assess_input_safety``).
from .safety import SafetyVerdict, assess_input_safety  # noqa: F401
from .tools import Citation, ToolCall, ToolResult  # noqa: F401

# Preserve the legacy internal names used by a handful of tests.
from .planner import plan_tool_calls  # noqa: F401
from .responder import (  # noqa: F401
    collect_citations,
    compose_answer,
    render_sources_block,
    stream_answer,
)
from .tools import run_tools_in_parallel  # noqa: F401

if TYPE_CHECKING:  # pragma: no cover
    from ..guide_chatbot import GuideChatbot


def run_agent(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> AgentAnswer:
    """Blocking end-to-end agent run (plan → tools → answer)."""
    return run_agent_sync(
        chatbot, question=question, lang=lang, session_id=session_id,
    )


def stream_agent(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> Iterator[dict]:
    """Yield ``{'type': 'status' | 'chunk' | 'end', ...}`` events.

    Event shape matches the contract consumed by ``bridge.py``:
    * ``status``: ``{type, step, tool_calls?}``
    * ``chunk``: ``{type, text}``
    * ``end``: ``{type, answer, sources_block, sources, tool_calls, timings_ms, refusal_reason?}``
    """
    yield from stream_agent_sync(
        chatbot, question=question, lang=lang, session_id=session_id,
    )


__all__ = [
    "AgentAnswer",
    "Citation",
    "SafetyVerdict",
    "ToolCall",
    "ToolResult",
    "assess_input_safety",
    "run_agent",
    "stream_agent",
    # Legacy internals kept for test coverage
    "collect_citations",
    "compose_answer",
    "plan_tool_calls",
    "render_sources_block",
    "run_tools_in_parallel",
    "stream_answer",
]
