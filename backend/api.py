"""
API Flask for the pre-indexed vehicle guide chatbot.
"""
import csv
import json
import logging
import os
import queue
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, redirect, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.guide_manager import guide_manager
from src.guide_chatbot import get_guide_chatbot, prewarm_guide_chatbots
from src.config import (
    DATA_DIR,
    ALLOWED_ORIGINS,
    MAX_MESSAGE_LENGTH,
    PREWARM_GUIDES,
    STREAM_HEARTBEAT_SECONDS,
)


def _csv_safe(value: str) -> str:
    """Prevent CSV formula injection."""
    s = str(value)
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("auris")

# Build fingerprint printed at worker boot — bump when shipping a fix
# whose deployment must be verified at a glance in prod logs.
BUILD_MARKER = "BUILD-2026-04-19-async-v1"
log.info("=== %s booting ===", BUILD_MARKER)


BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIST_DIR = Path(
    os.getenv("FRONTEND_DIST_DIR", PROJECT_ROOT / "frontend" / "dist")
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB max request body

CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["120 per minute"],
    storage_uri="memory://",
)


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # CSP is handled by the reverse proxy (Traefik / Dokploy).
    # Setting it here was blocking eval, inline scripts, and API connections.
    return response

# Serve car images from data/vehicle_images first, then legacy manuel/voiture.
IMAGE_DIRS = [
    DATA_DIR / "vehicle_images",
    PROJECT_ROOT / "manuel" / "voiture",
]

# PDF directories for open proof (car data + legacy manuel)
PDF_DIRS = [
    PROJECT_ROOT / "car_data",   # Docker: /app/car_data/<Brand>/file.pdf
    PROJECT_ROOT / "car data",   # Local dev: car data/<Brand>/file.pdf
    PROJECT_ROOT / "manuel",     # Legacy: manuel/manuel clio 4.pdf
]

WAITLIST_DIR = DATA_DIR / "waitlist"
WAITLIST_FILE = WAITLIST_DIR / "premium_waitlist.csv"
WAITLIST_COLUMNS = ["email", "lang", "source", "created_at"]
WAITLIST_LOCK = Lock()
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ============================================
# GUIDE ENDPOINTS
# ============================================

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _sse_event(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_comment(comment: str) -> str:
    return f": {comment}\n\n"


def _agent_enabled() -> bool:
    """Feature flag — when true ``/chat`` and ``/chat/stream`` route to the
    tool-calling agent instead of the legacy linear pipeline."""
    return os.getenv("AGENT_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")


def _compute_fallback_chunk(streamed_text: str, fallback_text: str) -> str:
    """Return only the missing suffix when a sync fallback completes a partial stream.

    This function is strict by design: it ONLY emits the missing tail when the streamed
    text is a clean prefix of the fallback text. If the two responses diverge mid-way
    (common with non-deterministic LLM output), emitting any portion of the fallback
    would cause visible duplication in the chat UI. In that case we prefer to leave
    the already-streamed text alone and return an empty string.
    """
    streamed = streamed_text or ""
    fallback = fallback_text or ""

    if not fallback:
        return ""
    if not streamed:
        return fallback
    if streamed == fallback:
        return ""
    # Only append the fallback tail if the stream is a TRUE prefix.
    if fallback.startswith(streamed):
        return fallback[len(streamed):]
    # Be conservative: do not splice divergent text — that is what caused the
    # duplicated responses observed in production.
    return ""


_PREWARM_STARTED = False
_PREWARM_LOCK = Lock()


def _maybe_start_prewarm():
    global _PREWARM_STARTED
    if not PREWARM_GUIDES:
        return
    with _PREWARM_LOCK:
        if _PREWARM_STARTED:
            return
        _PREWARM_STARTED = True

    def _run():
        started_at = datetime.now(timezone.utc)
        log.info("Starting chatbot prewarm for %s", PREWARM_GUIDES)
        results = prewarm_guide_chatbots()
        log.info(
            "Chatbot prewarm finished at %s: %s",
            started_at.isoformat(),
            json.dumps(results, ensure_ascii=True, sort_keys=True),
        )

    Thread(target=_run, name="chatbot-prewarm", daemon=True).start()


_maybe_start_prewarm()


@app.route('/api/guides', methods=['GET'])
def list_guides():
    """List all available pre-indexed guides."""
    brand = request.args.get("brand", "").strip() or None
    segment = request.args.get("segment", "").strip() or None
    all_guides = guide_manager.list_guides()
    filtered = all_guides
    if brand:
        brand_norm = brand.casefold()
        filtered = [
            g for g in all_guides
            if str(g.get("brand", "")).casefold() == brand_norm
        ]
    if segment:
        segment_norm = segment.casefold()
        filtered = [
            g for g in filtered
            if str(g.get("segment", "")).casefold() == segment_norm
        ]
    segments = sorted(
        {str(g.get("segment", "autre")) for g in all_guides},
        key=str.casefold,
    )
    brands = sorted(
        {str(g.get("brand")) for g in all_guides if g.get("brand")},
        key=str.casefold,
    )
    return jsonify({
        "success": True,
        "guides": filtered,
        "brands": brands,
        "segments": segments,
    })


@app.route('/api/guides/<slug>', methods=['GET'])
def get_guide(slug):
    """Get details for a specific guide."""
    if not _SLUG_RE.match(slug):
        return jsonify({"success": False, "error": "Invalid slug"}), 400
    guide = guide_manager.get_guide(slug)
    if not guide or not guide.is_indexed:
        return jsonify({
            "success": False,
            "error": "Guide introuvable"
        }), 404

    guide_payload = guide.to_dict()
    # The preview button should be shown when EITHER a local PDF exists
    # under car data/ OR the guide's manifest carries an external pdf_url
    # (inspirauto.fr/getPdf.php/?file=...). to_dict() already exposes
    # pdf_url so the frontend can open it directly with #page=N anchors.
    has_external = bool(guide_payload.get("pdf_url"))
    has_local = _find_guide_pdf(slug) is not None
    guide_payload["pdf_available"] = has_local or has_external

    return jsonify({
        "success": True,
        "guide": guide_payload,
    })


def _normalize_pdf_name(name: str) -> str:
    """Normalize PDF name for fuzzy matching (strip accents, lowercase, collapse separators)."""
    nfkd = unicodedata.normalize("NFKD", name.lower())
    clean = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[-_\s]+", " ", clean).strip()


def _find_guide_pdf(slug: str, filename: Optional[str] = None) -> Optional[Path]:
    """Best-effort fuzzy lookup of the source PDF for a guide.

    Returns the resolved ``Path`` when a match is found inside any of the
    configured ``PDF_DIRS``, otherwise ``None``. Shared by ``serve_guide_pdf``
    and ``get_guide`` so the metadata endpoint can tell the frontend whether
    a PDF preview is actually available.
    """
    guide = guide_manager.get_guide(slug)
    guide_name = guide.name if guide else slug.replace("-", " ")

    targets: List[str] = []
    if filename and ".." not in filename:
        targets.append(_normalize_pdf_name(filename))
    targets.append(_normalize_pdf_name(guide_name))
    slug_normalized = slug.replace("-", " ")

    for pdf_dir in PDF_DIRS:
        if not pdf_dir.exists():
            continue
        for pdf_path in pdf_dir.rglob("*.pdf"):
            try:
                pdf_path.resolve().relative_to(pdf_dir.resolve())
            except ValueError:
                continue
            norm_name = _normalize_pdf_name(pdf_path.stem)
            for target in targets:
                if (
                    norm_name == _normalize_pdf_name(Path(target).stem)
                    or target in norm_name
                    or norm_name in target
                ):
                    return pdf_path
            if slug_normalized in norm_name or norm_name in slug_normalized:
                return pdf_path
    return None


@app.route('/api/guides/<slug>/pdf', methods=['GET'])
@app.route('/api/guides/<slug>/pdf/<path:filename>', methods=['GET'])
def serve_guide_pdf(slug, filename=None):
    """Serve a guide's source PDF. Tries filename first, then fuzzy matches by guide name."""
    if not _SLUG_RE.match(slug):
        return jsonify({"error": "Invalid request"}), 400

    pdf_path = _find_guide_pdf(slug, filename=filename)
    if pdf_path is not None:
        resp = send_from_directory(
            str(pdf_path.parent), pdf_path.name, mimetype="application/pdf"
        )
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        return resp

    # No local PDF — if the guide manifest carries an inspirauto pdf_url,
    # redirect the browser to it so the built-in proof modal can still
    # open the right page via the #page=N anchor.
    guide = guide_manager.get_guide(slug)
    external_url = str(getattr(guide, "pdf_url", "") or "").strip()
    if external_url:
        return redirect(external_url, code=302)

    return jsonify({"error": "PDF not found"}), 404



# ============================================
# CHAT ENDPOINTS
# ============================================

_SESSION_ID_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def _parse_chat_request(slug: str):
    """Validate slug + JSON body shared by /chat and /chat/stream.

    Returns (parsed, error_response). On success parsed is a dict with
    {guide, question, lang, session_id} and error_response is None.
    On failure parsed is None and error_response is a (flask_response, status)
    tuple the endpoint returns directly.
    """
    if not _SLUG_RE.match(slug):
        return None, (jsonify({"success": False, "error": "Invalid slug"}), 400)

    guide = guide_manager.get_guide(slug)
    if not guide or not guide.is_indexed:
        return None, (jsonify({"success": False, "error": "Guide introuvable"}), 404)

    data = request.get_json(silent=True)
    if not data or 'message' not in data:
        return None, (jsonify({"success": False, "error": "Message requis"}), 400)

    question = str(data.get('message', '')).strip()
    if not question:
        return None, (jsonify({"success": False, "error": "Message vide"}), 400)
    if len(question) > MAX_MESSAGE_LENGTH:
        return None, (jsonify({
            "success": False,
            "error": f"Message trop long (max {MAX_MESSAGE_LENGTH} caracteres)",
        }), 400)

    lang = data.get('lang') or None
    if lang and lang not in ('fr', 'en', 'ko'):
        lang = None

    session_id = data.get('session_id') or "default"
    if len(session_id) > 64 or not _SESSION_ID_RE.match(session_id):
        session_id = "default"

    return {
        "guide": guide,
        "question": question,
        "lang": lang,
        "session_id": session_id,
    }, None


@app.route('/api/guides/<slug>/chat', methods=['POST'])
@limiter.limit("15 per minute")
def chat(slug):
    """Chat with a specific guide's chatbot."""
    parsed, err = _parse_chat_request(slug)
    if err is not None:
        return err
    guide = parsed["guide"]
    question = parsed["question"]
    lang = parsed["lang"]
    session_id = parsed["session_id"]

    try:
        chatbot = get_guide_chatbot(slug)
        if _agent_enabled():
            response = chatbot.chat_agentic(question, lang=lang, session_id=session_id)
        else:
            response = chatbot.chat(question, lang=lang, session_id=session_id)

        return jsonify({
            "success": True,
            "response": response,
            "vehicle_name": guide.name,
        })

    except Exception as e:
        log.error("Chat error for guide %s: %s", slug, e)
        return jsonify({
            "success": False,
            "error": "Une erreur interne est survenue. Veuillez réessayer."
        }), 500


@app.route('/api/guides/<slug>/chat/stream', methods=['POST'])
@limiter.limit("15 per minute")
def chat_stream(slug):
    """Stream chat tokens from a specific guide chatbot using SSE."""
    parsed, err = _parse_chat_request(slug)
    if err is not None:
        return err
    guide = parsed["guide"]
    question = parsed["question"]
    lang = parsed["lang"]
    session_id = parsed["session_id"]

    try:
        chatbot = get_guide_chatbot(slug)
    except Exception as e:
        log.error("Chat stream init error for guide %s: %s", slug, e)
        return jsonify({
            "success": False,
            "error": "Une erreur interne est survenue. Veuillez réessayer."
        }), 500

    @stream_with_context
    def event_stream():
        log.info("[SSE %s] stream_opened use_agent=%s lang=%s", slug, _agent_enabled(), lang)
        yield _sse_event("start", {
            "success": True,
            "vehicle_name": guide.name,
        })
        event_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        fallback_started = False
        fallback_completed = False
        fallback_started_at = 0.0
        request_started_at = time.monotonic()
        first_chunk_received = False
        # Poll faster than STREAM_HEARTBEAT_SECONDS so chunks don't sit in the
        # queue while the reader naps. The ping comment is decoupled below.
        stream_poll_timeout = 0.2
        ping_interval = max(5.0, min(STREAM_HEARTBEAT_SECONDS, 20.0))
        last_ping_at = time.monotonic()
        stream_stall_timeout = 18.0
        fallback_deadline = 14.0

        def _start_fallback(reason: str = "error"):
            nonlocal fallback_started, fallback_started_at
            if fallback_started:
                return
            fallback_started = True
            fallback_started_at = time.monotonic()
            log.warning("Starting sync fallback for guide %s (reason=%s)", slug, reason)

            def _run_fallback():
                try:
                    # Inherit the original query's routing (web vs manual) instead
                    # of hardcoding manual_only — otherwise users asking
                    # recall/price/regulation questions get a manual-only answer
                    # that diverges from what the stream would have produced.
                    if use_agent:
                        fallback_response = chatbot.chat_agentic(
                            question,
                            lang=lang,
                            session_id=session_id,
                        )
                    else:
                        fallback_response = chatbot.chat(
                            question,
                            lang=lang,
                            session_id=session_id,
                            llm_timeout_cap_seconds=12,
                            max_output_tokens_cap=2000,
                        )
                    event_queue.put(("fallback_result", fallback_response))
                except Exception as fallback_exc:
                    event_queue.put(("fallback_error", fallback_exc))

            Thread(
                target=_run_fallback,
                name=f"chat-fallback-{slug}",
                daemon=True,
            ).start()

        use_agent = _agent_enabled()
        stream_fn = chatbot.chat_stream_agentic if use_agent else chatbot.chat_stream

        def _produce():
            log.info("[SSE %s] _produce START fn=%s", slug, stream_fn.__name__)
            count = 0
            try:
                for item in stream_fn(question, lang=lang, session_id=session_id):
                    count += 1
                    event_queue.put(("event", item))
            except Exception as exc:
                log.exception("chat stream crashed slug=%s: %s", slug, exc)
                event_queue.put(("error", exc))
            finally:
                log.info("[SSE %s] _produce EXIT events=%d", slug, count)
                event_queue.put(("done", None))

        Thread(target=_produce, name=f"chat-stream-{slug}", daemon=True).start()
        try:
            ended = False
            streamed_parts: list[str] = []
            last_message_id = ""
            while True:
                try:
                    kind, payload = event_queue.get(timeout=stream_poll_timeout)
                except queue.Empty:
                    now = time.monotonic()
                    if (now - last_ping_at) >= ping_interval:
                        yield _sse_comment("ping")
                        last_ping_at = now
                    if (
                        not ended
                        and not fallback_started
                        and not first_chunk_received
                        and (now - request_started_at) >= stream_stall_timeout
                    ):
                        _start_fallback("stall_no_chunk")
                    if (
                        fallback_started
                        and not fallback_completed
                        and fallback_started_at > 0.0
                        and (now - fallback_started_at) >= fallback_deadline
                    ):
                        # Mark fallback as terminated BEFORE yielding so a late
                        # fallback_result landing in the queue is ignored
                        # instead of emitting a second end event.
                        fallback_completed = True
                        yield _sse_event("end", {
                            "success": True,
                            "vehicle_name": guide.name,
                            "message_id": last_message_id,
                            "response": "La réponse a pris trop de temps. Réessayez dans un instant.",
                        })
                        ended = True
                        break
                    continue

                if kind == "done":
                    if fallback_started and not fallback_completed:
                        continue
                    break
                if kind == "error":
                    stream_error = payload
                    if ended:
                        log.warning("Chat stream post-end error for guide %s: %s", slug, stream_error)
                        break

                    log.error("Chat stream error for guide %s, switching to sync fallback: %s", slug, stream_error)
                    _start_fallback("stream_error")
                    continue

                if kind == "fallback_error":
                    fallback_completed = True
                    log.error("Chat stream sync fallback failed for guide %s: %s", slug, payload)
                    fallback_response = "Une erreur interne est survenue. Veuillez réessayer."
                    yield _sse_event("end", {
                        "success": True,
                        "vehicle_name": guide.name,
                        "message_id": last_message_id,
                        "response": fallback_response,
                    })
                    ended = True
                    break

                if kind == "fallback_result":
                    if ended or fallback_completed:
                        # Deadline timer or natural stream end already closed
                        # the response — drop the late result instead of
                        # emitting a second end event.
                        log.debug("Ignoring late fallback_result for guide %s", slug)
                        break
                    fallback_completed = True
                    fallback_response = payload
                    if not isinstance(fallback_response, str) or not fallback_response.strip():
                        fallback_response = "Une erreur interne est survenue. Veuillez réessayer."
                    fallback_response = fallback_response.strip()

                    streamed_so_far = "".join(streamed_parts)
                    # Only append the missing suffix when the streamed text is
                    # a clean prefix of the fallback. Divergent text would
                    # otherwise be spliced on top and produce duplicates.
                    if streamed_parts:
                        fallback_chunk = _compute_fallback_chunk(
                            streamed_so_far,
                            fallback_response,
                        )
                        if fallback_chunk:
                            yield _sse_event("chunk", {
                                "text": fallback_chunk,
                                "message_id": last_message_id,
                            })
                            streamed_parts.append(fallback_chunk)
                            final_response = streamed_so_far + fallback_chunk
                        else:
                            # Stream and fallback diverged — keep what was
                            # already streamed; do not splice new content.
                            final_response = streamed_so_far or fallback_response
                    else:
                        # No chunks streamed yet — emit the fallback as a
                        # single chunk so the UI runs its typing animation
                        # instead of popping the whole answer in on `end`.
                        yield _sse_event("chunk", {
                            "text": fallback_response,
                            "message_id": last_message_id,
                        })
                        streamed_parts.append(fallback_response)
                        final_response = fallback_response

                    yield _sse_event("end", {
                        "success": True,
                        "vehicle_name": guide.name,
                        "message_id": last_message_id,
                        "response": final_response,
                    })
                    ended = True
                    break

                event = payload
                event_type = str(event.get("type", "")).strip().lower()
                mid = event.get("message_id", "")
                if mid:
                    last_message_id = mid
                if event_type == "chunk":
                    chunk_text = str(event.get("text", ""))
                    if chunk_text:
                        first_chunk_received = True
                        streamed_parts.append(chunk_text)
                        yield _sse_event("chunk", {"text": chunk_text, "message_id": mid})
                elif event_type == "end":
                    if ended:
                        continue
                    end_payload = {
                        "success": True,
                        "vehicle_name": guide.name,
                        "message_id": mid,
                    }
                    response_text = event.get("response")
                    if isinstance(response_text, str):
                        end_payload["response"] = response_text
                    if "confidence" in event:
                        end_payload["confidence"] = event["confidence"]
                    if "fix_mode" in event:
                        end_payload["fix_mode"] = event["fix_mode"]
                    if "metrics" in event and isinstance(event["metrics"], dict):
                        end_payload["metrics"] = event["metrics"]
                    if "sources_structured" in event and isinstance(event["sources_structured"], list):
                        end_payload["sources_structured"] = event["sources_structured"]
                    if "video" in event and isinstance(event["video"], dict):
                        end_payload["video"] = event["video"]
                    yield _sse_event("end", end_payload)
                    ended = True
                    # Cancel any still-running fallback timer since the stream
                    # landed cleanly — prevents the deadline from firing a
                    # second end event after the real one was emitted.
                    fallback_completed = True
                elif event_type == "status":
                    yield _sse_event("status", {"step": event.get("step", ""), "message_id": mid})
                elif event_type == "sources_start":
                    yield _sse_event("sources_start", {"message_id": mid})
                elif event_type == "source_item":
                    yield _sse_event("source_item", {
                        "message_id": mid,
                        "source": event.get("source", {}),
                    })
                elif event_type == "sources_end":
                    yield _sse_event("sources_end", {"message_id": mid})
                elif event_type == "video_result":
                    yield _sse_event("video_result", {
                        "message_id": mid,
                        "title": event.get("title", ""),
                        "url": event.get("url", ""),
                        "thumbnail": event.get("thumbnail", ""),
                    })
                elif event_type == "video_none":
                    yield _sse_event("video_none", {"message_id": mid})
            if not ended:
                yield _sse_event("end", {
                    "success": True,
                    "vehicle_name": guide.name,
                })
        except Exception as e:
            log.error("Chat stream error for guide %s: %s", slug, e)
            yield _sse_event("end", {
                "success": True,
                "vehicle_name": guide.name,
                "response": "Une erreur interne est survenue. Veuillez réessayer.",
            })

    response = Response(event_stream(), mimetype="text/event-stream; charset=utf-8")
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["Connection"] = "keep-alive"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Content-Encoding"] = "identity"
    return response


@app.route('/api/guides/<slug>/history', methods=['GET'])
def get_history(slug):
    """Get conversation history for a guide chatbot."""
    guide = guide_manager.get_guide(slug)
    if not guide or not guide.is_indexed:
        return jsonify({
            "success": False,
            "error": "Guide introuvable"
        }), 404

    session_id = request.args.get("session_id", "default")
    if len(session_id) > 64 or not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        session_id = "default"

    try:
        chatbot = get_guide_chatbot(slug)
        return jsonify({
            "success": True,
            "history": chatbot.get_history(session_id=session_id),
            "vehicle_name": guide.name,
        })
    except Exception as e:
        log.error("History error for guide %s: %s", slug, e)
        return jsonify({
            "success": False,
            "error": "Une erreur interne est survenue."
        }), 500


@app.route('/api/guides/<slug>/reset', methods=['POST'])
@limiter.limit("10 per minute")
def reset_chat(slug):
    """Reset conversation history for a guide session."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or "default"
    if len(session_id) > 64 or not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        session_id = "default"

    guide = guide_manager.get_guide(slug)
    if not guide or not guide.is_indexed:
        return jsonify({
            "success": False,
            "error": "Guide introuvable"
        }), 404

    try:
        chatbot = get_guide_chatbot(slug)
        chatbot.clear_history(session_id=session_id)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "message": "Conversation reinitialisee"
    })


# ============================================
# IMAGE SERVING
# ============================================

@app.route('/api/images/<path:filename>', methods=['GET'])
def serve_image(filename):
    """Serve car images from configured image directories."""
    if '..' in filename or filename.startswith('/'):
        return jsonify({"error": "Invalid filename"}), 400

    for image_dir in IMAGE_DIRS:
        if not image_dir.exists():
            continue
        candidate = image_dir / filename
        try:
            candidate.resolve().relative_to(image_dir.resolve())
        except ValueError:
            return jsonify({"error": "Invalid filename"}), 400
        if candidate.exists() and candidate.is_file():
            return send_from_directory(str(image_dir), filename)
    return jsonify({"error": "Image not found"}), 404


# ============================================
# UTILITY ENDPOINTS
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "guides": len(guide_manager.list_guides()),
    })


@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    suggestions = [
        {"id": 1, "text": "Comment fonctionne le systeme de freinage ?", "category": "mecanique"},
        {"id": 2, "text": "Quelle est la pression recommandee des pneus ?", "category": "entretien"},
        {"id": 3, "text": "Que signifie le voyant moteur allume ?", "category": "diagnostic"},
        {"id": 4, "text": "Comment faire une vidange ?", "category": "entretien"},
        {"id": 5, "text": "Quelle est la capacite du reservoir ?", "category": "caracteristiques"},
        {"id": 6, "text": "Comment connecter mon telephone en Bluetooth ?", "category": "multimedia"},
    ]

    return jsonify({
        "success": True,
        "suggestions": suggestions
    })


@app.route('/api/waitlist/premium', methods=['POST'])
@limiter.limit("5 per minute")
def save_premium_waitlist_email():
    """Save a premium waitlist email in backend/data/waitlist/premium_waitlist.csv."""
    data = request.get_json(silent=True) or {}
    raw_email = str(data.get("email", "")).strip().lower()
    lang = str(data.get("lang", "")).strip().lower()[:10]
    source = str(data.get("source", "")).strip()[:120]

    if not EMAIL_REGEX.match(raw_email):
        return jsonify({
            "success": False,
            "error": "invalid_email",
        }), 400

    try:
        WAITLIST_DIR.mkdir(parents=True, exist_ok=True)

        with WAITLIST_LOCK:
            existing_emails = set()
            if WAITLIST_FILE.exists():
                with WAITLIST_FILE.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing = str(row.get("email", "")).strip().lower()
                        if existing:
                            existing_emails.add(existing)

            if raw_email in existing_emails:
                return jsonify({
                    "success": True,
                    "already_exists": True,
                }), 200

            write_header = not WAITLIST_FILE.exists() or WAITLIST_FILE.stat().st_size == 0
            with WAITLIST_FILE.open("a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=WAITLIST_COLUMNS)
                if write_header:
                    writer.writeheader()
                writer.writerow({
                    "email": _csv_safe(raw_email),
                    "lang": _csv_safe(lang),
                    "source": _csv_safe(source),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

        return jsonify({
            "success": True,
            "already_exists": False,
        }), 201
    except Exception:
        return jsonify({
            "success": False,
            "error": "waitlist_write_failed",
        }), 500


# ============================================
# GARAGE BETA (experimental, additive)
# ============================================
try:
    from garage_endpoints import register_garage_routes
    register_garage_routes(app, limiter)
    log.info("Garage Beta routes registered")
except Exception as _garage_exc:  # never block legacy routes
    log.warning("Garage Beta routes not loaded: %s", _garage_exc)


# ============================================
# FRONTEND (SPA) SERVING
# ============================================

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """Serve built frontend assets and SPA routes."""
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404

    if FRONTEND_DIST_DIR.exists():
        requested = FRONTEND_DIST_DIR / path
        if path and requested.exists() and requested.is_file():
            return send_from_directory(str(FRONTEND_DIST_DIR), path)

        index_file = FRONTEND_DIST_DIR / "index.html"
        if index_file.exists():
            response = send_from_directory(str(FRONTEND_DIST_DIR), "index.html")
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    return jsonify({"error": "Frontend build not found"}), 404


if __name__ == '__main__':
    _maybe_start_prewarm()
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "your_google_api_key_here":
        print("\n WARNING: GOOGLE_API_KEY is not set or invalid!")
        print(" Create a .env file with: GOOGLE_API_KEY=your_key")
        print(" Get a key at: https://aistudio.google.com/app/apikey\n")

    port = int(os.getenv("PORT", 5002))
    guides = guide_manager.list_guides()
    print("\n API Vehicle Guide Chatbot v3.0")
    print(f" {len(guides)} guide(s) available")
    for g in guides:
        print(f"   - {g['name']} ({g['slug']})")
    print(f" Server starting on http://localhost:{port}\n")
    is_debug = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    if is_debug and os.getenv("PORT"):
        print("WARNING: FLASK_DEBUG=true with PORT set. Disabling debug for safety.")
        is_debug = False
    app.run(host='127.0.0.1', port=port, debug=is_debug, use_reloader=False)
