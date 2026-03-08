# Car Chat : CC — Assistant documentaire intelligent pour vehicules

Application full-stack qui transforme des manuels PDF (entretien, depannage, fonctionnalites) en assistant conversationnel specialise par vehicule.

Permet d'obtenir des reponses contextualisees a partir de documents techniques, sans recherche manuelle dans des centaines de pages.

## Fonctionnalites

- **Sessions isolees** par vehicule avec upload multi-PDF
- **Pipeline RAG optimise** : extraction parallele, chunking intelligent par sections, filtrage des pages inutiles
- **Recherche hybride** : FAISS (semantique) + BM25 (lexicale) pour une meilleure pertinence
- **Traitement asynchrone** avec suivi de progression en temps reel
- **Chat contextuel** base uniquement sur les documents de la session

## Stack technique

| Couche | Technologies |
|--------|-------------|
| **Backend** | Python, Flask, LangChain, FAISS, BM25, Google Gemini |
| **Frontend** | React 19, Vite, React Router, Framer Motion |
| **Deploiement** | Render (backend), Vercel (frontend) |

## Architecture

```
backend/
├── api.py                  # API Flask (point d'entree)
├── requirements.txt
├── render.yaml             # Config deploiement Render
└── src/
    ├── config.py           # Configuration & variables d'env
    ├── session_manager.py  # Gestion des sessions utilisateur
    ├── pdf_processor.py    # Pipeline : extraction → chunking → indexation
    ├── text_chunker.py     # Chunking intelligent par sections
    ├── vector_store.py     # FAISS vector store
    └── session_chatbot.py  # RAG chatbot avec recherche hybride

frontend/
├── vercel.json             # Config deploiement Vercel
└── src/
    ├── App.jsx
    └── pages/
        ├── LandingPage.jsx
        ├── UploadPage.jsx
        ├── ProcessingPage.jsx
        └── ChatPage.jsx
```

## Installation

### Prerequis
- Python 3.10+
- Node.js 18+
- Cle API Google Gemini ([obtenir ici](https://aistudio.google.com/app/apikey))

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env        # Editer et ajouter GOOGLE_API_KEY
python api.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

L'API tourne sur `http://localhost:5002`, le frontend sur `http://localhost:5173`.

## Endpoints API

| Methode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/session/create` | Creer une session vehicule |
| `POST` | `/api/session/{id}/upload` | Uploader un PDF |
| `POST` | `/api/session/{id}/process` | Lancer le traitement |
| `GET` | `/api/session/{id}/status` | Statut de la session |
| `POST` | `/api/session/{id}/chat` | Poser une question |
| `GET` | `/api/health` | Verification de sante |

## Deploiement

- **Backend** → [Render](https://render.com) (Free tier, config dans `render.yaml`)
- **Frontend** → [Vercel](https://vercel.com) (Free tier, config dans `vercel.json`)

Variable d'environnement Vercel : `VITE_API_URL=https://your-app.onrender.com/api`

## Auteur

**Amine S.**

