"""
API Flask for the pre-indexed vehicle guide chatbot.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from src.guide_manager import guide_manager
from src.guide_chatbot import get_guide_chatbot, clear_guide_chatbot_cache

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Serve car images from manuel/voiture/
IMAGES_DIR = Path(__file__).parent.parent / "manuel" / "voiture"


# ============================================
# GUIDE ENDPOINTS
# ============================================

@app.route('/api/guides', methods=['GET'])
def list_guides():
    """List all available pre-indexed guides."""
    guides = guide_manager.list_guides()
    return jsonify({
        "success": True,
        "guides": guides,
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
    """Serve car images from the manuel/voiture directory."""
    if not IMAGES_DIR.exists():
        return jsonify({"error": "Images directory not found"}), 404
    return send_from_directory(str(IMAGES_DIR), filename)


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
