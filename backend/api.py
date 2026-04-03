"""
API Flask for the pre-indexed vehicle guide chatbot.
"""
import csv
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.guide_manager import guide_manager
from src.guide_chatbot import get_guide_chatbot, clear_guide_chatbot_cache
from src.config import DATA_DIR, ALLOWED_ORIGINS, MAX_MESSAGE_LENGTH

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("auris")

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
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # CSP is handled by the reverse proxy (Traefik / Dokploy) or vercel.json.
    # Setting it here was blocking eval, inline scripts, and API connections.
    return response

# Serve car images from data/vehicle_images first, then legacy manuel/voiture.
IMAGE_DIRS = [
    DATA_DIR / "vehicle_images",
    PROJECT_ROOT / "manuel" / "voiture",
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

    return jsonify({
        "success": True,
        "guide": guide.to_dict(),
    })


# ============================================
# CHAT ENDPOINTS
# ============================================

@app.route('/api/guides/<slug>/chat', methods=['POST'])
@limiter.limit("15 per minute")
def chat(slug):
    """Chat with a specific guide's chatbot."""
    if not _SLUG_RE.match(slug):
        return jsonify({"success": False, "error": "Invalid slug"}), 400
    guide = guide_manager.get_guide(slug)
    if not guide or not guide.is_indexed:
        return jsonify({
            "success": False,
            "error": "Guide introuvable"
        }), 404

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({
            "success": False,
            "error": "Message requis"
        }), 400

    question = data['message'].strip()
    if not question:
        return jsonify({
            "success": False,
            "error": "Message vide"
        }), 400

    if len(question) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "success": False,
            "error": f"Message trop long (max {MAX_MESSAGE_LENGTH} caracteres)"
        }), 400

    lang = data.get('lang') or None
    if lang and lang not in ('fr', 'en', 'ko'):
        lang = None

    session_id = data.get('session_id') or "default"

    try:
        chatbot = get_guide_chatbot(slug)
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
            "error": "Une erreur interne est survenue. Veuillez reessayer."
        }), 500


@app.route('/api/guides/<slug>/chat/stream', methods=['POST'])
@limiter.limit("15 per minute")
def chat_stream(slug):
    """Stream chat tokens from a specific guide chatbot using SSE."""
    if not _SLUG_RE.match(slug):
        return jsonify({"success": False, "error": "Invalid slug"}), 400
    guide = guide_manager.get_guide(slug)
    if not guide or not guide.is_indexed:
        return jsonify({
            "success": False,
            "error": "Guide introuvable"
        }), 404

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({
            "success": False,
            "error": "Message requis"
        }), 400

    question = data['message'].strip()
    if not question:
        return jsonify({
            "success": False,
            "error": "Message vide"
        }), 400

    if len(question) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "success": False,
            "error": f"Message trop long (max {MAX_MESSAGE_LENGTH} caracteres)"
        }), 400

    lang = data.get('lang') or None
    if lang and lang not in ('fr', 'en', 'ko'):
        lang = None

    session_id = data.get('session_id') or "default"

    try:
        chatbot = get_guide_chatbot(slug)
    except Exception as e:
        log.error("Chat stream init error for guide %s: %s", slug, e)
        return jsonify({
            "success": False,
            "error": "Une erreur interne est survenue. Veuillez reessayer."
        }), 500

    @stream_with_context
    def event_stream():
        yield _sse_event("start", {
            "success": True,
            "vehicle_name": guide.name,
        })
        try:
            ended = False
            for event in chatbot.chat_stream(question, lang=lang, session_id=session_id):
                event_type = str(event.get("type", "")).strip().lower()
                mid = event.get("message_id", "")
                if event_type == "chunk":
                    chunk_text = str(event.get("text", ""))
                    if chunk_text:
                        yield _sse_event("chunk", {"text": chunk_text, "message_id": mid})
                elif event_type == "end":
                    end_payload = {
                        "success": True,
                        "vehicle_name": guide.name,
                        "message_id": mid,
                    }
                    response_text = event.get("response")
                    if isinstance(response_text, str):
                        end_payload["response"] = response_text
                    yield _sse_event("end", end_payload)
                    ended = True
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
            yield _sse_event("error", {
                "success": False,
                "error": "Une erreur interne est survenue. Veuillez reessayer."
            })

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["Connection"] = "keep-alive"
    response.headers["X-Accel-Buffering"] = "no"
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
    session_id = data.get("session_id")

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
        "message": "API Vehicle Guide Chatbot",
        "version": "3.0.0",
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
                    "email": raw_email,
                    "lang": lang,
                    "source": source,
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
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "your_google_api_key_here":
        print("\n WARNING: GOOGLE_API_KEY is not set or invalid!")
        print(" Create a .env file with: GOOGLE_API_KEY=your_key")
        print(" Get a key at: https://aistudio.google.com/app/apikey\n")

    port = int(os.getenv("PORT", 5002))
    guides = guide_manager.list_guides()
    print(f"\n API Vehicle Guide Chatbot v3.0")
    print(f" {len(guides)} guide(s) available")
    for g in guides:
        print(f"   - {g['name']} ({g['slug']})")
    print(f" Server starting on http://localhost:{port}\n")
    is_debug = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    app.run(host='127.0.0.1', port=port, debug=is_debug, use_reloader=False)
