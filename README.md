# AurisTraining — Assistant documentaire intelligent pour véhicules

AurisTraining est une application full-stack qui transforme des manuels PDF (entretien, dépannage, fonctionnalités) en assistant conversationnel spécialisé par véhicule.

Objectif : permettre à un utilisateur d’obtenir des réponses contextualisées à partir de ses propres documents techniques, sans recherche manuelle dans des centaines de pages.

## Aperçu du projet

Le produit suit un flux simple et orienté usage :

1. Création d’une session véhicule
2. Upload de documents PDF
3. Traitement des documents (extraction, chunking, indexation)
4. Conversation avec un chatbot RAG dédié à la session

## Problème traité

Les manuels techniques sont longs, peu ergonomiques à consulter et difficiles à exploiter en situation réelle (panne, maintenance, question précise).

## Solution apportée

Le backend construit une base de connaissances vectorielle à partir des PDFs uploadés, puis expose une API de chat qui récupère les passages pertinents avant génération de réponse.

## Stack technique

### Backend
- Python
- Flask
- LangChain
- ChromaDB
- Google Gemini
- sentence-transformers

### Frontend
- React
- Vite
- React Router
- ESLint

## Fonctionnalités

- Sessions isolées par véhicule
- Upload de plusieurs PDFs
- Traitement asynchrone avec suivi de statut
- Chat contextuel basé sur les documents de la session
- API REST claire pour l’orchestration frontend/backend

## Architecture

```text
AurisTraining/
├── backend/
│   ├── api.py                  # API Flask principale
│   ├── main.py                 # Point d’entrée alternatif
│   ├── requirements.txt
│   ├── src/
│   │   ├── config.py
│   │   ├── session_manager.py
│   │   ├── pdf_processor.py
│   │   ├── session_chatbot.py
│   │   ├── chatbot.py
│   │   ├── vector_store.py
│   │   └── pdf_loader.py
│   └── test_*.py
└── frontend/
    ├── package.json
    ├── src/
    │   ├── pages/
    │   │   ├── UploadPage.jsx
    │   │   ├── ProcessingPage.jsx
    │   │   └── ChatPage.jsx
    │   ├── App.jsx
    │   └── main.jsx
    └── vite.config.js
```

## Installation

### Prérequis
- Python 3.10+
- Node.js 18+
- npm 9+
- Une clé `GOOGLE_API_KEY`

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env
```

Éditer `.env` et renseigner au minimum :

```env
GOOGLE_API_KEY=...
FRONTEND_URL=http://localhost:5173
```

Lancer l’API :

```bash
python api.py
```

### 2) Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Usage

1. Ouvrir l’interface frontend.
2. Créer une session en renseignant le véhicule.
3. Uploader un ou plusieurs manuels PDF.
4. Lancer le traitement.
5. Poser des questions techniques dans le chat.

## Endpoints principaux

- `POST /api/session/create`
- `POST /api/session/{id}/upload`
- `POST /api/session/{id}/process`
- `GET /api/session/{id}/status`
- `POST /api/session/{id}/chat`
- `GET /api/health`

## Ce que ce projet démontre

- Conception d’un pipeline RAG de bout en bout
- Structuration d’une API Flask orientée produit
- Intégration frontend/backend avec gestion de flux utilisateur
- Organisation modulaire du code (traitement, session, vector store)
- Prise en compte des environnements de déploiement (Render/Vercel)

## Axes d’amélioration

- Standardiser un seul point d’entrée backend (`api.py` ou `main.py`)
- Ajouter des tests automatisés backend exécutables en CI
- Ajouter des tests frontend (Vitest/RTL)
- Renommer certains fichiers backend pour expliciter les responsabilités (ex: `session_chatbot.py` → `session_rag_service.py`)
- Centraliser les scripts de dev dans un `Makefile` racine

## Auteur

**Amine S.**

Projet portfolio orienté software craftsmanship : lisibilité, modularité et documentation opérationnelle.
