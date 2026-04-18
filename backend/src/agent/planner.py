"""Planner stage of the agent.

Given the user question, the guide metadata and the recent history, ask a
small Gemini model to choose which tools to invoke and with what arguments.

Latency budget: ~600-1200 ms. We use a compact prompt and force the model
into tool-call mode so the response is deterministic JSON rather than prose.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from google.genai import types as genai_types

from ..config import LLM_TIMEOUT_SECONDS
from .safety import SAFETY_GUARDRAIL
from .schemas import TOOL_NAMES, build_tool_declarations
from .tools import ToolCall

if TYPE_CHECKING:  # pragma: no cover
    from google.genai import Client as GenAIClient

log = logging.getLogger("auris.agent.planner")


# Small, fast model for planning. Falls back to the main model if the
# planner-specific env var is not set, so deployments without a secondary
# model continue to work.
def _resolve_planner_model(default_model: str) -> str:
    import os
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


def plan_tool_calls(
    client: "GenAIClient",
    *,
    question: str,
    vehicle_name: str,
    lang: str,
    history_block: str,
    default_model: str,
    timeout_seconds: Optional[int] = None,
    safety_notice: str = "",
) -> List[ToolCall]:
    """Ask the planner model which tools to run.

    Returns an ordered list of tool calls. An empty list is a valid outcome
    and means the responder should answer from history alone (e.g. for
    a pure greeting).

    ``safety_notice`` is injected into the planner system prompt when the
    safety triage flagged soft-injection hints in the user question.
    """
    model = _resolve_planner_model(default_model)
    tools = build_tool_declarations()

    lang_hint = {
        "fr": "The user writes in French.",
        "en": "The user writes in English.",
        "ko": "The user writes in Korean.",
    }.get(lang, "The user may write in French, English or Korean.")

    history_line = (
        f"Recent conversation (most recent last):\n{history_block}"
        if history_block
        else "No prior conversation."
    )

    system_instruction = _PLANNER_SYSTEM_PROMPT + SAFETY_GUARDRAIL
    if safety_notice:
        system_instruction += f"\n\n{safety_notice}"

    prompt = (
        f"Vehicle: {vehicle_name}\n"
        f"{lang_hint}\n"
        f"{history_line}\n\n"
        f"User question: {question}\n\n"
        "Choose the tool calls that will gather the evidence needed to "
        "answer. Return only function calls — no prose."
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0,
                tools=tools,
                tool_config=genai_types.ToolConfig(
                    function_calling_config=genai_types.FunctionCallingConfig(
                        mode="ANY",
                        allowed_function_names=list(TOOL_NAMES),
                    ),
                ),
                http_options=genai_types.HttpOptions(
                    timeout=(timeout_seconds or LLM_TIMEOUT_SECONDS) * 1000,
                ),
            ),
        )
    except Exception as exc:
        log.warning("Planner call failed (model=%s): %s", model, exc)
        return _default_plan(question)

    calls = _extract_tool_calls(response)
    if not calls:
        log.info("Planner returned no tool calls; falling back to default plan.")
        return _default_plan(question)

    # Hard cap at 4 calls to protect latency even if the planner over-asks.
    # The responder prompt assumes we never fan out too far.
    return calls[:4]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
