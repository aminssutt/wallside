"""Legacy-SSE bridge for the tool-calling agent.

Translates the agent's own events (``status`` / ``chunk`` / ``end``) into
the richer wire format that ``api.py::chat_stream`` already forwards to
the frontend:

* ``status`` — agent_planning / agent_searching / generating
* ``chunk`` — text deltas as produced by the responder
* ``sources_start`` + ``source_item`` × N + ``sources_end`` — manual + web
  citations in the exact shape ``build_sources_structured`` produces.
* ``video_result`` / ``video_none`` — YouTube tutorial suggestion.
* ``end`` — response text, confidence, fix_mode, metrics,
  sources_structured, optional video.

Thanks to this adapter the frontend does not need any change when the
backend swaps from the legacy streaming pipeline to the agent.
"""
from __future__ import annotations

import re
from typing import Dict, Iterator, List, Optional, TYPE_CHECKING

from .orchestrator import stream_agent
from .tools import Citation

if TYPE_CHECKING:  # pragma: no cover
    from ..guide_chatbot import GuideChatbot


_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def _extract_youtube_id(url: str) -> str:
    match = _YOUTUBE_ID_RE.search(url or "")
    return match.group(1) if match else ""


def _legacy_manual_source(
    citation: Citation,
    slug: str,
    pdf_url: str = "",
) -> Dict[str, str]:
    label = citation.source_file or citation.label or "manuel.pdf"
    page = citation.page or "?"
    source: Dict[str, str] = {
        "kind": "manual",
        "label": label,
        "page": page,
        "slug": slug,
        "excerpt": "",
        "display": f"Manual: {label}, page {page}",
    }
    # When the guide's manifest carries an inspirauto pdf_url, thread it
    # through so the frontend's proof modal opens the external PDF
    # anchored on the right page (#page=N) instead of hitting a dead
    # /api/guides/<slug>/pdf route for guides whose source PDF was never
    # copied into car data/.
    if pdf_url:
        source["pdf_url"] = pdf_url
    return source


def _legacy_web_source(citation: Citation) -> Dict[str, str]:
    label = citation.label or citation.url
    display = citation.label or citation.url
    return {
        "kind": "web",
        "label": label,
        "url": citation.url,
        "display": display,
    }


def _dict_to_citation(data: Dict) -> Optional[Citation]:
    """Reconstruct a ``Citation`` from its serialised dict form.

    Silently drops malformed entries rather than raising.
    """
    try:
        return Citation(
            kind=str(data.get("kind", "")),
            label=str(data.get("label", "")),
            url=str(data.get("url", "")),
            source_file=str(data.get("source_file", "")),
            page=str(data.get("page", "")),
        )
    except Exception:
        return None


def _status_step(agent_step: str) -> str:
    """Map internal agent steps to the names the frontend already renders."""
    return {
        "planning": "agent_planning",
        "searching": "agent_searching",
        "generating": "generating",
    }.get(agent_step, agent_step or "")


def stream_agent_legacy_events(
    chatbot: "GuideChatbot",
    *,
    question: str,
    lang: str,
    session_id: str = "default",
    message_id: str = "",
) -> Iterator[Dict]:
    """Run the agent and yield events in the legacy SSE contract.

    The generator is ready to be plumbed directly into
    ``api.py::chat_stream`` without touching the existing dispatcher
    (``event_type == "chunk"`` / ``"source_item"`` / …).
    """
    slug = chatbot.guide.slug
    guide_pdf_url = str(getattr(chatbot.guide, "pdf_url", "") or "")
    response_parts: List[str] = []
    sources_emitted = False

    for event in stream_agent(
        chatbot,
        question=question,
        lang=lang,
        session_id=session_id,
    ):
        etype = str(event.get("type", "")).strip()

        if etype == "status":
            step = _status_step(str(event.get("step", "")))
            if step:
                yield {"type": "status", "step": step, "message_id": message_id}
            continue

        if etype == "chunk":
            text = str(event.get("text", ""))
            if not text:
                continue
            response_parts.append(text)
            yield {"type": "chunk", "text": text, "message_id": message_id}
            continue

        if etype == "end":
            citations: List[Citation] = []
            for raw in event.get("sources") or []:
                if isinstance(raw, dict):
                    reconstructed = _dict_to_citation(raw)
                    if reconstructed:
                        citations.append(reconstructed)

            manual_and_web: List[Dict[str, str]] = []
            video_payload: Optional[Dict[str, str]] = None
            for citation in citations:
                if citation.kind == "manual":
                    manual_and_web.append(
                        _legacy_manual_source(citation, slug, pdf_url=guide_pdf_url)
                    )
                elif citation.kind == "web":
                    manual_and_web.append(_legacy_web_source(citation))
                elif citation.kind == "youtube":
                    video_id = _extract_youtube_id(citation.url)
                    thumbnail = (
                        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                        if video_id
                        else ""
                    )
                    video_payload = {
                        "title": citation.label or "YouTube tutorial",
                        "url": citation.url,
                        "thumbnail": thumbnail,
                    }

            if manual_and_web and not sources_emitted:
                sources_emitted = True
                yield {"type": "sources_start", "message_id": message_id}
                for src in manual_and_web:
                    yield {
                        "type": "source_item",
                        "message_id": message_id,
                        "source": src,
                    }
                yield {"type": "sources_end", "message_id": message_id}

            if video_payload:
                yield {"type": "video_result", "message_id": message_id, **video_payload}
            else:
                yield {"type": "video_none", "message_id": message_id}

            final_response = (
                str(event.get("answer") or "").strip()
                or "".join(response_parts).strip()
            )
            end_payload = {
                "type": "end",
                "message_id": message_id,
                "response": final_response,
                "confidence": str(event.get("confidence") or "medium"),
                "fix_mode": False,
                "metrics": event.get("timings_ms") or {},
                "sources_structured": manual_and_web,
            }
            if video_payload:
                end_payload["video"] = video_payload
            yield end_payload
            continue


__all__ = ["stream_agent_legacy_events"]
