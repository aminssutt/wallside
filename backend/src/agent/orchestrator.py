"""Public orchestrator surface — thin sync bridge over the async pipeline.

The actual orchestration lives in :mod:`.async_pipeline`. This module
re-exports the blocking + generator entry points the rest of the
codebase expects:

* ``run_agent`` — blocking end-to-end run returning :class:`AgentAnswer`.
* ``stream_agent`` — generator of SSE-friendly event dicts.
"""
from __future__ import annotations

from typing import Iterator, TYPE_CHECKING

from .async_pipeline import (
    AgentAnswer,
    run_agent_sync,
    stream_agent_sync,
)
from .safety import SafetyVerdict, assess_input_safety  # noqa: F401
from .tools import Citation, ToolCall, ToolResult  # noqa: F401

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
    """Yield ``{'type': 'status' | 'chunk' | 'end', ...}`` events."""
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
]
