# Contributing

Merci pour votre intérêt pour AurisTraining.

## Préparer l'environnement

1. Forker le dépôt puis créer une branche :
   - `feature/nom-court`
   - `fix/nom-court`
2. Installer les dépendances :

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

## Standards de contribution

- Produire des changements ciblés, lisibles et testables.
- Conserver une architecture modulaire (session, ingestion PDF, chat, UI pages).
- Éviter les commentaires redondants ; préférer des noms explicites.
- Ne jamais commiter de secrets (`.env`, clés API, credentials).

## Validation locale

Avant ouverture de PR :

```bash
cd frontend
npm run lint
npm run build
```

Le backend ne dispose pas encore d'une suite de tests automatisée exécutable via CI ; merci de décrire dans la PR la validation manuelle effectuée.

## Pull Request

Une PR de qualité contient :

- un contexte (problème traité),
- le changement proposé,
- les impacts éventuels,
- les étapes de vérification.

Merci de garder des PR petites et orientées une seule intention.
