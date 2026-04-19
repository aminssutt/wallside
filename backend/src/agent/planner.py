"""Planner prompt + response parsing helpers.

The async agent in :mod:`.async_pipeline` handles the actual Gemini call.
This module owns the planner system prompt, the model-name resolver, and
the response parser / default-plan fallback.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from .schemas import TOOL_NAMES
from .tools import ToolCall

log = logging.getLogger("auris.agent.planner")


# Small, fast model for planning. Falls back to the main model if the
# planner-specific env var is not set, so deployments without a secondary
# model continue to work.
def _resolve_planner_model(default_model: str) -> str:
    env_value = os.getenv("LLM_PLANNER_MODEL", "").strip()
    model = env_value or default_model
    return model.replace("models/", "", 1)


_PLANNER_SYSTEM_PROMPT = (
    "You are the PLANNING brain of an automotive assistant dedicated to a "
    "single vehicle. Your only job is to choose which tools to call to "
    "gather enough evidence to answer the user's question.\n\n"
    "Rules:\n"
    "1. Always call search_manual first for factual vehicle questions.\n"
    "2. Call search_web in parallel when the question is likely outside the "
    "owner's manual (recalls, known bugs, community fixes, real-world "
    "prices, regulations, or anything time-sensitive). The tool already "
    "boosts manufacturer sites (audi.fr, bmw.com, hyundai.co.kr...) — you "
    "don't need to add site: yourself.\n"
    "3. You MAY emit up to TWO search_web calls when a second angle would "
    "clearly help: e.g. one in English using the technical term "
    "('towing capacity') PLUS one in the user's language using local "
    "wording ('capacité de remorquage'). Pass the ``language`` argument "
    "('en', 'fr', 'ko', ...) so each query is routed to the right region.\n"
    "4. Call search_youtube only when the user asks how to perform a "
    "hands-on procedure or when a walkthrough clearly helps. YouTube "
    "stays worldwide by default — no need to force a language.\n"
    "5. Skip tools that make no sense: do NOT call any tool for pure "
    "greetings ('hi', 'thanks') or pure meta questions about your "
    "capabilities.\n"
    "6. You may call at most 4 tool invocations in total across all "
    "tools. Prefer fewer when the manual alone is likely sufficient.\n"
    "7. Reformulate queries so they are specific: always include the vehicle "
    "make and model in web/youtube queries."
)


def _extract_tool_calls(response: Any) -> List[ToolCall]:
    calls: List[ToolCall] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            fn = getattr(part, "function_call", None)
            if not fn:
                continue
            name = getattr(fn, "name", "") or ""
            raw_args = getattr(fn, "args", {}) or {}
            args: Dict[str, Any] = dict(raw_args) if raw_args else {}
            if name in TOOL_NAMES:
                calls.append(ToolCall(name=name, args=args))
    return calls


def _default_plan(question: str) -> List[ToolCall]:
    """Safe fallback when the planner fails or produces nothing.

    Always searches the manual with the raw question. The responder will
    still get a chance to answer from whatever that returns, and the
    orchestrator can trigger a web follow-up if the responder refuses.
    """
    return [ToolCall(name="search_manual", args={"query": question.strip()[:120]})]
