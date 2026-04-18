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

_MANUAL_SEARCH_HARD_TIMEOUT = 12.0


def _run_with_hard_timeout(fn, timeout_s: float, label: str):
    """Run ``fn`` in a daemon thread and raise TimeoutError if it exceeds ``timeout_s``.

    Python cannot kill a thread holding a stuck socket (embeddings RPC,
    DDGS, etc.). We simply stop waiting for it — the thread becomes a
    zombie that dies with the worker process, but the caller returns
    in bounded time instead of blocking gunicorn to SIGKILL.
    """
    import queue as _queue
    import threading as _threading

    q: "_queue.Queue[tuple[str, object]]" = _queue.Queue(maxsize=1)

    def _target() -> None:
        try:
            q.put(("ok", fn()))
        except Exception as exc:
            q.put(("err", exc))

    t = _threading.Thread(target=_target, name=f"hardto-{label}", daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        log.warning("[HARD-TIMEOUT] %s exceeded %.1fs — abandoning", label, timeout_s)
        raise TimeoutError(f"{label} exceeded {timeout_s}s")
    try:
        status, payload = q.get_nowait()
    except _queue.Empty:
        raise TimeoutError(f"{label} returned without a result")
    if status == "err":
        raise payload  # type: ignore[misc]
    return payload


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
        # Wrap the hybrid search in a hard timeout. The embedding RPC
        # can stall from Dokploy if the egress to Google is momentarily
        # unreachable, and LangChain's FAISS wrapper has no timeout of
        # its own.
        result = _run_with_hard_timeout(
            lambda: chatbot._hybrid_search(query, k=TOP_K_RESULTS),
            timeout_s=_MANUAL_SEARCH_HARD_TIMEOUT,
            label="search_manual",
        )
    except TimeoutError as exc:
        log.warning("search_manual TIMED OUT for %s: %s", chatbot.guide.slug, exc)
        return ToolResult(
            name="search_manual",
            ok=False,
            summary="Manual search timed out (embedding service slow).",
            error="timeout",
        )
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
    query_variants: List[str] = [query]
    if official and "site:" not in query.lower():
        # Cap to the first 3 domains so the ``OR`` chain stays sane.
        site_clause = " OR ".join(f"site:{d}" for d in official[:3])
        query_variants.append(f"{query} {site_clause}")

    budget = max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS)
    results_by_variant: List[List[Dict[str, str]]] = []

    import time as _time

    # Per-variant hard timeout: 6s is enough for a healthy DDGS response
    # (we measured ~1.3s locally) and caps the damage when the library
    # falls back to Wikipedia OpenSearch and stalls on DNS/TLS inside
    # Docker. DDGS(timeout=N) is only a per-HTTP-request cap, not a
    # wall-clock guarantee — this is.
    DDGS_VARIANT_TIMEOUT = 6.0

    def _fetch(q: str) -> List[Dict[str, str]]:
        t0 = _time.perf_counter()
        log.info("[DDGS] fetch START q=%r", q[:80])
        try:
            out = _run_with_hard_timeout(
                lambda: web_search_results(
                    q,
                    max_results=max_results,
                    time_budget_seconds=budget,
                    region=region,
                ) or [],
                timeout_s=DDGS_VARIANT_TIMEOUT,
                label=f"ddgs[{q[:40]}]",
            )
            log.info("[DDGS] fetch DONE %dms -> %d items q=%r", int((_time.perf_counter()-t0)*1000), len(out), q[:80])
            return out
        except TimeoutError as exc:
            log.warning("[DDGS] fetch TIMED OUT after %dms q=%r: %s", int((_time.perf_counter()-t0)*1000), q[:80], exc)
            return []
        except Exception as exc:
            log.warning("[DDGS] fetch FAILED %dms q=%r: %s", int((_time.perf_counter()-t0)*1000), q[:80], exc)
            return []

    # Same trap as run_tools_in_parallel: never use `with ThreadPoolExecutor`
    # here. If DDGS hangs on a network read, Python cannot kill the thread,
    # and the context manager's shutdown(wait=True) blocks the entire
    # request. Exit with wait=False and accept zombie threads.
    ex = ThreadPoolExecutor(max_workers=len(query_variants))
    fetch_deadline = budget + 2.0
    try:
        futures = [ex.submit(_fetch, variant) for variant in query_variants]
        try:
            for future in as_completed(futures, timeout=fetch_deadline):
                try:
                    results_by_variant.append(future.result(timeout=0.1))
                except Exception:
                    results_by_variant.append([])
        except Exception:
            log.warning("[DDGS] variants deadline %.1fs hit — collecting what we have", fetch_deadline)
            for f in futures:
                if f.done():
                    try:
                        results_by_variant.append(f.result(timeout=0.1))
                    except Exception:
                        results_by_variant.append([])
                else:
                    f.cancel()
                    results_by_variant.append([])
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
        # YouTube helper runs multiple DDGS queries sequentially; give it
        # a hard 8s wall-clock cap so one stuck query doesn't block the
        # whole agent.
        video = _run_with_hard_timeout(
            lambda: youtube_video_suggestion(
                query,
                time_budget_seconds=max(1.0, ENRICHMENT_TIME_BUDGET_SECONDS),
                region=region,
            ) or {},
            timeout_s=8.0,
            label="search_youtube",
        )
    except TimeoutError:
        log.warning("search_youtube TIMED OUT for %s", query)
        return ToolResult(
            name="search_youtube",
            ok=False,
            summary="YouTube search timed out.",
            error="timeout",
        )
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

    import time as _time

    def _timed_handler(name: str, handler, args):
        t_start = _time.perf_counter()
        log.info("[TOOL %s] START args=%s", name, {k: str(v)[:60] for k, v in (args or {}).items()})
        try:
            result = handler(chatbot, args)
            dt = int((_time.perf_counter() - t_start) * 1000)
            log.info("[TOOL %s] DONE %dms ok=%s summary=%s", name, dt, result.ok, result.summary[:80])
            return result
        except Exception as exc:
            dt = int((_time.perf_counter() - t_start) * 1000)
            log.exception("[TOOL %s] CRASH %dms: %s", name, dt, exc)
            raise

    results: List[ToolResult] = [None] * len(calls)  # type: ignore[assignment]
    # NOTE: do NOT use `with ThreadPoolExecutor(...)` — the context manager
    # calls shutdown(wait=True) on exit, which would block forever on any
    # stuck thread (DDGS hanging on Wikipedia, genai socket frozen). Python
    # cannot kill a thread, so we explicitly shutdown(wait=False) and let
    # zombies die with the worker process.
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
            future_to_index[executor.submit(_timed_handler, call.name, handler, call.args)] = index

        batch_started = _time.perf_counter()
        completed = 0
        pending = len(future_to_index)
        HARD_CAP_SECONDS = 20.0
        try:
            for future in as_completed(future_to_index, timeout=HARD_CAP_SECONDS):
                index = future_to_index[future]
                call = calls[index]
                try:
                    results[index] = future.result(timeout=0.1)
                    completed += 1
                    pending -= 1
                    log.info(
                        "[TOOLS-BATCH] progress %d/%d elapsed=%.2fs",
                        completed,
                        len(future_to_index),
                        _time.perf_counter() - batch_started,
                    )
                except Exception as exc:
                    log.exception("[TOOLS-BATCH] %s failed: %s", call.name, exc)
                    results[index] = ToolResult(
                        name=call.name, ok=False, summary=f"Tool {call.name} failed.", error=str(exc),
                    )
                    pending -= 1
        except Exception as exc:
            log.warning(
                "[TOOLS-BATCH] HARD CAP hit after %.2fs — %d pending, reason=%s",
                _time.perf_counter() - batch_started,
                pending,
                exc.__class__.__name__,
            )
            for future, index in future_to_index.items():
                if results[index] is None:
                    future.cancel()
                    call = calls[index]
                    log.warning("[TOOLS-BATCH] marking %s as hang_timeout", call.name)
                    results[index] = ToolResult(
                        name=call.name,
                        ok=False,
                        summary=f"Tool {call.name} timed out after {HARD_CAP_SECONDS}s.",
                        error="hang_timeout",
                    )
    finally:
        # wait=False: return immediately even if threads are stuck.
        # cancel_futures=True: drop anything still in the queue.
        log.info("[TOOLS-BATCH] shutting down executor (wait=False)")
        executor.shutdown(wait=False, cancel_futures=True)
        log.info("[TOOLS-BATCH] executor.shutdown returned")

    log.info("[TOOLS-BATCH] FULLY DONE completed=%d/%d", completed, len(future_to_index))
    return [r for r in results if r is not None]
