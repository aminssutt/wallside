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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

from ..config import (
    ENRICHMENT_TIME_BUDGET_SECONDS,
    TOP_K_RESULTS,
    WEB_MAX_RESULTS,
)

if TYPE_CHECKING:  # pragma: no cover - type-only imports
    from ..guide_chatbot import GuideChatbot

log = logging.getLogger("auris.agent.tools")


# ---------------------------------------------------------------------------
# Localisation + official-domain boost
# ---------------------------------------------------------------------------

# Language -> DDGS region. ``wt-wt`` means worldwide (no bias), which we keep
# as a sane fallback so niche languages still reach global content.
_LANG_TO_REGION: Dict[str, str] = {
    "fr": "fr-fr",
    "en": "us-en",
    "ko": "kr-kr",
    "de": "de-de",
    "es": "es-es",
    "it": "it-it",
}


def _region_for_lang(lang: Optional[str]) -> str:
    if not lang:
        return "wt-wt"
    return _LANG_TO_REGION.get(lang.lower().strip(), "wt-wt")


# Best-effort mapping from a guide's brand slug to official manufacturer
# domains. When a match exists, ``_run_search_web`` fires an additional
# ``site:<domain>`` query in parallel with the planner's generic query so
# answers get anchored on official sources (audi.fr, bmw.com, hyundai.co.kr,
# ...) instead of random aggregators.
_OFFICIAL_DOMAINS: Dict[str, List[str]] = {
    "alfa-romeo": ["alfaromeo.com", "alfaromeo.fr", "alfaromeousa.com"],
    "alpine": ["alpinecars.com", "alpine.cars"],
    "audi": ["audi.com", "audi.fr", "audiusa.com", "audi.co.uk", "audi.co.kr"],
    "bmw": ["bmw.com", "bmw.fr", "bmwusa.com", "bmw.co.uk", "bmw.co.kr"],
    "chevrolet": ["chevrolet.com", "chevrolet.fr", "chevrolet.co.kr"],
    "citroen": ["citroen.com", "citroen.fr", "citroen.co.uk"],
    "cupra": ["cupraofficial.com", "cupraofficial.fr"],
    "dacia": ["dacia.com", "dacia.fr", "dacia.co.uk"],
    "ds": ["dsautomobiles.com", "dsautomobiles.fr"],
    "fiat": ["fiat.com", "fiat.fr", "fiatusa.com"],
    "ford": ["ford.com", "ford.fr", "ford.co.uk"],
    "genesis": ["genesis.com", "genesis.fr", "genesis.co.kr"],
    "honda": ["honda.com", "honda.fr", "honda.co.uk", "honda.co.kr"],
    "hyundai": ["hyundai.com", "hyundai.fr", "hyundai.co.kr", "hyundaiusa.com"],
    "jaguar": ["jaguar.com", "jaguar.fr", "jaguar.co.uk"],
    "jeep": ["jeep.com", "jeep.fr"],
    "kia": ["kia.com", "kia.fr", "kia.com/us", "kia.com/kr"],
    "land-rover": ["landrover.com", "landrover.fr", "landrover.co.uk"],
    "lexus": ["lexus.com", "lexus.fr", "lexus.eu", "lexus.co.kr"],
    "maserati": ["maserati.com", "maserati.fr"],
    "mazda": ["mazda.com", "mazda.fr", "mazdausa.com"],
    "mercedes": ["mercedes-benz.com", "mercedes-benz.fr", "mbusa.com"],
    "mini": ["mini.com", "mini.fr", "miniusa.com"],
    "mitsubishi": ["mitsubishi-motors.com", "mitsubishi-motors.fr"],
    "nissan": ["nissan.com", "nissan.fr", "nissanusa.com", "nissan.co.uk"],
    "opel": ["opel.com", "opel.fr"],
    "peugeot": ["peugeot.com", "peugeot.fr"],
    "renault": ["renault.com", "renault.fr", "renault.co.uk"],
    "seat": ["seat.com", "seat.fr"],
    "skoda": ["skoda.com", "skoda.fr", "skoda-auto.com"],
    "subaru": ["subaru.com", "subaru.fr", "subaru-global.com"],
    "suzuki": ["suzuki.com", "suzuki.fr", "globalsuzuki.com"],
    "tesla": ["tesla.com", "tesla.com/fr", "tesla.com/ko_kr"],
    "toyota": ["toyota.com", "toyota.fr", "toyota.co.uk", "toyota.co.kr"],
    "volkswagen": ["volkswagen.com", "volkswagen.fr", "vw.com"],
    "volvo": ["volvocars.com", "volvocars.fr"],
}


def _slugify_brand(brand: str) -> str:
    """Cheap slug for dict lookup. Matches the keys above."""
    text = (brand or "").strip().lower()
    for ch in (" ", "_", "."):
        text = text.replace(ch, "-")
    # Keep only ascii letters + hyphens so alfa-romeo, land-rover, ... match.
    return "".join(c for c in text if c.isalpha() or c == "-")


def _official_domains_for(chatbot: "GuideChatbot") -> List[str]:
    brand_attr = getattr(getattr(chatbot, "guide", None), "brand", "") or ""
    return _OFFICIAL_DOMAINS.get(_slugify_brand(brand_attr), [])


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
    """Multi-query DuckDuckGo web search with official-site boost.

    Strategy: the planner's generic query is fired in parallel with a
    ``site:<official-domain>`` variant when the guide's brand maps to a
    known manufacturer domain. Both result streams are merged, deduped by
    URL, and kept diverse (max 2 snippets per domain) so the responder
    gets sources from SEVERAL sites instead of being anchored on a single
    aggregator.
    """
    from ..guide_chatbot import web_search_results  # avoid import cycle

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

    # Language hint propagated from the planner / bridge. Falls back to
    # whatever the guide's stored detected language is so we still tilt
    # toward the user's locale without the planner having to track it.
    lang = str(args.get("language") or "").strip().lower() or None
    region = _region_for_lang(lang)

    official = _official_domains_for(chatbot)
    # Fan out: generic query + up to 3 separate ``site:<domain>`` queries,
    # one per official domain. Each runs in its own thread so a slow or
    # empty manufacturer site can't delay the generic search. We then
    # early-exit as soon as two variants come back with any usable
    # results — extra results are nice but not worth waiting for.
    query_variants: List[str] = [query]
    if official and "site:" not in query.lower():
        for domain in official[:3]:
            query_variants.append(f"{query} site:{domain}")

    budget = max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS)
    results_by_variant: List[List[Dict[str, str]]] = []

    def _fetch(q: str) -> List[Dict[str, str]]:
        try:
            return web_search_results(
                q,
                max_results=max_results,
                time_budget_seconds=budget,
                region=region,
            ) or []
        except Exception as exc:
            log.warning("web_search_results failed for %r: %s", q, exc)
            return []

    # Early-exit target: once ENOUGH variants come back non-empty we stop
    # waiting for the rest. That guarantees we return in roughly the time
    # of the FASTEST two responders rather than the slowest one.
    enough_non_empty = min(2, len(query_variants))
    non_empty_count = 0
    ex = ThreadPoolExecutor(max_workers=len(query_variants))
    try:
        futures = [ex.submit(_fetch, variant) for variant in query_variants]
        try:
            for future in as_completed(futures, timeout=budget + 1.0):
                try:
                    result = future.result(timeout=0.1)
                except Exception:
                    result = []
                results_by_variant.append(result)
                if result:
                    non_empty_count += 1
                if non_empty_count >= enough_non_empty:
                    # Good enough — drop the pending ones and move on.
                    break
        except FutureTimeoutError:
            pass
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    # Merge: prefer items that appear in the ``site:<official>`` variant
    # (they come from a manufacturer domain) but keep diversity so the
    # responder has several angles to cite.
    seen_urls = set()
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

    # Official results first (reversed order so site: variant takes priority
    # when present), general results after.
    for chunk in reversed(results_by_variant):
        _ingest(chunk, cap_per_domain=2)

    if not merged:
        return ToolResult(
            name="search_web",
            ok=True,
            summary=f"Web search returned no usable results for: {query!r}.",
            payload={"results": [], "query": query},
        )

    merged = merged[: max_results * 2]

    citations: List[Citation] = []
    for item in merged:
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        domain = str(item.get("domain", "")).strip()
        if not title or not url:
            continue
        citations.append(
            Citation(
                kind="web",
                label=f"{title} ({domain})" if domain else title,
                url=url,
            )
        )

    distinct_domains = sorted({str(r.get("domain", "")).strip() for r in merged if r.get("domain")})
    summary = (
        f"Got {len(merged)} web results across {len(distinct_domains)} "
        f"domain(s) for: {query!r}."
    )
    return ToolResult(
        name="search_web",
        ok=True,
        summary=summary,
        payload={"results": merged, "query": query, "domains": distinct_domains},
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

    lang = str(args.get("language") or "").strip().lower() or None
    # Youtube is worldwide by default so tutorials in any language stay
    # eligible; only bias when the user explicitly asked us to.
    region = _region_for_lang(lang) if lang and lang != "en" else "wt-wt"

    try:
        video = youtube_video_suggestion(
            query,
            time_budget_seconds=max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS),
            region=region,
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


# Wall-clock caps. The underlying ddgs library occasionally hangs when one
# of its upstream engines (Wikipedia, Yahoo, Mojeek, ...) takes minutes to
# respond or rate-limits. Without these caps, a single stuck future bubbles
# all the way up to Gunicorn which then SIGKILLs the whole worker. Keep
# these tight: the agent is allowed to return a partial evidence block if
# one tool is slow.
_PER_TOOL_TIMEOUT_SECONDS = 8.0
_BATCH_TIMEOUT_SECONDS = 12.0


def run_tools_in_parallel(
    chatbot: "GuideChatbot",
    calls: Sequence[ToolCall],
    max_workers: int = 3,
) -> List[ToolResult]:
    """Execute a batch of tool calls concurrently with hard wall-clock caps.

    Unknown tool names produce a failed ``ToolResult`` rather than raising,
    so the agent can still hand off what succeeded to the responder.
    Results preserve the order of ``calls`` for deterministic citation
    numbering. Individual tools are capped at ``_PER_TOOL_TIMEOUT_SECONDS``
    and the whole batch at ``_BATCH_TIMEOUT_SECONDS`` — anything slower is
    recorded as a failed ``ToolResult(ok=False, error="timeout")`` so the
    responder still gets whatever succeeded.
    """
    if not calls:
        return []

    import time as _time
    started_at = _time.monotonic()

    results: List[ToolResult] = [None] * len(calls)  # type: ignore[assignment]
    # ``cancel_futures=True`` is set on shutdown below so pending submits
    # are dropped when the batch deadline is reached. The executor is kept
    # out of the ``with`` contextmanager so we can control shutdown
    # semantics manually.
    executor = ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(calls))))
    try:
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

        for future in as_completed(future_to_index, timeout=_BATCH_TIMEOUT_SECONDS):
            index = future_to_index[future]
            call = calls[index]
            remaining = max(0.1, _PER_TOOL_TIMEOUT_SECONDS - (_time.monotonic() - started_at))
            try:
                results[index] = future.result(timeout=remaining)
            except FutureTimeoutError:
                log.warning("Tool %s timed out after %.1fs", call.name, remaining)
                future.cancel()
                results[index] = ToolResult(
                    name=call.name,
                    ok=False,
                    summary=f"Tool {call.name} timed out.",
                    error="timeout",
                )
            except Exception as exc:  # pragma: no cover - defensive
                log.exception("Tool %s crashed: %s", call.name, exc)
                results[index] = ToolResult(
                    name=call.name,
                    ok=False,
                    summary=f"Tool {call.name} crashed.",
                    error=str(exc),
                )
    except FutureTimeoutError:
        log.warning(
            "Batch of %d tool calls exceeded %.1fs — returning partial results",
            len(future_to_index),
            _BATCH_TIMEOUT_SECONDS,
        )
        for future, index in future_to_index.items():
            if results[index] is None:
                call = calls[index]
                future.cancel()
                results[index] = ToolResult(
                    name=call.name,
                    ok=False,
                    summary=f"Tool {call.name} dropped (batch timeout).",
                    error="batch_timeout",
                )
    finally:
        # Do NOT wait for stuck threads — they would keep the worker blocked
        # indefinitely. cancel_futures drops everything still pending.
        executor.shutdown(wait=False, cancel_futures=True)

    return [r for r in results if r is not None]
