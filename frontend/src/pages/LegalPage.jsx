import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import './LegalPage.css';

/* ============================================================
   Tab definitions
   ============================================================ */

const TABS = [
  { id: 'mentions', label: 'Mentions legales' },
  { id: 'cgu', label: 'CGU' },
  { id: 'privacy', label: 'Confidentialite' },
];

/* ============================================================
   Content sections
   ============================================================ */

function MentionsLegales() {
  return (
    <div className="legal-page__section">
      <h2>Mentions legales</h2>

      <h3>Editeur du site</h3>
      <ul>
        <li>Nom du site : Mechora</li>
        <li>URL : <a href="https://carchat.online" target="_blank" rel="noopener noreferrer">carchat.online</a></li>
        <li>Responsable de la publication : Lakhdar Berache (entrepreneur individuel)</li>
        <li>Adresse e-mail : <a href="mailto:lakhdarberache@gmail.com">lakhdarberache@gmail.com</a></li>
      </ul>

      <h3>Hebergement</h3>
      <p>
        Le site est heberge sur un serveur dedie. Les coordonnees
        precises de l'hebergeur seront communiquees sur demande adressee
        a l'editeur.
      </p>

      <h3>Nature du service</h3>
      <p>
        Mechora est un assistant technique automobile base sur
        l'intelligence artificielle. Le site utilise l'IA (Gemini de Google)
        pour fournir des reponses basees sur les manuels constructeurs
        automobiles. Les reponses generees sont fournies a titre purement
        informatif.
      </p>

      <span className="legal-page__updated">Derniere mise a jour : avril 2026</span>
    </div>
  );
}

function CGU() {
  return (
    <div className="legal-page__section">
      <h2>Conditions generales d'utilisation</h2>

      <h3>Article 1 — Objet</h3>
      <p>
        Les presentes Conditions Generales d'Utilisation (CGU) ont pour objet
        de definir les modalites d'acces et d'utilisation du service Mechora,
        accessible a l'adresse <a href="https://carchat.online" target="_blank" rel="noopener noreferrer">carchat.online</a>.
        Mechora est un assistant technique automobile base sur l'intelligence
        artificielle, concu pour repondre aux questions relatives a
        l'utilisation et l'entretien des vehicules.
      </p>

      <h3>Article 2 — Acces au service</h3>
      <p>
        L'acces au service est gratuit dans sa version de base. Aucune
        creation de compte n'est requise pour utiliser le chatbot.
        L'editeur se reserve le droit de proposer des fonctionnalites
        premium payantes a l'avenir.
      </p>

      <h3>Article 3 — Limitations de responsabilite</h3>
      <p>
        Les reponses fournies par Mechora sont generees par intelligence
        artificielle et sont communiquees a titre informatif uniquement.
        Elles ne sauraient en aucun cas se substituer a l'avis d'un
        professionnel de l'automobile (mecanicien, concessionnaire, expert).
      </p>
      <p>
        Mechora ne garantit pas l'exactitude, l'exhaustivite ou
        l'actualite des reponses fournies par l'IA. L'utilisateur
        utilise le service sous sa propre responsabilite.
      </p>

      <h3>Article 4 — Propriete intellectuelle</h3>
      <p>
        Les manuels techniques et guides constructeurs utilises comme
        source de donnees restent la propriete exclusive de leurs
        constructeurs respectifs. Le contenu du site Mechora (design,
        textes, logo) est la propriete de Lakhdar Berache, sauf
        mention contraire.
      </p>

      <h3>Article 5 — Comportement de l'utilisateur</h3>
      <p>
        L'utilisateur s'engage a utiliser le service de maniere
        conforme a sa destination. Toute utilisation abusive,
        automatisee ou detournee du service pourra entrainer une
        restriction d'acces sans preavis.
      </p>

      <h3>Article 6 — Modification des CGU</h3>
      <p>
        L'editeur se reserve le droit de modifier les presentes CGU a
        tout moment. Les modifications prennent effet des leur
        publication sur le site. L'utilisation continue du service
        vaut acceptation des CGU modifiees.
      </p>

      <span className="legal-page__updated">Derniere mise a jour : avril 2026</span>
    </div>
  );
}

function PolitiqueConfidentialite() {
  return (
    <div className="legal-page__section">
      <h2>Politique de confidentialite</h2>

      <h3>1. Donnees collectees</h3>
      <p>
        Mechora collecte un minimum de donnees necessaires au
        fonctionnement du service :
      </p>
      <ul>
        <li>
          <strong>Messages de chat :</strong> les messages envoyes au
          chatbot sont transmis a l'API Gemini de Google pour
          traitement. Ils ne sont pas stockes de maniere persistante
          sur nos serveurs.
        </li>
        <li>
          <strong>Preference de langue :</strong> la langue choisie
          par l'utilisateur est enregistree dans le localStorage du
          navigateur (stockage local uniquement).
        </li>
      </ul>

      <h3>2. Absence de compte utilisateur</h3>
      <p>
        Aucune creation de compte n'est requise. Mechora ne collecte
        ni nom, ni adresse e-mail, ni aucune autre donnee
        d'identification personnelle.
      </p>

      <h3>3. Cookies et traceurs</h3>
      <p>
        Mechora n'utilise aucun cookie de tracking. Aucun outil
        d'analyse tiers (Google Analytics ou equivalent) n'est
        integre au site. Seul le localStorage du navigateur est
        utilise pour stocker la preference de langue.
      </p>

      <h3>4. Partage de donnees</h3>
      <p>
        Les messages de chat sont transmis a l'API Gemini de Google
        dans le cadre du traitement des requetes. Aucune donnee
        personnelle n'est vendue, louee ou cedee a des tiers a des
        fins commerciales ou publicitaires.
      </p>

      <h3>5. Vos droits (RGPD)</h3>
      <p>
        Conformement au Reglement General sur la Protection des
        Donnees (RGPD), vous disposez des droits suivants :
      </p>
      <ul>
        <li>Droit d'acces a vos donnees</li>
        <li>Droit de rectification</li>
        <li>Droit a l'effacement (droit a l'oubli)</li>
        <li>Droit a la limitation du traitement</li>
        <li>Droit a la portabilite des donnees</li>
        <li>Droit d'opposition</li>
      </ul>
      <p>
        Pour exercer ces droits, contactez-nous a l'adresse :
        {' '}<a href="mailto:lakhdarberache@gmail.com">lakhdarberache@gmail.com</a>
      </p>

      <h3>6. Contact</h3>
      <p>
        Pour toute question relative a la protection de vos donnees
        personnelles, vous pouvez nous contacter par e-mail a
        l'adresse : <a href="mailto:lakhdarberache@gmail.com">lakhdarberache@gmail.com</a>
      </p>

      <span className="legal-page__updated">Derniere mise a jour : avril 2026</span>
    </div>
  );
}

/* ============================================================
   Main component
   ============================================================ */

const PAGE_VARIANTS = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
};

const CONTENT_VARIANTS = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15 } },
};

export default function LegalPage() {
  const [activeTab, setActiveTab] = useState('mentions');

  const renderContent = () => {
    switch (activeTab) {
      case 'mentions':
        return <MentionsLegales />;
      case 'cgu':
        return <CGU />;
      case 'privacy':
        return <PolitiqueConfidentialite />;
      default:
        return <MentionsLegales />;
    }
  };

  return (
    <Motion.div
      className="legal-page"
      variants={PAGE_VARIANTS}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <header className="legal-page__header">
        <Link to="/" className="legal-page__back">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Retour
        </Link>
      </header>

      <h1 className="legal-page__title">Informations legales</h1>

      <nav className="legal-page__tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`legal-page__tab${activeTab === tab.id ? ' legal-page__tab--active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="legal-page__content" role="tabpanel">
        <AnimatePresence mode="wait">
          <Motion.div
            key={activeTab}
            variants={CONTENT_VARIANTS}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {renderContent()}
          </Motion.div>
        </AnimatePresence>
      </div>
    </Motion.div>
  );
}
