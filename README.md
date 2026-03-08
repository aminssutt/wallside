# Car Chat CC — Assistant documentaire intelligent pour véhicules

![Backend Python](https://img.shields.io/badge/Backend-Python%203.12-3776AB?logo=python&logoColor=white)
![Frontend React](https://img.shields.io/badge/Frontend-React%2019-61DAFB?logo=react&logoColor=white)
![Deploy Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)
![RAG](https://img.shields.io/badge/IA-RAG%20(FAISS%20%2B%20BM25)-7A5AF8)

Application full-stack qui transforme des manuels PDF automobiles (entretien, dépannage, fonctionnalités) en assistant conversationnel spécialisé par véhicule.

L’objectif : obtenir des réponses fiables et contextualisées sans parcourir manuellement des centaines de pages techniques.

## Pourquoi ce projet ?

- 🔎 **Gain de temps** : accès direct aux informations utiles d’un manuel.
- 🧠 **Réponses contextualisées** : fondées uniquement sur les documents chargés.
- 🚗 **Organisation par véhicule** : chaque guide reste isolé dans sa session.
- ⚙️ **Architecture moderne** : backend IA + frontend React, prêts au déploiement.

## Fonctionnalités principales

- **Sessions isolées** par véhicule avec import de plusieurs PDF.
- **Pipeline RAG optimisé** : extraction, segmentation intelligente et indexation.
- **Recherche hybride** : FAISS (sémantique) + BM25 (lexicale).
- **Traitement asynchrone** avec suivi de progression.
- **Chat contextuel** basé strictement sur les contenus indexés.

## Stack technique

| Couche | Technologies |
|---|---|
| **Backend** | Python, Flask, LangChain, FAISS, BM25, Google Gemini |
| **Frontend** | React 19, Vite, React Router, Framer Motion |
| **Déploiement** | Render (backend + frontend) |

## Structure du dépôt

```text
AurisTraining/
├── backend/                # API Flask, pipeline RAG et configuration Render
├── frontend/               # Interface React
├── manuel/                 # Manuels PDF par véhicule
├── render.yaml             # Configuration Render racine (backend uniquement)
├── start-dev.cmd           # Démarrage local (Windows CMD)
└── start-dev.ps1           # Démarrage local (PowerShell)
```

## Architecture applicative (fichiers clés)

```text
backend/
├── api.py                  # Point d’entrée API Flask
├── add_manual.py           # Script d’ajout de nouveaux guides
├── index_manuals.py        # Réindexation des manuels
├── render.yaml             # Dans backend/: configuration complète (backend + frontend)
└── src/
    ├── config.py
    ├── guide_manager.py
    ├── text_chunker.py
    ├── vector_store.py
    └── guide_chatbot.py

frontend/
└── src/pages/
    ├── LandingPage.jsx
    ├── GuidesPage.jsx
    └── ChatPage.jsx
```

## Installation locale

### Prérequis

- Python 3.10+
- Node.js 18+
- Clé API Google Gemini ([obtenir une clé](https://aistudio.google.com/app/apikey))

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env        # Ajouter GOOGLE_API_KEY
python api.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Par défaut :
- API : `http://localhost:5002`
- Frontend : `http://localhost:5173`

## API (principales routes)

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/session/create` | Créer une session véhicule |
| `POST` | `/api/session/{id}/upload` | Ajouter un PDF |
| `POST` | `/api/session/{id}/process` | Lancer le traitement |
| `GET` | `/api/session/{id}/status` | Vérifier le statut |
| `POST` | `/api/session/{id}/chat` | Poser une question |
| `GET` | `/api/health` | Vérifier la santé de l’API |

## Déploiement (Render)

Le projet est déployé sur **Render pour le backend et le frontend** :

- `backend/render.yaml` définit :
  - un service web Python (`car-chat-cc-backend`)
  - un service statique frontend (`car-chat-cc-frontend`)

Variables d’environnement importantes :
- `GOOGLE_API_KEY`
- `FRONTEND_URL`
- `VITE_API_URL`

## Roadmap

- Ajouter progressivement plus de voitures et leurs manuels associés.
- Continuer à améliorer la qualité des réponses et la couverture documentaire.

## Auteur

**Lakhdar Berache**
