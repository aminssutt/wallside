"""
API Flask for the pre-indexed vehicle guide chatbot.
"""
import csv
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from src.guide_manager import guide_manager
from src.guide_chatbot import get_guide_chatbot, clear_guide_chatbot_cache
from src.config import DATA_DIR

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIST_DIR = Path(
    os.getenv("FRONTEND_DIST_DIR", PROJECT_ROOT / "frontend" / "dist")
)

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

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

@app.route('/api/guides', methods=['GET'])
def list_guides():
    """List all available pre-indexed guides."""
    brand = request.args.get("brand", "").strip() or None
    guides = guide_manager.list_guides(brand=brand)
    return jsonify({
        "success": True,
        "guides": guides,
        "brands": guide_manager.list_brands(),
    })


@app.route('/api/guides/<slug>', methods=['GET'])
def get_guide(slug):
    """Get details for a specific guide."""
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
def chat(slug):
    """Chat with a specific guide's chatbot."""
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

    lang = data.get('lang') or None
    if lang and lang not in ('fr', 'en', 'ko'):
        lang = None

    try:
        chatbot = get_guide_chatbot(slug)
        response = chatbot.chat(question, lang=lang)

        return jsonify({
            "success": True,
            "response": response,
            "vehicle_name": guide.name,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/guides/<slug>/history', methods=['GET'])
def get_history(slug):
    """Get conversation history for a guide chatbot."""
    guide = guide_manager.get_guide(slug)
    if not guide or not guide.is_indexed:
        return jsonify({
            "success": False,
            "error": "Guide introuvable"
        }), 404

    try:
        chatbot = get_guide_chatbot(slug)
        return jsonify({
            "success": True,
            "history": chatbot.get_history(),
            "vehicle_name": guide.name,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/guides/<slug>/reset', methods=['POST'])
def reset_chat(slug):
    """Reset conversation history for a guide."""
    clear_guide_chatbot_cache(slug)
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
    for image_dir in IMAGE_DIRS:
        if not image_dir.exists():
            continue
        candidate = image_dir / filename
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
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
