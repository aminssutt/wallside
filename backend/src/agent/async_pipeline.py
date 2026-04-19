"""Asyncio-native agent pipeline.

Replaces the previous threaded orchestration (ThreadPoolExecutor +
daemon-timeout threads + queue bridges) with a single asyncio event
loop per request. Benefits:

* ONE worker thread per request (not 8-10). No zombie accumulation.
* ``asyncio.wait_for`` gives real, structured timeouts. The underlying
  sync call (FAISS embedding, DDGS) still cannot be interrupted if it
  blocks on a socket — but only ONE default thread-pool slot is held
  instead of one PER-tool + one PER-hard-timeout.
* ``asyncio.gather`` cleanly fans out the parallel tool calls.
* Uses ``client.aio.models.generate_content_stream`` natively: no
  daemon thread is needed to drain the Gemini SDK iterator.

Public surface (consumed by ``orchestrator.py`` and ``__init__.py``):

* ``stream_agent_async(chatbot, question, lang, session_id)``
  — async generator of ``{'type': 'status' | 'chunk' | 'end', ...}``.
* ``stream_agent_sync(...)``
  — thin sync wrapper that runs ``stream_agent_async`` in a dedicated
  worker thread and yields events through a ``queue.Queue``. This is
  what the Flask SSE handler consumes.
* ``run_agent_async(...)`` / ``run_agent_sync(...)``
  — blocking variants that consume the stream and return an
  ``AgentAnswer`` once done.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Sequence, TYPE_CHECKING

from google.genai import types as genai_types

from ..config import (
    ENRICHMENT_TIME_BUDGET_SECONDS,
    LLM_TIMEOUT_SECONDS,
    TOP_K_RESULTS,
    WEB_MAX_RESULTS,
)
from .planner import _resolve_planner_model, _extract_tool_calls, _default_plan, _PLANNER_SYSTEM_PROMPT
from .responder import (
    _DEFAULT_MAX_TOKENS,
    _extract_chunk_text,
    build_evidence_block,
    build_system_instruction,
    build_user_prompt,
    collect_citations,
    render_sources_block,
)
from .safety import SAFETY_GUARDRAIL, assess_input_safety
from .schemas import TOOL_NAMES, build_tool_declarations
from .tools import (
    Citation,
    ToolCall,
    ToolResult,
    _OFFICIAL_DOMAINS,
    _region_for_lang,
    _slugify_brand,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..guide_chatbot import GuideChatbot

log = logging.getLogger("auris.agent.async")


# ---------------------------------------------------------------------------
# Timeouts (seconds) — single source of truth for the whole pipeline
# ---------------------------------------------------------------------------

_PLANNER_TIMEOUT = 15.0
_MANUAL_SEARCH_TIMEOUT = 10.0
_WEB_VARIANT_TIMEOUT = 5.0
_YOUTUBE_TIMEOUT = 6.0
_TOOLS_BATCH_TIMEOUT = 15.0     # whole gather() deadline
_RESPONDER_WALLCLOCK = 30.0     # total stream duration
_RESPONDER_FIRST_TOKEN = 10.0   # max wait for first chunk


# ---------------------------------------------------------------------------
# Public result container (kept identical to previous AgentAnswer)
# ---------------------------------------------------------------------------

@dataclass
class AgentAnswer:
    """Bundle returned by the blocking ``run_agent_sync`` entry point."""

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
# Internal helpers
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


def _official_domains_for(chatbot: "GuideChatbot") -> List[str]:
    brand_attr = getattr(getattr(chatbot, "guide", None), "brand", "") or ""
    return _OFFICIAL_DOMAINS.get(_slugify_brand(brand_attr), [])


# ---------------------------------------------------------------------------
# Planner (async)
# ---------------------------------------------------------------------------

async def _plan_async(
    client: Any,
    *,
    question: str,
    vehicle_name: str,
    lang: str,
    history_block: str,
    default_model: str,
    safety_notice: str = "",
) -> List[ToolCall]:
    """Ask the planner model which tools to run, via async Gemini API."""
    model = _resolve_planner_model(default_model)
    tools = build_tool_declarations()

    lang_hint = {
        "fr": "The user writes in French.",
        "en": "The user writes in English.",
        "ko": "The user writes in Korean.",
    }.get(lang, "The user may write in French, English or Korean.")
    history_line = (
        f"Recent conversation (most recent last):\n{history_block}"
        if history_block else "No prior conversation."
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

    config = genai_types.GenerateContentConfig(
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
            timeout=LLM_TIMEOUT_SECONDS * 1000,
        ),
    )

    # We deliberately call the SYNC API via ``asyncio.to_thread`` instead of
    # ``client.aio.*``: the async client caches an ``httpx.AsyncClient``
    # bound to the first event loop it runs in, so the second request with a
    # fresh ``asyncio.run()`` loop errors out with
    # "Executor shutdown has been called". The sync client is loop-agnostic
    # and just uses a blocking httpx call under the hood.
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=prompt,
                config=config,
            ),
            timeout=_PLANNER_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("planner timed out after %.0fs — falling back", _PLANNER_TIMEOUT)
        return _default_plan(question)
    except Exception as exc:
        log.warning("planner call failed (model=%s): %s", model, exc)
        return _default_plan(question)

    calls = _extract_tool_calls(response)
    if not calls:
        log.info("planner returned no tool calls — falling back")
        return _default_plan(question)
    return calls[:4]


# ---------------------------------------------------------------------------
# Tools (async)
# ---------------------------------------------------------------------------

async def _search_manual_async(chatbot: "GuideChatbot", args: Dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(name="search_manual", ok=False,
                          summary="No query provided.", error="empty_query")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(chatbot._hybrid_search, query, k=TOP_K_RESULTS),
            timeout=_MANUAL_SEARCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("search_manual timed out (%.0fs) slug=%s", _MANUAL_SEARCH_TIMEOUT, chatbot.guide.slug)
        return ToolResult(name="search_manual", ok=False,
                          summary="Manual search timed out.", error="timeout")
    except Exception as exc:
        log.warning("search_manual failed slug=%s: %s", chatbot.guide.slug, exc)
        return ToolResult(name="search_manual", ok=False,
                          summary="Manual search crashed.", error=str(exc))

    # _hybrid_search returns either a plain list of docs or a (docs, stats) tuple.
    docs = result[0] if isinstance(result, tuple) and result else (result or [])
    if not docs:
        return ToolResult(name="search_manual", ok=True,
                          summary="Manual returned no passages.",
                          payload={"chunks": []})

    chunks: List[Dict[str, str]] = []
    citations: List[Citation] = []
    seen: set = set()
    for doc in docs:
        source_file = str(doc.metadata.get("source_file", "manuel.pdf"))
        page = str(doc.metadata.get("page", "?"))
        chunks.append({"source_file": source_file, "page": page, "text": doc.page_content})
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
        name="search_manual", ok=True,
        summary=f"Found {len(chunks)} manual passages for: {query!r}.",
        payload={"chunks": chunks, "query": query},
        citations=citations,
    )


async def _search_web_async(chatbot: "GuideChatbot", args: Dict[str, Any]) -> ToolResult:
    from ..guide_chatbot import web_search_results

    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(name="search_web", ok=False,
                          summary="No query provided.", error="empty_query")

    try:
        max_results = int(args.get("max_results") or WEB_MAX_RESULTS)
    except (TypeError, ValueError):
        max_results = WEB_MAX_RESULTS
    max_results = max(1, min(max_results, 8))

    lang = str(args.get("language") or "").strip().lower() or None
    region = _region_for_lang(lang)

    # Fan out: generic + up to 3 site: variants, each with its own timeout.
    official = _official_domains_for(chatbot)
    query_variants: List[str] = [query]
    if official and "site:" not in query.lower():
        for domain in official[:3]:
            query_variants.append(f"{query} site:{domain}")

    budget = max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS)

    async def _one(q: str) -> List[Dict[str, str]]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    web_search_results, q,
                    max_results=max_results,
                    time_budget_seconds=budget,
                    region=region,
                ),
                timeout=_WEB_VARIANT_TIMEOUT,
            ) or []
        except asyncio.TimeoutError:
            return []
        except Exception as exc:
            log.warning("web variant failed q=%r: %s", q[:60], exc)
            return []

    # Serialize variants. Running them in parallel via gather under a
    # 1-CPU container caused the event loop to freeze with no timeout
    # firing — a chain of at most ~3 DDGS calls finishes in 3-6s total
    # and is far more predictable.
    results_by_variant: List[List[Dict[str, str]]] = []
    for variant in query_variants:
        items = await _one(variant)
        results_by_variant.append(items)
        # Early exit: stop fanning out as soon as we have 2 non-empty
        # result sets. The responder doesn't need every single angle.
        if sum(1 for r in results_by_variant if r) >= 2:
            break

    # Merge with per-domain cap for diversity; official variants first.
    seen_urls: set = set()
    domain_count: Dict[str, int] = {}
    merged: List[Dict[str, str]] = []

    def _ingest(items: List[Dict[str, str]], cap_per_domain: int) -> None:
        for item in items:
            url = str(item.get("url", "")).strip()
            if not url or url in seen_urls:
                continue
            domain = str(item.get("domain", "")).strip() or url
            if domain_count.get(domain, 0) >= cap_per_domain:
                continue
            seen_urls.add(url)
            domain_count[domain] = domain_count.get(domain, 0) + 1
            merged.append(item)

    for chunk in reversed(results_by_variant):
        _ingest(chunk, cap_per_domain=2)

    if not merged:
        return ToolResult(name="search_web", ok=True,
                          summary=f"Web search returned no usable results for: {query!r}.",
                          payload={"results": [], "query": query})

    merged = merged[: max_results * 2]
    citations: List[Citation] = []
    for item in merged:
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

    distinct_domains = sorted({str(r.get("domain", "")).strip() for r in merged if r.get("domain")})
    summary = (
        f"Got {len(merged)} web results across {len(distinct_domains)} "
        f"domain(s) for: {query!r}."
    )
    return ToolResult(
        name="search_web", ok=True, summary=summary,
        payload={"results": merged, "query": query, "domains": distinct_domains},
        citations=citations,
    )


async def _search_youtube_async(chatbot: "GuideChatbot", args: Dict[str, Any]) -> ToolResult:
    from ..guide_chatbot import youtube_video_suggestion

    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(name="search_youtube", ok=False,
                          summary="No query provided.", error="empty_query")

    lang = str(args.get("language") or "").strip().lower() or None
    region = _region_for_lang(lang) if lang and lang != "en" else "wt-wt"

    try:
        video = await asyncio.wait_for(
            asyncio.to_thread(
                youtube_video_suggestion, query,
                time_budget_seconds=max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS),
                region=region,
            ),
            timeout=_YOUTUBE_TIMEOUT,
        ) or {}
    except asyncio.TimeoutError:
        log.warning("search_youtube timed out")
        return ToolResult(name="search_youtube", ok=False,
                          summary="YouTube search timed out.", error="timeout")
    except Exception as exc:
        log.warning("search_youtube failed: %s", exc)
        return ToolResult(name="search_youtube", ok=False,
                          summary="YouTube search failed.", error=str(exc))

    url = str(video.get("url", "")).strip()
    title = str(video.get("title", "")).strip() or "YouTube tutorial"
    if not url:
        return ToolResult(name="search_youtube", ok=True,
                          summary="No relevant YouTube tutorial found.",
                          payload={})

    return ToolResult(
        name="search_youtube", ok=True,
        summary=f"Found YouTube tutorial: {title}.",
        payload={"video": video, "query": query},
        citations=[Citation(kind="youtube", label=title, url=url)],
    )


_DISPATCH_ASYNC = {
    "search_manual": _search_manual_async,
    "search_web": _search_web_async,
    "search_youtube": _search_youtube_async,
}


async def _run_tools_async(
    chatbot: "GuideChatbot",
    calls: Sequence[ToolCall],
) -> List[ToolResult]:
    """Run tool calls SEQUENTIALLY.

    We intentionally serialize the tools instead of ``asyncio.gather``:
    - On a 1-CPU container with nested ``wait_for`` + ``to_thread``, the
      event loop got starved under contention and no timeout could fire.
    - The embedding + DDGS calls are network-bound, not CPU-bound, so
      going sequential only adds ~0.5-1s of wall time vs. in-parallel.
    - Each tool keeps its own internal ``wait_for``, so a hung tool
      still bounds itself.
    """
    if not calls:
        return []

    results: List[ToolResult] = []
    for call in calls:
        handler = _DISPATCH_ASYNC.get(call.name)
        if handler is None:
            results.append(ToolResult(
                name=call.name, ok=False,
                summary=f"Unknown tool: {call.name}", error="unknown_tool",
            ))
            continue
        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                handler(chatbot, call.args),
                timeout=_TOOLS_BATCH_TIMEOUT,
            )
            log.debug("tool %s done %dms ok=%s", call.name,
                      int((time.perf_counter() - t0) * 1000), result.ok)
            results.append(result)
        except asyncio.TimeoutError:
            log.warning("tool %s outer timeout after %dms", call.name,
                        int((time.perf_counter() - t0) * 1000))
            results.append(ToolResult(
                name=call.name, ok=False,
                summary=f"Tool {call.name} outer timeout.",
                error="outer_timeout",
            ))
        except Exception as exc:
            log.exception("tool %s crashed after %dms: %s", call.name,
                          int((time.perf_counter() - t0) * 1000), exc)
            results.append(ToolResult(
                name=call.name, ok=False,
                summary=f"Tool {call.name} crashed.", error=str(exc),
            ))

    return results


# ---------------------------------------------------------------------------
# Responder (async)
# ---------------------------------------------------------------------------

def _build_responder_config(system_instruction: str, max_tokens: int) -> genai_types.GenerateContentConfig:
    return genai_types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.15,
        max_output_tokens=max_tokens,
        http_options=genai_types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),
    )


async def _stream_answer_async(
    client: Any,
    *,
    model: str,
    vehicle_name: str,
    lang: str,
    question: str,
    history_block: str,
    tool_results: Sequence[ToolResult],
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    safety_notice: str = "",
) -> AsyncIterator[str]:
    """Stream the Gemini responder through an asyncio.Queue bridge.

    Same rationale as the planner: we drive the SYNC SDK API from a
    dedicated daemon thread (one per request) and republish chunks onto
    an ``asyncio.Queue`` using ``loop.call_soon_threadsafe``. This avoids
    the ``client.aio`` event-loop cache bug AND keeps ``wait_for``
    cancellation semantics in the main coroutine.
    """
    system_instruction = build_system_instruction(vehicle_name, lang, safety_notice)
    evidence_block = build_evidence_block(tool_results)
    prompt = build_user_prompt(
        question=question,
        history_block=history_block,
        evidence_block=evidence_block,
    )

    loop = asyncio.get_running_loop()
    chunk_queue: "asyncio.Queue[Any]" = asyncio.Queue(maxsize=128)
    QUEUE_DONE = object()

    def _drain_sync() -> None:
        def _put(item: Any) -> None:
            loop.call_soon_threadsafe(chunk_queue.put_nowait, item)

        try:
            stream = client.models.generate_content_stream(
                model=model,
                contents=prompt,
                config=_build_responder_config(system_instruction, max_tokens),
            )
            for chunk in stream:
                _put(("chunk", chunk))
        except Exception as exc:
            _put(("error", exc))
        finally:
            _put(QUEUE_DONE)

    threading.Thread(
        target=_drain_sync, name="responder-drain", daemon=True,
    ).start()

    started = time.perf_counter()
    saw_first = False
    while True:
        elapsed = time.perf_counter() - started
        remaining_wallclock = _RESPONDER_WALLCLOCK - elapsed
        if remaining_wallclock <= 0:
            log.warning("responder wallclock cap (%.0fs) hit", _RESPONDER_WALLCLOCK)
            return
        per_get_timeout = (
            _RESPONDER_FIRST_TOKEN if not saw_first
            else min(remaining_wallclock, 10.0)
        )

        try:
            item = await asyncio.wait_for(chunk_queue.get(), timeout=per_get_timeout)
        except asyncio.TimeoutError:
            if not saw_first:
                log.warning("responder first-token timeout (%.0fs)", _RESPONDER_FIRST_TOKEN)
            else:
                log.warning("responder silence timeout after %.1fs", elapsed)
            return

        if item is QUEUE_DONE:
            return
        kind, payload = item
        if kind == "error":
            log.error("responder stream drain error: %s", payload)
            return
        saw_first = True
        text = _extract_chunk_text(payload)
        if text:
            yield text


# ---------------------------------------------------------------------------
# Orchestrator (async)
# ---------------------------------------------------------------------------

async def stream_agent_async(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> AsyncIterator[dict]:
    """Async generator that yields ``{'type': ...}`` events."""
    t0 = time.perf_counter()
    timings: dict = {}
    history = chatbot._get_session_history(session_id)
    history_block = _build_history_block(history)
    slug = chatbot.guide.slug
    log.debug("agent enter slug=%s qlen=%d lang=%s", slug, len(question), lang)

    # ---- Safety triage (sync, cheap) ---------------------------------
    verdict = assess_input_safety(
        question, vehicle_name=chatbot.guide.name, lang=lang,
    )
    if verdict.refused:
        log.info("agent refusal slug=%s reason=%s", slug, verdict.reason)
        yield {"type": "chunk", "text": verdict.refusal_message}
        _save_history(chatbot, session_id, question, verdict.refusal_message)
        yield {
            "type": "end",
            "answer": verdict.refusal_message,
            "sources_block": "", "sources": [],
            "tool_calls": [],
            "timings_ms": {"total_ms": int((time.perf_counter() - t0) * 1000)},
            "refusal_reason": verdict.reason,
        }
        return

    # ---- Planner ----------------------------------------------------
    yield {"type": "status", "step": "planning"}
    plan_started = time.perf_counter()
    tool_calls = await _plan_async(
        chatbot.client,
        question=question,
        vehicle_name=chatbot.guide.name,
        lang=lang,
        history_block=history_block,
        default_model=chatbot.model_name,
        safety_notice=verdict.soft_notice,
    )
    timings["plan_ms"] = int((time.perf_counter() - plan_started) * 1000)
    log.debug("agent planner slug=%s %dms -> %s", slug, timings["plan_ms"],
              [c.name for c in tool_calls])

    # ---- Tools ------------------------------------------------------
    yield {
        "type": "status", "step": "searching",
        "tool_calls": [{"name": c.name, "args": c.args} for c in tool_calls],
    }
    tools_started = time.perf_counter()
    tool_results = await _run_tools_async(chatbot, tool_calls)
    timings["tools_ms"] = int((time.perf_counter() - tools_started) * 1000)
    log.debug("agent tools slug=%s %dms -> %s", slug, timings["tools_ms"],
              [f"{r.name}:ok={r.ok}" for r in tool_results])

    # ---- Responder --------------------------------------------------
    yield {"type": "status", "step": "generating"}
    pieces: List[str] = []
    respond_started = time.perf_counter()
    first_chunk = False
    try:
        async for delta in _stream_answer_async(
            chatbot.client,
            model=chatbot.model_name,
            vehicle_name=chatbot.guide.name,
            lang=lang,
            question=question,
            history_block=history_block,
            tool_results=tool_results,
            safety_notice=verdict.soft_notice,
        ):
            if not first_chunk:
                first_chunk = True
                log.debug("agent responder slug=%s first_chunk %dms", slug,
                          int((time.perf_counter() - respond_started) * 1000))
            pieces.append(delta)
            yield {"type": "chunk", "text": delta}
    except Exception as exc:
        log.error("responder failed slug=%s: %s", slug, exc)
    timings["respond_ms"] = int((time.perf_counter() - respond_started) * 1000)

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
        slug, timings["plan_ms"], timings["tools_ms"],
        timings["respond_ms"], timings["total_ms"],
        [c.name for c in tool_calls],
    )

    yield {
        "type": "end",
        "answer": answer,
        "sources_block": sources_block,
        "sources": [c.__dict__ for c in citations],
        "tool_calls": [{"name": c.name, "args": c.args} for c in tool_calls],
        "timings_ms": timings,
    }


# ---------------------------------------------------------------------------
# Sync bridge — what the Flask SSE thread actually consumes
# ---------------------------------------------------------------------------

_SENTINEL = object()


def stream_agent_sync(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> Iterator[dict]:
    """Run ``stream_agent_async`` in a dedicated worker thread and
    republish its events through a synchronous generator.

    This is the single bridge between the async agent and Flask's sync
    SSE handler. Exactly ONE extra thread per request is created — the
    event loop inside that thread handles planner/tools/responder
    concurrency through ``asyncio.gather`` and the default thread pool
    (min(32, cpu_count+4)) for any remaining sync I/O (FAISS, DDGS).
    """
    event_queue: "queue.Queue[Any]" = queue.Queue(maxsize=256)
    stop_event = threading.Event()
    slug = chatbot.guide.slug

    # Global watchdog: even if the async driver gets wedged (e.g. event
    # loop starved by GIL contention on a 1-CPU container), we cut the
    # stream after this many seconds so the SSE consumer never waits
    # forever. 55s leaves margin below the 75s gunicorn timeout.
    WATCHDOG_SECONDS = 55.0

    async def _driver() -> None:
        try:
            async for event in stream_agent_async(
                chatbot, question=question, lang=lang, session_id=session_id,
            ):
                if stop_event.is_set():
                    break
                event_queue.put(event)
        except Exception as exc:
            log.exception("agent bridge driver crashed slug=%s: %s", slug, exc)
        finally:
            event_queue.put(_SENTINEL)

    def _run_loop() -> None:
        try:
            asyncio.run(_driver())
        except Exception as exc:
            log.exception("agent bridge loop crashed slug=%s: %s", slug, exc)
            event_queue.put(_SENTINEL)

    def _watchdog() -> None:
        stopped = stop_event.wait(WATCHDOG_SECONDS)
        if not stopped:
            log.warning(
                "agent watchdog fired slug=%s after %.0fs — forcing end",
                slug, WATCHDOG_SECONDS,
            )
            stop_event.set()
            try:
                event_queue.put_nowait(_SENTINEL)
            except queue.Full:
                pass

    worker = threading.Thread(
        target=_run_loop, name=f"agent-{slug}", daemon=True,
    )
    worker.start()
    threading.Thread(
        target=_watchdog, name=f"agent-wd-{slug}", daemon=True,
    ).start()

    try:
        while True:
            item = event_queue.get()
            if item is _SENTINEL:
                return
            yield item
    finally:
        # If the SSE consumer bails out (client disconnect) we signal the
        # async driver to stop emitting. The worker thread is daemon so it
        # won't block process shutdown.
        stop_event.set()


# ---------------------------------------------------------------------------
# Blocking end-to-end helper (used by chat_agentic sync path + fallback)
# ---------------------------------------------------------------------------

async def _run_agent_async(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> AgentAnswer:
    pieces: List[str] = []
    tool_calls_seen: List[ToolCall] = []
    tool_results_seen: List[ToolResult] = []
    timings: dict = {}
    final_answer: Optional[str] = None
    sources_block = ""
    citations: List[Citation] = []
    refusal_reason: Optional[str] = None

    async for event in stream_agent_async(
        chatbot, question=question, lang=lang, session_id=session_id,
    ):
        etype = event.get("type")
        if etype == "chunk":
            pieces.append(str(event.get("text", "")))
        elif etype == "end":
            final_answer = str(event.get("answer", "") or "".join(pieces))
            sources_block = str(event.get("sources_block", ""))
            timings = event.get("timings_ms", {}) or {}
            refusal_reason = event.get("refusal_reason")
            # sources are already Citation dicts; rebuild objects
            for raw in event.get("sources", []) or []:
                try:
                    citations.append(Citation(**raw))
                except TypeError:
                    continue
            # tool_calls are in the event payload
            for tc in event.get("tool_calls", []) or []:
                tool_calls_seen.append(ToolCall(
                    name=str(tc.get("name", "")),
                    args=dict(tc.get("args", {}) or {}),
                ))

    return AgentAnswer(
        answer=(final_answer or "".join(pieces) or "Je n'ai pas pu generer de reponse."),
        sources_block=sources_block,
        citations=citations,
        tool_calls=tool_calls_seen,
        tool_results=tool_results_seen,
        timings_ms=timings,
    )


def run_agent_sync(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
) -> AgentAnswer:
    """Blocking wrapper around the async orchestrator.

    Used by sync callers (``chat_agentic``, SSE fallback thread).
    Creates an isolated event loop for this call. Safe to invoke from
    gunicorn gthread workers — they don't have an ambient loop.
    """
    return asyncio.run(_run_agent_async(
        chatbot, question=question, lang=lang, session_id=session_id,
    ))
