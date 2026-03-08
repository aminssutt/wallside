"""
API Flask pour le chatbot avec sessions utilisateur
"""
import os
import sys
from pathlib import Path

# Ajouter le répertoire src au path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from src.session_manager import session_manager, SessionStatus
from src.pdf_processor import process_session_pdfs
from src.session_chatbot import get_session_chatbot, clear_chatbot_cache

app = Flask(__name__)

# Configuration CORS
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "https://*.vercel.app",
]

FRONTEND_URL = os.getenv("FRONTEND_URL", "")
if FRONTEND_URL:
    ALLOWED_ORIGINS.append(FRONTEND_URL)

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Configuration upload
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB par fichier
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================
# ENDPOINTS SESSION
# ============================================

@app.route('/api/session/create', methods=['POST'])
def create_session():
    """Crée une nouvelle session"""
    try:
        data = request.get_json()
        
        if not data or 'vehicle_name' not in data:
            return jsonify({
                "success": False,
                "error": "Le nom du véhicule est requis"
            }), 400
        
        vehicle_name = data['vehicle_name'].strip()
        if not vehicle_name:
            return jsonify({
                "success": False,
                "error": "Le nom du véhicule ne peut pas être vide"
            }), 400
        
        session = session_manager.create_session(vehicle_name)
        
        return jsonify({
            "success": True,
            "session": session.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/session/<session_id>/upload', methods=['POST'])
def upload_pdf(session_id):
    """Upload un PDF pour une session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                "success": False,
                "error": "Session introuvable"
            }), 404
        
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "Aucun fichier fourni"
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "Aucun fichier sélectionné"
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                "success": False,
                "error": "Seuls les fichiers PDF sont acceptés"
            }), 400
        
        # Sauvegarder le fichier
        filename = secure_filename(file.filename)
        filepath = session.pdf_dir / filename
        file.save(str(filepath))
        
        # Ajouter à la liste des PDFs
        session_manager.add_pdf(session_id, filename)
        
        session_manager.update_progress(
            session_id,
            status=SessionStatus.UPLOADING,
            message=f"Fichier {filename} uploadé"
        )
        
        return jsonify({
            "success": True,
            "filename": filename,
            "message": f"Fichier {filename} uploadé avec succès"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/session/<session_id>/process', methods=['POST'])
def process_session(session_id):
    """Lance le traitement des PDFs d'une session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                "success": False,
                "error": "Session introuvable"
            }), 404
        
        if not session.pdf_files:
            return jsonify({
                "success": False,
                "error": "Aucun PDF uploadé"
            }), 400
        
        # Lancer le traitement en arrière-plan
        process_session_pdfs(session_id)
        
        return jsonify({
            "success": True,
            "message": "Traitement lancé"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/session/<session_id>/status', methods=['GET'])
def get_session_status(session_id):
    """Récupère le statut d'une session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                "success": False,
                "error": "Session introuvable"
            }), 404
        
        return jsonify({
            "success": True,
            "session": session.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/session/<session_id>/delete', methods=['DELETE'])
def delete_session(session_id):
    """Supprime une session"""
    try:
        clear_chatbot_cache(session_id)
        success = session_manager.delete_session(session_id)
        
        return jsonify({
            "success": success,
            "message": "Session supprimée" if success else "Session introuvable"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================
# ENDPOINTS CHAT
# ============================================

@app.route('/api/session/<session_id>/chat', methods=['POST'])
def chat(session_id):
    """Endpoint de chat pour une session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                "success": False,
                "error": "Session introuvable"
            }), 404
        
        if session.progress.status != SessionStatus.READY:
            return jsonify({
                "success": False,
                "error": "Le chatbot n'est pas encore prêt"
            }), 400
        
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                "success": False,
                "error": "Message requis"
            }), 400
        
        question = data['message']
        
        # Obtenir le chatbot de la session
        chatbot = get_session_chatbot(session_id)
        response = chatbot.chat(question)
        
        return jsonify({
            "success": True,
            "response": response,
            "vehicle_name": session.vehicle_name
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/session/<session_id>/history', methods=['GET'])
def get_history(session_id):
    """Récupère l'historique de conversation"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                "success": False,
                "error": "Session introuvable"
            }), 404
        
        chatbot = get_session_chatbot(session_id)
        
        return jsonify({
            "success": True,
            "history": chatbot.get_history(),
            "vehicle_name": session.vehicle_name
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================
# ENDPOINTS UTILITAIRES
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Vérification de santé de l'API"""
    return jsonify({
        "status": "ok",
        "message": "API Vehicle Chatbot opérationnelle",
        "version": "2.0.0"
    })


@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    """Suggestions de questions génériques"""
    suggestions = [
        {"id": 1, "text": "Comment fonctionne le système de freinage ?", "category": "mecanique"},
        {"id": 2, "text": "Quelle est la pression recommandée des pneus ?", "category": "entretien"},
        {"id": 3, "text": "Que signifie le voyant moteur allumé ?", "category": "diagnostic"},
        {"id": 4, "text": "Comment faire une vidange ?", "category": "entretien"},
        {"id": 5, "text": "Quelle est la capacité du réservoir ?", "category": "caracteristiques"},
        {"id": 6, "text": "Comment connecter mon téléphone en Bluetooth ?", "category": "multimedia"},
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
    print("\n API Vehicle Chatbot v2.0")
    print(" Sessions stockees dans: data/sessions/")
    print(f" Serveur demarre sur http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
