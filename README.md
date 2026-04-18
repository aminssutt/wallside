# CarChat — Assistant documentaire intelligent pour véhicules

Application full-stack qui transforme des manuels constructeur PDF (entretien,
dépannage, fonctionnalités) en assistant conversationnel spécialisé par
véhicule. L'utilisateur choisit un guide, pose une question en français /
anglais / coréen et obtient une réponse sourcée dans le manuel.

## Stack

| Couche       | Technologies                                                 |
|--------------|--------------------------------------------------------------|
| Backend      | Python 3.12, Flask, LangChain, FAISS, BM25, Google Gemini    |
| Frontend     | React 19, Vite, React Router, Framer Motion                  |
| Déploiement  | Dokploy (Docker Compose)                                     |

## Arborescence

```
.
├── backend/
│   ├── api.py                     # Serveur Flask (point d'entrée)
│   ├── gunicorn.conf.py           # Config runtime Gunicorn (SSE friendly)
│   ├── requirements.txt
│   ├── .env.example
│   ├── src/                       # Bibliothèque métier
│   │   ├── config.py              # Variables d'env + constantes
│   │   ├── guide_manager.py       # Catalogue des guides pré-indexés
│   │   ├── guide_chatbot.py       # Pipeline RAG + streaming
│   │   ├── text_chunker.py        # Chunking sémantique
│   │   └── vector_store.py        # FAISS + BM25
│   ├── scripts/                   # CLIs d'orchestration
│   │   ├── add_manual.py          # Ajouter un manuel utilisateur
│   │   ├── index_manuals.py       # Indexation principale
│   │   ├── ingest_vehicle.py      # Ingestion d'un véhicule (générique)
│   │   ├── ingest_tesla.py        # Pipeline Tesla
│   │   ├── batch_images.py        # Batch images + suppression fond
│   │   ├── fetch_vehicle_images.py
│   │   ├── process_vehicle_images.py
│   │   └── batches/               # Vagues d'ingestion historiques
│   │       ├── batch_ingest.py
│   │       ├── batch_ingest2.py
│   │       ├── batch_ingest4.py
│   │       ├── batch_ingest5.py
│   │       └── batch_vintage.py
│   ├── tests/                     # Pytest + scripts de qualité RAG
│   └── data/                      # Index FAISS/BM25 pré-calculés
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── i18n.js
│       ├── api.js
│       ├── toast.jsx
│       ├── assets/
│       └── pages/
│           ├── LandingPage.jsx
│           ├── GuidesPage.jsx
│           ├── ChatPage.jsx
│           └── LegalPage.jsx
├── docs/                          # Business plan, notes techniques
├── manuel/                        # PDF utilisateur (exemples)
├── car data/                      # PDF servis en production
├── Dockerfile
├── docker-compose.yml             # Déploiement Dokploy
├── deploy-prod.ps1
├── start-dev.ps1                  # Lance backend + frontend (Windows)
└── start-dev.cmd
```

## Installation

### Prérequis
- Python 3.12+
- Node.js 18+
- Clé API Google Gemini ([obtenir ici](https://aistudio.google.com/app/apikey))

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     # Linux / macOS
# .venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env          # Ajouter GOOGLE_API_KEY
python api.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

API : `http://localhost:5002`
Frontend : `http://localhost:5173`

Sur Windows, `start-dev.ps1` lance les deux en parallèle et nettoie les ports.

## Données non versionnées

Pour rester léger et éviter les fuites, le dépôt ignore :

- `backend/data/guides/*/vector_store/*` — index FAISS et BM25 des manuels
- `backend/data/waitlist/*` — données waitlist
- `.env`, `.env.prod` — secrets
- Les PDF constructeur sont servis depuis `car data/` (versionné pour la prod)

### Re-générer les guides après un clone

1. Placer les PDF dans `car data/<marque>/*.pdf`
2. Lancer l'indexation depuis `backend/` :

```bash
cd backend
python scripts/index_manuals.py --prune-missing-sources
```

3. Redémarrer l'API (`python api.py`)

### Images véhicules

- Fichiers dans `backend/data/vehicle_images/`
- Nom conventionnel : `<marque> <modèle>.png`
- Retraitement local (suppression de fond) :

```bash
cd backend
python scripts/process_vehicle_images.py
```

## Endpoints API principaux

| Méthode | Route                               | Description                          |
|---------|-------------------------------------|--------------------------------------|
| GET     | `/api/guides`                       | Liste des guides pré-indexés         |
| GET     | `/api/guides/<slug>`                | Détails d'un guide                   |
| GET     | `/api/guides/<slug>/pdf`            | PDF constructeur du guide            |
| POST    | `/api/guides/<slug>/chat`           | Question synchrone                   |
| POST    | `/api/guides/<slug>/chat/stream`    | Question avec streaming SSE          |
| GET     | `/api/guides/<slug>/history`        | Historique de session                |
| POST    | `/api/guides/<slug>/reset`          | Réinitialiser l'historique           |
| GET     | `/api/health`                       | Healthcheck                          |

## Tests

Depuis `backend/` :

```bash
python -m pytest tests/ -q
```

La suite couvre le fallback de streaming, la force du contexte manuel, les
timeouts d'enrichissement et le pipeline RAG complet. Le script
`tests/test_rag_quality.py` est un harnais QA manuel (nécessite une
`GOOGLE_API_KEY`).

## Déploiement

Production : Dokploy (Docker Compose).

- Build frontend intégré à l'image Docker via `VITE_API_URL` (défaut `/api`)
- Reverse-proxy Traefik / Dokploy pour TLS + domaine
- Les secrets (`GOOGLE_API_KEY`, `FRONTEND_URL`) sont injectés au runtime

## Auteur

Lakhdar Berache — [carchat.online](https://carchat.online)
