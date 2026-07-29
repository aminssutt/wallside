# Business Plan -- Mechora

**Assistant technique automobile propulse par l'IA**

*Date : Avril 2026*
*Version : 1.0*
*Auteur : Lakhdar Berache*

---

## Table des matieres

1. [Resume executif](#1-resume-executif)
2. [Le produit](#2-le-produit)
3. [Marche](#3-marche)
4. [Modele economique](#4-modele-economique)
5. [Go-to-Market](#5-go-to-market)
6. [Projections financieres](#6-projections-financieres-3-ans)
7. [Roadmap technique](#7-roadmap-technique)
8. [Equipe et besoins](#8-equipe--besoins)
9. [Risques et mitigation](#9-risques--mitigation)

---

## 1. Resume executif

### Vision

Mechora ambitionne de democratiser l'acces aux informations techniques automobiles. Aujourd'hui, lorsqu'un proprietaire de vehicule cherche a comprendre un voyant d'alerte, planifier un entretien ou diagnostiquer un probleme, il se retrouve face a des manuels de 400+ pages en PDF, des forums non structures et des videos YouTube de qualite variable. Mechora resout ce probleme en transformant chaque manuel constructeur en un assistant IA conversationnel capable de repondre en langage naturel, avec citation des pages exactes du document source.

### Proposition de valeur unique

- **Reponses sourcees** : chaque information cite la page exacte du manuel officiel du constructeur, contrairement aux LLM generiques (ChatGPT, Claude) qui hallucinent frequemment sur les donnees techniques specifiques.
- **Base de connaissances verifiee** : 143 vehicules de 34 marques, representant 53 659 pages de manuels et 117 442 chunks indexes.
- **Multilingue natif** : francais, anglais et coreen des le lancement.
- **Acces instantane** : aucun upload de PDF requis, les guides sont pre-indexes et disponibles immediatement.

### Marche cible

Le marche primaire est la France, avec 38,9 millions de vehicules en circulation et 46 millions de titulaires du permis de conduire. Mechora s'adresse en premier lieu aux proprietaires individuels (B2C) puis aux professionnels de l'automobile (B2B) : concessions, gestionnaires de flottes et centres d'entretien.

---

## 2. Le produit

### 2.1 Description detaillee

Mechora est une application web progressive (PWA-ready) qui permet a tout proprietaire de vehicule de poser des questions en langage naturel sur son vehicule et d'obtenir des reponses precises, structurees et sourcees depuis le manuel officiel du constructeur.

L'utilisateur selectionne son vehicule parmi un catalogue organise par marque et segment (citadine, SUV, berline, sportive, classique, utilitaire), puis ouvre une conversation. L'assistant repond en temps reel via streaming (SSE) et fournit :

- La reponse en Markdown formate (titres, listes, etapes numerotees)
- Les references exactes aux pages du manuel
- Un lien direct vers le PDF source
- Une suggestion de video YouTube pertinente (pour les questions procedurales)
- Un enrichissement web complementaire (rappels, prix, disponibilite)

### 2.2 Stack technique

| Couche | Technologie | Role |
|---|---|---|
| **LLM** | Google Gemini 2.5 Flash | Generation de reponses, comprehension du contexte |
| **Embeddings** | Gemini Embedding 001 | Vectorisation semantique des chunks |
| **Recherche vectorielle** | FAISS (faiss-cpu) | Recherche de similarite dense (semantic search) |
| **Recherche lexicale** | BM25 (rank-bm25) | Recherche par mots-cles avec scoring TF-IDF |
| **RAG Hybrid** | FAISS + BM25 fusion RRF | Reciprocal Rank Fusion pour combiner les deux retrieval |
| **Extraction PDF** | PyPDF + OCR | Extraction de texte depuis manuels scannees et natifs |
| **Chunking** | Section-aware splitter custom | Decoupe intelligente par sections avec filtrage des pages poubelles |
| **Backend** | Flask + Gunicorn + Gevent | API REST + SSE streaming |
| **Frontend** | React 19 + Vite 7 + Framer Motion | SPA avec animations fluides et lazy loading |
| **Routing** | React Router 7 | Navigation SPA avec 3 pages (Landing, Guides, Chat) |
| **Enrichissement Web** | DuckDuckGo Search (ddgs) | Recherche web complementaire sans cle API |
| **YouTube** | Scraping HTML YouTube | Suggestions video pertinentes sans API Key |
| **Conteneurisation** | Docker (multi-stage) | Build frontend Node 20 + Runtime Python 3.12 |
| **Rate Limiting** | Flask-Limiter | 120 req/min global, 15 req/min par chat, 5 req/min waitlist |
| **Securite** | Sanitization anti-injection, CSP, CORS, security headers | Protection contre les prompt injections et attaques web |
| **i18n** | Module i18n custom | 3 langues (FR, EN, KO) avec detection automatique |

### 2.3 Fonctionnalites cles (donnees reelles du code)

**Catalogue vehicules :**
- **143 vehicules** couverts
- **34 marques** : Alfa Romeo, Alpine, Audi, BMW, Chevrolet, Citroen, Cupra, DS, Dacia, Fiat, Ford, Genesis, Honda, Hyundai, Jaguar, Jeep, Kia, Lancia, Land Rover, Maserati, Mazda, Mercedes-Benz, Mitsubishi, Nissan, Opel, Peugeot, Renault, Seat, Subaru, Suzuki, Tesla, Toyota, Volkswagen, Volvo
- **53 659 pages** de manuels officiels indexees
- **117 442 chunks** dans la base vectorielle
- **7 segments** : citadine, SUV, berline, sportive, classique, utilitaire, monospace

**Intelligence conversationnelle :**
- Detection automatique de langue (FR/EN/KO) par analyse lexicale
- Mode "Fix" pour les questions procedurales (reponse structuree : objectif, difficulte, outils, etapes, attention)
- Filtrage des questions hors-sujet avec redirection vers des exemples utiles
- Detection des salutations, small talk, closures et fillers
- Score de confiance (high/medium/low) base sur la qualite du contexte RAG
- Routage intelligent des requetes : manual_only / web_blocking / web_async
- Protection contre les prompt injections (regex multi-patterns)
- Nettoyage automatique des sorties LLM (URLs parasites, blocs sources)
- Historique de conversation avec gestion par session_id
- Limite de 20 messages d'historique par conversation

**Interface utilisateur :**
- Landing page premium avec animations (glassmorphism, scroll reveal, word-by-word blur)
- Compteurs animes (vehicules, marques, pages analysees, langues)
- Demo de conversation interactive dans le hero
- Filtrage par marque, segment et recherche textuelle
- Carrousel de vehicules avec swipe mobile
- Questions rapides contextuelles par segment de vehicule
- Streaming SSE temps reel (token par token)
- Toast notifications
- Error boundary avec message multilingue
- Lazy loading des pages (code splitting)

**API et infrastructure :**
- 12 endpoints API REST (guides, chat, chat/stream, history, reset, images, pdf, health, suggestions, waitlist)
- Rate limiting a 3 niveaux (global, chat, waitlist)
- Security headers complets (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, Permissions-Policy)
- Validation d'entree stricte (slug regex, longueur message 3000 chars max, session_id format)
- Protection CSV injection sur la waitlist
- Serving statique du frontend SPA depuis le backend

### 2.4 Differenciation concurrentielle

| Critere | Mechora | ChatGPT / Claude | Forums auto | Garage |
|---|---|---|---|---|
| Source verifiee (page exacte) | Oui | Non (hallucinations) | Rarement | Verbal |
| Cout par question | ~0,001EUR | 20EUR/mois (abo) | Gratuit | 50-100EUR/diag |
| Specialise automobile | 143 vehicules | Generaliste | Par fil de discussion | Par vehicule |
| Temps de reponse | < 5 secondes | < 10 secondes | Heures/jours | Sur RDV |
| Multilingue | 3 langues | 50+ langues | Par forum | Langue locale |
| Procedure structuree | Mode Fix | Variable | Rarement | Oral |
| Disponibilite | 24/7 | 24/7 | Variable | Horaires ouvrables |

---

## 3. Marche

### 3.1 TAM (Total Addressable Market)

**Marche mondial de l'information technique automobile :**
- 1,4 milliard de vehicules en circulation dans le monde
- Marche mondial des services numeriques automobiles : ~45 milliards EUR en 2026
- En considerant que 5% des proprietaires paieraient pour un outil technique : ~70 millions de clients potentiels
- A 40EUR/an en moyenne : **TAM = ~2,8 milliards EUR/an**

### 3.2 SAM (Serviceable Addressable Market)

**Marche francophone + anglophone accessible :**
- France : 38,9 millions de vehicules, ~46 millions de titulaires du permis
- Europe francophone (Belgique, Suisse, Luxembourg) : ~10 millions de vehicules supplementaires
- Marche anglophone accessible (UK, Irlande) : ~35 millions de vehicules
- En ciblant les proprietaires connectes (60%) avec un taux d'adoption de 2% : ~1 million de clients potentiels
- **SAM = ~40 millions EUR/an**

### 3.3 SOM (Serviceable Obtainable Market)

**Objectif realiste a 3 ans :**
- France uniquement en priorite, expansion progressive
- Objectif : 15 000 utilisateurs premium + 50 contrats B2B
- **SOM = ~1,2 million EUR/an a l'horizon Annee 3**

### 3.4 Segments cibles

**B2C -- Proprietaires de vehicules :**
- Proprietaires bricoleurs / DIY (entretien courant)
- Nouveaux proprietaires cherchant a comprendre leur vehicule
- Proprietaires de vehicules d'occasion (pas de manuel papier)
- Conducteurs multilingues (expatries, frontaliers)

**B2B -- Concessionnaires et garages :**
- Service apres-vente (outil d'aide au diagnostic)
- Accueil client (reponses rapides aux questions courantes)
- Formation des techniciens juniors

**B2B -- Flottes et entreprises :**
- Gestionnaires de flottes multi-marques
- Societes de leasing (support premier niveau)
- Auto-ecoles (formation theorique)

### 3.5 Concurrence

**Concurrence directe :**
- **Aucun concurrent direct identique** combinant RAG sur manuels constructeurs + chat IA multilingue + sources verifiees
- Quelques initiatives fragmentees : chatbots constructeurs (limites a une marque), outils de diagnostic OBD-II (hardware)

**Concurrence indirecte :**
- ChatGPT / Claude / Gemini : generiques, pas de sources constructeur, hallucinations frequentes
- Forums (Forum-Auto, Forum-Peugeot, etc.) : lent, non structure, qualite variable
- YouTube : excellent pour les tutoriels visuels, mais pas de recherche textuelle structuree
- Manuels PDF bruts : disponibles mais inexploitables (400+ pages, pas de recherche intelligente)
- Garages : couteux (50-100EUR le diagnostic), horaires limites

---

## 4. Modele economique

### 4.1 B2C -- Freemium

| | Gratuit | Premium |
|---|---|---|
| **Prix** | 0EUR | 9,99EUR/mois |
| **Questions** | 10/jour | Illimitees |
| **Marques** | 34 marques | 34 marques |
| **Sources manuel** | Oui | Oui |
| **PDF sources directes** | Non | Oui |
| **Video YouTube** | Non | Oui |
| **Publicites** | Oui | Non |
| **Support** | Standard | Prioritaire |

**Prix constate sur la landing page actuelle :** Gratuit (10 questions/jour) et Premium a 9,99EUR/mois.

### 4.2 B2B -- Offre Entreprise

| Offre | Prix indicatif | Cible |
|---|---|---|
| Widget concessionnaire | 99-199EUR/mois | Concessions, garages |
| API integree | 0,05-0,20EUR/requete | Plateformes tierces |
| Entreprise sur devis | Sur mesure | Flottes, constructeurs |

L'offre Entreprise inclut : acces illimite pour toute l'equipe, API dediee, support 24/7, manuels personnalises, tableau de bord analytics, et partenariats constructeurs.

### 4.3 Structure de couts

**Couts variables par requete :**

| Poste | Cout unitaire | Detail |
|---|---|---|
| Gemini 2.5 Flash (generation) | ~0,0013EUR/requete | Input: ~5K tokens, Output: ~1K tokens |
| Gemini Embedding | ~0,0001EUR/requete | Vectorisation de la question |
| DuckDuckGo Search | 0EUR | API gratuite |
| YouTube scraping | 0EUR | Pas d'API payante |
| **Total par requete** | **~0,0014EUR** | |

**Couts fixes mensuels :**

| Poste | Cout mensuel | Detail |
|---|---|---|
| Hebergement serveur (VPS/Docker) | ~30EUR | Dokploy / Railway / VPS OVH |
| Domaine wallside.online | ~1EUR | Renouvellement annuel |
| Google API (base gratuite) | 0-15EUR | Tier gratuit generous puis pay-as-you-go |
| **Total fixe** | **~45EUR/mois** | |

### 4.4 Analyse du seuil de rentabilite

**Hypotheses :**
- Prix Premium moyen : 9,99EUR/mois
- Cout variable par utilisateur premium : ~2EUR/mois (estimant ~50 questions/mois a 0,0014EUR + marge serveur)
- Marge brute par premium : ~8EUR/mois
- Couts fixes : ~45EUR/mois (phase de demarrage)

**Break-even B2C :** 6 abonnes premium couvrent les couts fixes.

**Break-even avec salaire fondateur (2000EUR/mois) :** ~256 abonnes premium.

**Break-even avec equipe de 2 (6000EUR/mois charges incluses) :** ~755 abonnes premium.

---

## 5. Go-to-Market

### Phase 1 : Lancement France (Mois 1-3)

**Objectif : 1 000 utilisateurs gratuits, 50 premium**

| Action | Canal | Budget |
|---|---|---|
| Lancement Product Hunt | Product Hunt | 0EUR |
| Posts sur les forums auto FR | Forum-Auto, Forum-Peugeot, Clio-RS, etc. | 0EUR |
| SEO : pages de contenu par vehicule | Blog + Landing pages | 0EUR |
| Posts LinkedIn (reseau personnel) | LinkedIn | 0EUR |
| Subreddits auto (r/france, r/voiture) | Reddit | 0EUR |
| Groupes Facebook auto (Peugeot, Renault, etc.) | Facebook | 0EUR |
| Partenariat micro-influenceurs auto | YouTube / Instagram | 200-500EUR |
| **Total Phase 1** | | **200-500EUR** |

**Metriques cles :**
- Taux de conversion gratuit vers premium : objectif 5%
- Questions par utilisateur par jour : objectif 3-5
- NPS : objectif > 40
- Retention J30 : objectif > 30%

### Phase 2 : B2B Pilote (Mois 4-6)

**Objectif : 5 000 utilisateurs gratuits, 250 premium, 5 contrats B2B pilotes**

| Action | Detail |
|---|---|
| Prospection concessions | 5 concessions pilotes (Renault, Peugeot, Citroen) |
| Widget white-label | Version integrable pour les sites de concessionnaires |
| Offre d'essai gratuit 1 mois | Reduction de friction pour le B2B |
| Waitlist premium | Deja implementee dans le produit (endpoint API + CSV) |
| A/B testing landing | Optimisation du taux de conversion |

### Phase 3 : Scaling (Mois 7-12)

**Objectif : 15 000 utilisateurs, 1 000 premium, 20 contrats B2B**

| Action | Detail |
|---|---|
| SEA Google Ads | Ciblage "manuel [marque] [modele]", "voyant [marque]" |
| Partenariats ecoles mecaniques | Offre education gratuite |
| Expansion vehicules : 200+ modeles | Ajout marques asiatiques et americaines |
| App mobile (PWA) | Optimisation de l'experience mobile |
| Partenariats YouTube auto | Sponsoring sur chaines auto FR |

---

## 6. Projections financieres (3 ans)

### Annee 1 : Acquisition et validation

| Metrique | T1 | T2 | T3 | T4 | Total A1 |
|---|---|---|---|---|---|
| Utilisateurs gratuits | 500 | 2 000 | 5 000 | 10 000 | 10 000 |
| Abonnes premium | 25 | 100 | 300 | 600 | 600 |
| Contrats B2B | 0 | 2 | 5 | 10 | 10 |
| Revenus premium (EUR) | 750 | 3 000 | 9 000 | 18 000 | 30 750 |
| Revenus B2B (EUR) | 0 | 400 | 1 500 | 3 000 | 4 900 |
| **Revenus totaux** | **750** | **3 400** | **10 500** | **21 000** | **35 650** |
| Couts infrastructure | 200 | 300 | 500 | 800 | 1 800 |
| Couts API (Gemini) | 50 | 200 | 600 | 1 500 | 2 350 |
| Couts marketing | 200 | 500 | 1 000 | 2 000 | 3 700 |
| **Resultat net** | **+300** | **+2 400** | **+8 400** | **+16 700** | **+27 800** |

### Annee 2 : Scaling et B2B

| Metrique | Valeur A2 |
|---|---|
| Utilisateurs gratuits | 50 000 |
| Abonnes premium | 3 000 |
| Contrats B2B | 50 |
| Revenus premium | 360 000EUR |
| Revenus B2B | 120 000EUR |
| Revenus publicitaires | 15 000EUR |
| **Revenus totaux** | **495 000EUR** |
| Couts equipe (2 personnes) | 120 000EUR |
| Couts infrastructure | 18 000EUR |
| Couts API | 36 000EUR |
| Marketing | 40 000EUR |
| **Resultat net** | **+281 000EUR** |

### Annee 3 : Expansion internationale

| Metrique | Valeur A3 |
|---|---|
| Utilisateurs gratuits | 150 000 |
| Abonnes premium | 10 000 |
| Contrats B2B | 150 |
| Revenus premium | 1 200 000EUR |
| Revenus B2B | 450 000EUR |
| Revenus publicitaires | 50 000EUR |
| **Revenus totaux** | **1 700 000EUR** |
| Couts equipe (5 personnes) | 450 000EUR |
| Couts infrastructure | 60 000EUR |
| Couts API | 120 000EUR |
| Marketing | 150 000EUR |
| **Resultat net** | **+920 000EUR** |

### Projections cumulees

| | Annee 1 | Annee 2 | Annee 3 |
|---|---|---|---|
| Revenus cumules | 35 650EUR | 530 650EUR | 2 230 650EUR |
| Resultat cumule | 27 800EUR | 308 800EUR | 1 228 800EUR |

---

## 7. Roadmap technique

### 7.1 Ce qui est fait (etat actuel -- Avril 2026)

**Backend (Python/Flask) :**
- [x] Pipeline RAG hybride FAISS + BM25 avec fusion RRF
- [x] Integration Google Gemini 2.5 Flash (generation + embeddings)
- [x] Chunking intelligent section-aware avec filtrage des pages poubelles
- [x] Detection automatique de langue (FR/EN/KO)
- [x] Mode Fix pour les procedures (reponses structurees)
- [x] Routage intelligent des requetes (manual_only / web_blocking / web_async)
- [x] Score de confiance (high/medium/low)
- [x] Enrichissement web via DuckDuckGo Search
- [x] Suggestions YouTube sans API key
- [x] Streaming SSE token par token
- [x] Historique de conversation par session
- [x] Protection anti-injection de prompt
- [x] Rate limiting multi-niveaux
- [x] Sanitization des entrees et sorties
- [x] Gestion multi-manuels par vehicule (vehicule + multimedia system)
- [x] Serving du frontend SPA depuis le backend
- [x] Health check endpoint
- [x] Waitlist premium avec stockage CSV securise
- [x] Serving d'images et PDFs vehicules

**Frontend (React 19) :**
- [x] Landing page premium (glassmorphism, animations scroll, word reveal, compteurs animes)
- [x] Catalogue vehicules avec filtrage (marque, segment, recherche textuelle)
- [x] Chat en temps reel avec streaming SSE
- [x] Questions rapides contextuelles par segment
- [x] Demo conversationnelle interactive dans le hero
- [x] Internationalisation 3 langues (FR/EN/KO)
- [x] Grille tarifaire (Gratuit / Premium / Entreprise)
- [x] Section FAQ interactive
- [x] Section "A propos" avec profil fondateur
- [x] Formulaire de contact
- [x] Error boundary multilingue
- [x] Toast notifications
- [x] Code splitting et lazy loading
- [x] Responsive design (mobile, tablette, desktop)

**Infrastructure :**
- [x] Docker multi-stage (Node 20 build + Python 3.12 runtime)
- [x] Gunicorn + Gevent pour la production
- [x] Security headers complets
- [x] CORS configurable
- [x] 143 vehicules, 34 marques indexes

### 7.2 Phase 2 : Monetisation (Mois 1-3)

| Fonctionnalite | Priorite | Effort |
|---|---|---|
| Authentification utilisateur (OAuth Google/Email) | Critique | 2 semaines |
| Integration paiement (Stripe) | Critique | 2 semaines |
| Gestion des quotas (gratuit vs premium) | Critique | 1 semaine |
| Historique persistant (base de donnees) | Haute | 2 semaines |
| Tableau de bord utilisateur | Haute | 1 semaine |
| Migration SQLite/PostgreSQL | Haute | 1 semaine |
| Systeme de publicites (plan gratuit) | Moyenne | 1 semaine |

### 7.3 Phase 3 : Growth (Mois 4-6)

| Fonctionnalite | Priorite | Effort |
|---|---|---|
| Analytics evenementiels (Mixpanel / Amplitude) | Haute | 1 semaine |
| A/B testing sur la landing page | Haute | 1 semaine |
| Widget white-label pour B2B | Haute | 3 semaines |
| API publique documentee | Haute | 2 semaines |
| Pipeline d'ingestion automatisee (nouveaux vehicules) | Moyenne | 2 semaines |
| Feedback utilisateur (thumbs up/down) | Moyenne | 3 jours |
| SEO : pages vehicule individuelles | Moyenne | 1 semaine |

### 7.4 Phase 4 : Scale (Mois 7-12)

| Fonctionnalite | Priorite | Effort |
|---|---|---|
| Application mobile (React Native ou PWA) | Haute | 6 semaines |
| Migration vers PostgreSQL + Redis | Haute | 2 semaines |
| Cache de reponses frequentes | Haute | 1 semaine |
| Multi-tenant pour B2B | Haute | 3 semaines |
| Reconnaissance vocale (speech-to-text) | Moyenne | 2 semaines |
| Reconnaissance d'images (photo de voyant) | Moyenne | 3 semaines |
| Support de langues supplementaires (DE, ES, IT, PT) | Moyenne | 2 semaines |
| Notifications push (rappels entretien) | Basse | 1 semaine |

---

## 8. Equipe & Besoins

### 8.1 Equipe actuelle

| Membre | Role | Profil |
|---|---|---|
| **Lakhdar Berache** | Fondateur, Full-stack Developer | Etudiant ingenieur, experience en ingenierie automobile. Responsable de l'ensemble du produit : architecture, backend Python, frontend React, pipeline RAG, DevOps Docker. |

### 8.2 Recrutements prevus

**Annee 1 (selon traction) :**

| Poste | Quand | Profil recherche | Salaire indicatif |
|---|---|---|---|
| Developpeur backend Python (stage/alternance) | Mois 3-4 | Pipeline RAG, APIs, BDD | Stage : 1 200EUR/mois |
| Growth marketer (freelance) | Mois 4-6 | SEO, SEA, forums auto, social media | 2 000-3 000EUR/mois |

**Annee 2 :**

| Poste | Profil | Salaire indicatif |
|---|---|---|
| Developpeur full-stack senior | React + Python, experience SaaS | 45 000-55 000EUR/an |
| Business developer B2B | Commercial, secteur automobile | 35 000-45 000EUR/an + variable |
| Data engineer (mi-temps) | Pipeline d'ingestion, qualite des donnees | 25 000EUR/an (mi-temps) |

**Annee 3 :**

| Poste | Profil |
|---|---|
| DevOps / SRE | Infrastructure, scaling, monitoring |
| Designer UI/UX | Experience produit, design system |
| Customer success manager | Support B2B, onboarding |

### 8.3 Profils conseil / advisors

- Un expert du secteur automobile (ancien cadre concession ou constructeur)
- Un mentor technique en IA / NLP
- Un expert en strategie SaaS B2B

---

## 9. Risques & Mitigation

### 9.1 Risques techniques

| Risque | Probabilite | Impact | Mitigation |
|---|---|---|---|
| Hallucination du LLM sur des donnees techniques | Moyenne | Eleve | RAG hybride avec score de confiance + citation systeme des pages sources + disclaimer |
| Changement de pricing de l'API Gemini | Moyenne | Moyen | Architecture abstraite (switch possible vers Mistral, Llama), cout actuel tres faible (~0,0014EUR/req) |
| Scalabilite du backend Flask | Faible | Moyen | Migration vers FastAPI ou ajout de workers Gunicorn, cache Redis |
| Qualite des PDFs sources (scans de mauvaise qualite) | Moyenne | Moyen | Double extraction (PyPDF + OCR), chunking avec filtrage qualite, validation manuelle |

### 9.2 Risques commerciaux

| Risque | Probabilite | Impact | Mitigation |
|---|---|---|---|
| Faible taux de conversion gratuit vers premium | Moyenne | Eleve | A/B testing continu, valeur differenciante claire (PDF sources, video, sans pub) |
| Concurrence d'un acteur majeur (Google, ChatGPT) | Faible | Eleve | Specialisation verticale, base de donnees proprietaire de 143 vehicules, partenariats constructeurs |
| Difficulte a atteindre le B2B | Moyenne | Moyen | Commencer par des offres pilotes gratuites, demonstrer le ROI |

### 9.3 Risques juridiques

| Risque | Probabilite | Impact | Mitigation |
|---|---|---|---|
| Droits d'auteur sur les manuels constructeurs | Moyenne | Eleve | Usage transformatif (RAG, pas de reproduction integrale), citation avec references, negociation de partenariats avec les constructeurs |
| RGPD (donnees personnelles) | Faible | Moyen | Pas de stockage de donnees personnelles actuellement (pas d'auth), politique de confidentialite, DPO a prevoir |
| Responsabilite en cas de mauvais conseil technique | Faible | Eleve | Disclaimer visible, score de confiance, renvoi systematique vers un professionnel pour les operations de securite |

### 9.4 Risques financiers

| Risque | Probabilite | Impact | Mitigation |
|---|---|---|---|
| Couts API explosifs en cas de croissance rapide | Faible | Moyen | Cout unitaire tres faible (0,0014EUR), cache de reponses, quotas gratuits |
| Difficulte a lever des fonds | Moyenne | Moyen | Produit deja fonctionnel (MVP complet), bootstrapping possible grace aux couts ultra-faibles |

---

## Annexes

### A. Metriques techniques cles

| Metrique | Valeur |
|---|---|
| Vehicules indexes | 143 |
| Marques couvertes | 34 |
| Pages de manuels traitees | 53 659 |
| Chunks vectorises (FAISS + BM25) | 117 442 |
| Taille de chunk | 1 200 caracteres |
| Overlap de chunk | 200 caracteres |
| Top-K retrieval | 5 documents |
| Seuil de pertinence | 0.15 |
| Max tokens output (standard) | 4 096 |
| Max tokens output (mode Fix) | 8 192 |
| Max historique conversation | 20 messages |
| Max longueur message | 3 000 caracteres |
| Langues supportees | 3 (FR, EN, KO) |
| Segments vehicules | 7 |
| Endpoints API | 12 |

### B. Liste des 34 marques

Alfa Romeo, Alpine, Audi, BMW, Chevrolet, Citroen, Cupra, DS, Dacia, Fiat, Ford, Genesis, Honda, Hyundai, Jaguar, Jeep, Kia, Lancia, Land Rover, Maserati, Mazda, Mercedes-Benz, Mitsubishi, Nissan, Opel, Peugeot, Renault, Seat, Subaru, Suzuki, Tesla, Toyota, Volkswagen, Volvo.

### C. URLs du projet

| Ressource | URL |
|---|---|
| Production | https://wallside.online |
| Repository | GitHub (prive) |
| Contact | Landing page, section Contact |

---

*Document confidentiel -- Mechora, Avril 2026*
*Redige par Lakhdar Berache*
