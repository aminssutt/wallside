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
| **Deploiement** | Dokploy (Docker Compose) |

## Architecture

```
backend/
├── api.py                  # API Flask (point d'entree)
├── requirements.txt
└── src/
    ├── config.py           # Configuration & variables d'env
    ├── session_manager.py  # Gestion des sessions utilisateur
    ├── pdf_processor.py    # Pipeline : extraction → chunking → indexation
    ├── text_chunker.py     # Chunking intelligent par sections
    ├── vector_store.py     # FAISS vector store
    └── session_chatbot.py  # RAG chatbot avec recherche hybride

frontend/
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

## Donnees Locales (Non Versionnees)

Pour eviter de publier des donnees sensibles ou trop lourdes, le repo **ne versionne pas**:

- `backend/data/guides/*/vector_store/*` (indexes FAISS/BM25 issus des manuels)
- `backend/data/waitlist/*`
- les fichiers `.env`
- les PDF de manuels

### Regenerer les guides apres un clone

1. Mettre les PDF dans `car data/<marque>/*.pdf`
2. Lancer l'indexation:

```bash
cd backend
python index_manuals.py --prune-missing-sources
```

3. Redemarrer l'API Flask (`python api.py`)

### Images vehicules

- Les images front sont dans `backend/data/vehicle_images/`
- Nom recommande: nom du vehicule (exemple: `honda civic 11.png`)
- Si besoin de retraitement local:

```bash
cd backend
python process_vehicle_images.py
```

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

- **Production** → Dokploy via `docker-compose.yml`
- Build frontend integre dans l'image Docker avec `VITE_API_URL` (par defaut `/api`)
- Reverse proxy (Traefik/Dokploy) recommande pour TLS + domaine

### Nettoyage avant redeploiement serveur

Depuis la racine du projet (Windows PowerShell) :

```powershell
./clean-workspace.ps1
```

Options utiles :

- `./clean-workspace.ps1 -IncludeFrontendDist`
- `./clean-workspace.ps1 -IncludeFrontendDist -IncludeNodeModules`

## Auteur

**Amine S.**

