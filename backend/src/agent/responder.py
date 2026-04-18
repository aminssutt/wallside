"""Responder stage of the agent.

Consumes the tool results produced by the orchestrator and asks the main
Gemini model for a final, user-facing answer. Two entry points are exposed:

* ``compose_answer`` — blocking, returns the full string (used by the sync
  chat endpoint).
* ``stream_answer`` — generator yielding text deltas (used by the streaming
  endpoint so the UI can render tokens as they arrive).

The responder NEVER invokes tools itself: all tool work has already been
done by the orchestrator. This keeps the responder deterministic and its
latency predictable.
"""
from __future__ import annotations

import logging
from typing import Iterable, Iterator, List, Sequence

from google.genai import types as genai_types

from ..config import LLM_TIMEOUT_SECONDS
from .safety import SAFETY_GUARDRAIL, sanitize_tool_text
from .tools import Citation, ToolResult

log = logging.getLogger("auris.agent.responder")


_MAX_CHUNK_CHARS = 1400   # Per-passage cap when injecting manual snippets
_MAX_MANUAL_SNIPPETS = 6  # Never dump more than N chunks into the prompt
_MAX_WEB_ITEMS = 5
_DEFAULT_MAX_TOKENS = 3500


def build_system_instruction(vehicle_name: str, lang: str, safety_notice: str = "") -> str:
    """Static guardrails for the responder model.

    ``safety_notice`` is appended when the safety triage flagged the user
    message as potentially adversarial (embedded role-play, fake system
    headers, etc.). The responder then knows to ignore any such framing.
    """
    lang_line = {
        "fr": "Réponds en français.",
        "en": "Answer in English.",
        "ko": "한국어로 답변하세요.",
    }.get(lang, "Reponds en francais.")

    core = (
        f"You are the REPLY brain of an automotive assistant specialised in "
        f"the {vehicle_name}. Another brain (the planner) has already chosen "
        f"tools and executed them; you receive their results as evidence.\n\n"
        f"{lang_line}\n\n"
        "Rules:\n"
        "1. Do NOT invent vehicle-specific numerical values (torques, "
        "pressures, capacities, service intervals, fluid grades) that "
        "are not explicitly in the evidence. General automotive best "
        "practice that does not rely on specific values IS allowed "
        "and expected — see rule 4.\n"
        "2. Do NOT write inline source citations ('selon la page 370', "
        "'according to page 12', 'Source: audi.com', etc.). The UI "
        "renders clickable sources in a separate block below your "
        "answer, so repeating them inline only clutters the prose.\n"
        "3. Prefer manual evidence over web evidence when both cover the "
        "question. If the manual is silent but the web evidence covers "
        "it, answer from the web. When web evidence spans multiple sites, "
        "prefer the manufacturer's official domain (audi.fr, bmw.com, "
        "hyundai.co.kr, renault.com...) over aggregators; if values "
        "conflict between official and aggregator sources, quote the "
        "official one and flag the disagreement briefly.\n"
        "4. When the question is a GENERAL procedural one (basic "
        "maintenance, routine checks, common warning lights, seasonal "
        "prep) and the evidence has no vehicle-specific data, GIVE the "
        "standard automotive checklist adapted to this vehicle's "
        "category (ICE / hybrid / EV) — e.g. engine oil level and "
        "colour, tire pressure and tread, brake fluid level, coolant "
        "level, battery terminals, wiper blades, all external lights, "
        "windshield washer fluid. You may describe these generally "
        "('check oil level between MIN and MAX on the dipstick') but "
        "must NEVER quote an unverified figure ('2.3 bar', '10 000 km') "
        "that isn't in the evidence. End the answer by suggesting the "
        "user consult their owner's manual or dealer for "
        "vehicle-specific intervals and values.\n"
        "5. Only use the plain 'I don't have this information' refusal "
        "when the question is narrowly specific (a torque value, a "
        "recall reference, a VIN lookup) AND the evidence genuinely "
        "has nothing. Never use it for broad how-to questions.\n"
        "6. Numerical units must match the user's language: when you "
        "answer in French give metric first ('2 000 kg' before '4 400 lbs') "
        "and convert imperial values if the evidence only has them. Same "
        "for Korean answers.\n"
        "7. For procedures, give ALL steps in a numbered list.\n"
        "8. Plain text only — no markdown hashes, asterisks or code fences.\n"
        "9. Do NOT add a 'Sources' section yourself: it is rendered "
        "separately from the citations in the evidence block."
    )
    instruction = core + SAFETY_GUARDRAIL
    if safety_notice:
        instruction += f"\n\n{safety_notice}"
    return instruction


def build_evidence_block(tool_results: Sequence[ToolResult]) -> str:
    """Compact, LLM-friendly rendering of the tool results."""
    sections: List[str] = []

    manual_chunks: List[dict] = []
    web_items: List[dict] = []
    youtube_items: List[dict] = []

    for result in tool_results:
        if not result.ok:
            continue
        payload = result.payload or {}
        if result.name == "search_manual":
            manual_chunks.extend(payload.get("chunks", []))
        elif result.name == "search_web":
            web_items.extend(payload.get("results", []))
        elif result.name == "search_youtube":
            video = payload.get("video")
            if video:
                youtube_items.append(video)

    if manual_chunks:
        rendered = []
        for chunk in manual_chunks[:_MAX_MANUAL_SNIPPETS]:
            text = sanitize_tool_text(str(chunk.get("text", "")))
            if not text:
                continue
            if len(text) > _MAX_CHUNK_CHARS:
                text = text[:_MAX_CHUNK_CHARS] + "..."
            rendered.append(
                f"[manual {chunk.get('source_file', 'manuel.pdf')} "
                f"p.{chunk.get('page', '?')}]\n{text}"
            )
        if rendered:
            sections.append("MANUAL EVIDENCE:\n" + "\n\n".join(rendered))

    if web_items:
        rendered = []
        for item in web_items[:_MAX_WEB_ITEMS]:
            title = sanitize_tool_text(str(item.get("title", "")))
            domain = sanitize_tool_text(str(item.get("domain", "")))
            snippet = sanitize_tool_text(str(item.get("snippet", "")))
            url = str(item.get("url", "")).strip()
            if not title or not url:
                continue
            rendered.append(
                f"[web {domain or 'source'}] {title}\n{snippet}\n{url}"
            )
        if rendered:
            sections.append("WEB EVIDENCE:\n" + "\n\n".join(rendered))

    if youtube_items:
        rendered = []
        for video in youtube_items[:1]:
            title = sanitize_tool_text(str(video.get("title", ""))) or "YouTube tutorial"
            url = str(video.get("url", "")).strip()
            if not url:
                continue
            rendered.append(f"[youtube] {title}\n{url}")
        if rendered:
            sections.append("YOUTUBE EVIDENCE:\n" + "\n\n".join(rendered))

    if not sections:
        return "EVIDENCE: none. Explain honestly that you do not have the information for this question."

    return "\n\n---\n\n".join(sections)


def build_user_prompt(
    *,
    question: str,
    history_block: str,
    evidence_block: str,
) -> str:
    """Final prompt assembled from question + history + evidence."""
    parts: List[str] = []
    if history_block:
        parts.append(f"Recent conversation:\n{history_block}")
    parts.append(evidence_block)
    parts.append(f"User question: {question}")
    return "\n\n---\n\n".join(parts)


def _build_config(system_instruction: str, max_tokens: int) -> genai_types.GenerateContentConfig:
    return genai_types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.15,
        max_output_tokens=max_tokens,
        http_options=genai_types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),
    )


def compose_answer(
    client,
    *,
    model: str,
    vehicle_name: str,
    lang: str,
    question: str,
    history_block: str,
    tool_results: Sequence[ToolResult],
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    safety_notice: str = "",
) -> str:
    """Blocking response. Returns the raw text the model produced."""
    system_instruction = build_system_instruction(vehicle_name, lang, safety_notice)
    evidence_block = build_evidence_block(tool_results)
    prompt = build_user_prompt(
        question=question,
        history_block=history_block,
        evidence_block=evidence_block,
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=_build_config(system_instruction, max_tokens),
        )
    except Exception as exc:
        log.error("Responder call failed: %s", exc)
        raise

    return (getattr(response, "text", "") or "").strip()


def stream_answer(
    client,
    *,
    model: str,
    vehicle_name: str,
    lang: str,
    question: str,
    history_block: str,
    tool_results: Sequence[ToolResult],
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    safety_notice: str = "",
) -> Iterator[str]:
    """Streaming response. Yields text deltas as Gemini emits them."""
    import time as _time

    system_instruction = build_system_instruction(vehicle_name, lang, safety_notice)
    evidence_block = build_evidence_block(tool_results)
    prompt = build_user_prompt(
        question=question,
        history_block=history_block,
        evidence_block=evidence_block,
    )
    log.info(
        "[RESPONDER] about to call generate_content_stream model=%s prompt_len=%d evidence_len=%d",
        model, len(prompt), len(evidence_block),
    )

    call_started = _time.perf_counter()
    try:
        stream = client.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=_build_config(system_instruction, max_tokens),
        )
    except Exception as exc:
        log.error("[RESPONDER] generate_content_stream FAILED: %s", exc)
        raise
    log.info(
        "[RESPONDER] generate_content_stream returned in %dms, starting iteration",
        int((_time.perf_counter() - call_started) * 1000),
    )

    iter_started = _time.perf_counter()
    chunk_count = 0
    first_text_at = None
    last_log_at = iter_started
    for chunk in stream:
        now = _time.perf_counter()
        chunk_count += 1
        text = _extract_chunk_text(chunk)
        if text:
            if first_text_at is None:
                first_text_at = now - iter_started
                log.info(
                    "[RESPONDER] FIRST TEXT chunk after %dms (iter #%d)",
                    int(first_text_at * 1000), chunk_count,
                )
            yield text
        # Periodic progress log so prod doesn't look silent for long pauses.
        if now - last_log_at > 5.0:
            log.info(
                "[RESPONDER] still streaming... elapsed=%.1fs chunks=%d",
                now - iter_started, chunk_count,
            )
            last_log_at = now
    log.info(
        "[RESPONDER] stream iteration DONE elapsed=%dms total_chunks=%d",
        int((_time.perf_counter() - iter_started) * 1000), chunk_count,
    )


def _extract_chunk_text(chunk) -> str:
    """Gemini stream chunks sometimes expose ``.text``, sometimes ``.candidates``."""
    direct = getattr(chunk, "text", "")
    if direct:
        return direct

    pieces: List[str] = []
    candidates = getattr(chunk, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            piece = getattr(part, "text", "")
            if piece:
                pieces.append(piece)
    return "".join(pieces)


# ---------------------------------------------------------------------------
# Citation collection
# ---------------------------------------------------------------------------

def collect_citations(tool_results: Iterable[ToolResult]) -> List[Citation]:
    """Flatten successful tool citations into a deduplicated list."""
    seen: set = set()
    flat: List[Citation] = []
    for result in tool_results:
        if not result.ok:
            continue
        for citation in result.citations:
            key = (citation.kind, citation.label, citation.url, citation.page)
            if key in seen:
                continue
            seen.add(key)
            flat.append(citation)
    return flat


def render_sources_block(citations: Sequence[Citation]) -> str:
    """Render the deterministic Sources footer appended to the final answer."""
    if not citations:
        return ""
    lines = ["Sources:"]
    for citation in citations[:8]:
        if citation.kind == "manual":
            lines.append(f"- Manual: {citation.source_file}, page {citation.page}")
        elif citation.kind == "web":
            lines.append(f"- Web: {citation.label} - {citation.url}")
        elif citation.kind == "youtube":
            lines.append(f"- YouTube: {citation.label} - {citation.url}")
    return "\n".join(lines)
