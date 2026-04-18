"""OBD-II DTC dictionary adapter.

Source : structure SAE J2012 (norme publique), descriptions et causes
authored-in-house a partir de connaissances factuelles generales sur
le diagnostic automobile. Aucun texte copyrighte n'est reproduit.

Chaque code est decrit sous forme structuree (symptomes, causes
probables, approche diagnostic) utilisable par le RAG atelier.
"""
from __future__ import annotations

import re
from typing import Iterable, List

from ..base import NormalizedDoc, SourceAdapter


# ---------------------------------------------------------------------------
# Decodeur structurel (couvre n'importe quel code OBD-II)
# ---------------------------------------------------------------------------

_CATEGORY = {
    "P": "Groupe motopropulseur (moteur, transmission, emissions)",
    "B": "Carrosserie (confort, airbag, ceintures, climatisation)",
    "C": "Chassis (ABS, ESP, direction assistee, suspension)",
    "U": "Reseau de communication (CAN, LIN, bus vehicule)",
}

_P_SUBSYSTEM = {
    "0": "Dosage air / carburant ou commande auxiliaire",
    "1": "Dosage air / carburant",
    "2": "Circuit injecteurs",
    "3": "Allumage ou rate d'allumage",
    "4": "Systeme de controle des emissions",
    "5": "Regime moteur / controle de vitesse",
    "6": "Ordinateur de bord et entrees / sorties",
    "7": "Transmission",
    "8": "Transmission",
    "9": "Transmission",
    "A": "Systeme hybride / electrique",
    "B": "Systeme hybride / electrique",
    "C": "Systeme hybride / electrique",
}

_CODE_RE = re.compile(r"^[PBCU][0-3][0-9A-F]{3}$", re.IGNORECASE)


def is_valid_dtc(code: str) -> bool:
    return bool(_CODE_RE.match((code or "").strip()))


def normalize_dtc(code: str) -> str:
    return (code or "").strip().upper()


def decode_structure(code: str) -> dict:
    """Return a structural breakdown for any valid OBD-II DTC."""
    code = normalize_dtc(code)
    if not is_valid_dtc(code):
        return {}
    category = code[0]
    second = code[1]
    generic = second in ("0", "2")  # per SAE J2012 (P0xxx, P2xxx = generic)
    subsystem = _P_SUBSYSTEM.get(code[2], "Sous-systeme non classifie")
    return {
        "code": code,
        "category": _CATEGORY.get(category, "Categorie inconnue"),
        "category_letter": category,
        "scope": "generique (norme SAE J2012)" if generic else "specifique constructeur",
        "subsystem_hint": subsystem if category == "P" else "",
    }


# ---------------------------------------------------------------------------
# Base de donnees curee : top codes les plus rencontres en atelier
# Descriptions courtes et factuelles, redigees pour ce projet.
# ---------------------------------------------------------------------------

# Format d'entree :
#   code, title, symptoms[], causes[], checks[]

_CURATED: List[dict] = [
    {
        "code": "P0100",
        "title": "Circuit debitmetre d'air massique : defaut general",
        "symptoms": [
            "Ralenti instable",
            "Perte de puissance",
            "Consommation anormale",
            "Voyant moteur allume",
        ],
        "causes": [
            "Debitmetre (MAF) encrasse ou defaillant",
            "Connecteur oxyde ou desserre",
            "Prise d'air non mesuree apres le debitmetre",
            "Filtre a air sature ou mal monte",
        ],
        "checks": [
            "Lire le debit d'air au ralenti et compare a la valeur attendue (env. 2 a 4 g/s chaud)",
            "Controler visuellement le connecteur et le cablage",
            "Verifier l'etancheite du conduit d'admission entre MAF et papillon",
            "Nettoyer le fil chaud du MAF avec un produit specifique, jamais avec du degraissant",
        ],
    },
    {
        "code": "P0101",
        "title": "Debitmetre d'air : signal hors plage / incoherent",
        "symptoms": [
            "A-coups a l'acceleration",
            "Ralenti irregulier",
            "Demarrage difficile a chaud",
        ],
        "causes": [
            "MAF encrasse",
            "Filtre a air colmate",
            "Fuite d'air non mesuree (durites admission)",
            "Catalyseur ou FAP sature creant une contre-pression",
        ],
        "checks": [
            "Debit au ralenti puis a 2500 tr/min, comparer a la valeur constructeur",
            "Rechercher prise d'air non mesuree (fumigene ou ecoute)",
            "Etat du filtre a air",
        ],
    },
    {
        "code": "P0171",
        "title": "Melange trop pauvre, banc 1",
        "symptoms": [
            "Ralenti instable",
            "Perte de puissance, consommation en hausse",
            "Voyant moteur, parfois mode degrade",
        ],
        "causes": [
            "Prise d'air (durite craquelee, joint d'admission)",
            "Debitmetre encrasse",
            "Pression de carburant insuffisante (pompe, filtre, regulateur)",
            "Injecteur bouche",
            "Capteur de pression d'admission (MAP) defectueux",
        ],
        "checks": [
            "Test d'etancheite admission (fumigene)",
            "Pression rampe injection (valeur constructeur)",
            "Valeurs STFT / LTFT au ralenti et en charge",
            "Debit MAF a 2500 tr/min",
        ],
    },
    {
        "code": "P0172",
        "title": "Melange trop riche, banc 1",
        "symptoms": [
            "Odeur d'essence a l'echappement",
            "Fumees noires",
            "Consommation elevee",
            "Encrassement bougies",
        ],
        "causes": [
            "Injecteur qui fuit",
            "Regulateur de pression de carburant defectueux",
            "Sonde lambda amont defaillante",
            "Capteur temperature liquide de refroidissement fournissant une valeur froide en permanence",
            "Filtre a air tres colmate",
        ],
        "checks": [
            "Test etancheite injecteurs (pression statique apres coupure)",
            "Valeur sonde lambda amont (doit osciller 0.1 a 0.9 V)",
            "Temperature liquide refroidissement via diag : doit monter a 85 a 95 C",
        ],
    },
    {
        "code": "P0174",
        "title": "Melange trop pauvre, banc 2",
        "symptoms": ["Idem P0171 sur cote 2 (V6/V8)"],
        "causes": ["Prise d'air cote banc 2", "Injecteur banc 2", "Collecteur admission fissure"],
        "checks": ["Test fumigene banc 2", "Controle injecteurs banc 2"],
    },
    {
        "code": "P0175",
        "title": "Melange trop riche, banc 2",
        "symptoms": ["Idem P0172 sur cote 2"],
        "causes": ["Injecteur banc 2 qui fuit", "Sonde lambda banc 2"],
        "checks": ["Test etancheite injecteurs banc 2", "Signal sonde lambda banc 2"],
    },
    {
        "code": "P0200",
        "title": "Circuit injecteurs : defaut general",
        "symptoms": ["A-coups", "Rate d'allumage"],
        "causes": ["Injecteur HS", "Cablage injecteur", "ECU faisceau"],
        "checks": ["Resistance injecteur (env. 12 a 17 ohms en essence, 0.5 a 2 ohms en diesel selon techno)"],
    },
    {
        "code": "P0201",
        "title": "Injecteur cylindre 1 : defaut circuit",
        "symptoms": ["Rate d'allumage cylindre 1", "Perte de puissance"],
        "causes": ["Injecteur 1 HS", "Connecteur injecteur 1", "Faisceau"],
        "checks": ["Echanger injecteur 1 avec un autre cylindre et verifier si le defaut suit"],
    },
    {
        "code": "P0202",
        "title": "Injecteur cylindre 2 : defaut circuit",
        "symptoms": ["Rate d'allumage cylindre 2"],
        "causes": ["Injecteur 2 HS", "Connecteur 2"],
        "checks": ["Echange croise injecteur"],
    },
    {
        "code": "P0203",
        "title": "Injecteur cylindre 3 : defaut circuit",
        "symptoms": ["Rate d'allumage cylindre 3"],
        "causes": ["Injecteur 3 HS", "Connecteur 3"],
        "checks": ["Echange croise injecteur"],
    },
    {
        "code": "P0204",
        "title": "Injecteur cylindre 4 : defaut circuit",
        "symptoms": ["Rate d'allumage cylindre 4"],
        "causes": ["Injecteur 4 HS", "Connecteur 4"],
        "checks": ["Echange croise injecteur"],
    },
    {
        "code": "P0300",
        "title": "Rate d'allumage aleatoire / multiple",
        "symptoms": [
            "Ralenti tres instable",
            "A-coups et secousses",
            "Voyant moteur clignotant (risque catalyseur)",
        ],
        "causes": [
            "Bougies usees ou incorrectes",
            "Bobines ou cables d'allumage HS",
            "Prise d'air importante",
            "Injecteurs encrasses",
            "Compression faible sur plusieurs cylindres",
            "Qualite carburant",
        ],
        "checks": [
            "Lire les compteurs de rates par cylindre",
            "Remplacer ou permuter bougies, bobines",
            "Test compression",
            "Test fumigene",
        ],
    },
    {
        "code": "P0301",
        "title": "Rate d'allumage cylindre 1",
        "symptoms": ["A-coup marque", "Perte de puissance", "Voyant clignotant"],
        "causes": ["Bougie 1", "Bobine 1", "Injecteur 1", "Compression faible cylindre 1"],
        "checks": ["Permuter bobine 1 avec une autre, relire le code", "Test compression cylindre 1"],
    },
    {
        "code": "P0302",
        "title": "Rate d'allumage cylindre 2",
        "symptoms": ["Idem P0301 cote cylindre 2"],
        "causes": ["Bougie / bobine / injecteur cyl 2", "Compression"],
        "checks": ["Permutation bobine 2", "Test compression"],
    },
    {
        "code": "P0303",
        "title": "Rate d'allumage cylindre 3",
        "symptoms": ["A-coup marque"],
        "causes": ["Bougie / bobine / injecteur cyl 3", "Compression"],
        "checks": ["Permutation bobine 3", "Compression"],
    },
    {
        "code": "P0304",
        "title": "Rate d'allumage cylindre 4",
        "symptoms": ["A-coup marque"],
        "causes": ["Bougie / bobine / injecteur cyl 4", "Compression"],
        "checks": ["Permutation bobine 4", "Compression"],
    },
    {
        "code": "P0305",
        "title": "Rate d'allumage cylindre 5",
        "symptoms": ["A-coup"],
        "causes": ["Bougie / bobine / injecteur cyl 5"],
        "checks": ["Permutation bobine", "Compression"],
    },
    {
        "code": "P0306",
        "title": "Rate d'allumage cylindre 6",
        "symptoms": ["A-coup"],
        "causes": ["Bougie / bobine / injecteur cyl 6"],
        "checks": ["Permutation bobine", "Compression"],
    },
    {
        "code": "P0340",
        "title": "Circuit capteur arbre a cames : defaut",
        "symptoms": ["Demarrage long ou impossible", "Perte de puissance"],
        "causes": ["Capteur AAC HS", "Cablage coupe ou court-circuit", "Distribution decalee"],
        "checks": ["Signal capteur AAC a l'oscilloscope", "Correlation AAC / vilebrequin", "Controle calage distribution"],
    },
    {
        "code": "P0341",
        "title": "Capteur arbre a cames : signal incoherent",
        "symptoms": ["Demarrage difficile", "Calage moteur intermittent"],
        "causes": ["Cible AAC endommagee", "Chaine ou courroie detendue", "Capteur HS"],
        "checks": ["Controle tension chaine ou etat courroie", "Oscilloscope signal AAC vs vilebrequin"],
    },
    {
        "code": "P0420",
        "title": "Efficacite catalyseur sous seuil, banc 1",
        "symptoms": [
            "Voyant moteur allume",
            "Pas toujours de symptome percu",
            "Possible odeur soufre / oeuf pourri",
        ],
        "causes": [
            "Catalyseur vieillissant ou endommage",
            "Sonde lambda aval defaillante",
            "Fuite d'echappement avant le catalyseur",
            "Consommation d'huile trop elevee",
        ],
        "checks": [
            "Comparer signaux sonde lambda amont (oscillante) et aval (doit etre stable)",
            "Inspection visuelle catalyseur (fonte, casse)",
            "Etancheite echappement entre collecteur et catalyseur",
        ],
    },
    {
        "code": "P0421",
        "title": "Efficacite catalyseur chauffe sous seuil, banc 1",
        "symptoms": ["Idem P0420, apparition plus rapide"],
        "causes": ["Catalyseur HS", "Sonde lambda aval"],
        "checks": ["Signal sonde aval", "Etat catalyseur"],
    },
    {
        "code": "P0430",
        "title": "Efficacite catalyseur sous seuil, banc 2",
        "symptoms": ["Idem P0420 sur banc 2"],
        "causes": ["Catalyseur banc 2 HS", "Sonde lambda aval banc 2"],
        "checks": ["Signaux lambda banc 2", "Etat catalyseur banc 2"],
    },
    {
        "code": "P0440",
        "title": "Systeme EVAP : defaut general",
        "symptoms": ["Voyant moteur", "Odeur de carburant"],
        "causes": [
            "Bouchon reservoir mal ferme ou joint HS",
            "Durite EVAP percee",
            "Canister ou electrovanne purge defaillant",
        ],
        "checks": ["Test d'etancheite EVAP au fumigene", "Verifier le bouchon de reservoir"],
    },
    {
        "code": "P0441",
        "title": "Purge EVAP : debit incorrect",
        "symptoms": ["Voyant moteur"],
        "causes": ["Electrovanne purge bloquee", "Durite purge percee ou pincee"],
        "checks": ["Commande active electrovanne au diag", "Test etancheite EVAP"],
    },
    {
        "code": "P0442",
        "title": "EVAP : petite fuite detectee",
        "symptoms": ["Voyant moteur uniquement"],
        "causes": ["Bouchon reservoir", "Joint bouchon", "Petite fuite durite"],
        "checks": ["Reserrer / remplacer bouchon", "Fumigene EVAP"],
    },
    {
        "code": "P0455",
        "title": "EVAP : grosse fuite detectee",
        "symptoms": ["Odeur carburant marquee"],
        "causes": ["Bouchon absent ou HS", "Durite deconnectee", "Canister fissure"],
        "checks": ["Inspection visuelle", "Fumigene EVAP"],
    },
    {
        "code": "P0500",
        "title": "Capteur de vitesse vehicule : defaut",
        "symptoms": ["Compteur de vitesse errone ou a zero", "Passage de vitesses anormal (BVA)", "ESP / ABS desactives"],
        "causes": ["Capteur de roue HS", "Cablage", "Calculateur ABS"],
        "checks": ["Lire les 4 vitesses roues au diag", "Continuite cablage capteur"],
    },
    {
        "code": "P0506",
        "title": "Regime ralenti trop bas",
        "symptoms": ["Cale au ralenti", "Ralenti errant bas"],
        "causes": ["Boitier papillon encrasse", "Fuite vide", "Capteur pedale accelerateur"],
        "checks": ["Nettoyage papillon puis reapprentissage", "Test etancheite vide"],
    },
    {
        "code": "P0507",
        "title": "Regime ralenti trop haut",
        "symptoms": ["Ralenti superieur a la cible", "Frein moteur faible"],
        "causes": ["Prise d'air", "Papillon mal referme", "Capteur pedale"],
        "checks": ["Test fumigene", "Reapprentissage papillon"],
    },
    {
        "code": "P0562",
        "title": "Tension systeme trop basse",
        "symptoms": ["Voyant batterie", "Demarrage difficile", "Voyants tableau bord aleatoires"],
        "causes": ["Alternateur HS", "Courroie accessoires", "Cosse batterie oxydee", "Batterie fatiguee"],
        "checks": ["Tension aux bornes batterie moteur tournant (doit etre 13.8 a 14.4 V)", "Test alternateur en charge"],
    },
    {
        "code": "P0563",
        "title": "Tension systeme trop haute",
        "symptoms": ["Ampoules grillent frequemment"],
        "causes": ["Regulateur alternateur HS"],
        "checks": ["Tension aux bornes batterie moteur a 2500 tr/min"],
    },
    {
        "code": "P0600",
        "title": "Defaut de communication interne calculateur",
        "symptoms": ["Defauts multiples sans coherence"],
        "causes": ["Masse calculateur", "Alimentation calculateur", "Calculateur HS"],
        "checks": ["Controler masses moteur", "Verifier tensions d'alimentation calculateur"],
    },
    {
        "code": "P0700",
        "title": "Defaut transmission : code parent",
        "symptoms": ["Mode degrade BVA", "Passages brusques ou retardes"],
        "causes": ["Code parent : lire les codes secondaires BVA"],
        "checks": ["Lire les DTC du calculateur de transmission", "Niveau et etat de l'huile BVA"],
    },
    {
        "code": "P1000",
        "title": "Tests OBD non completes (Ford et equivalents)",
        "symptoms": ["Aucun", "Apparait apres effacement de codes"],
        "causes": ["Cycle de roulage OBD non effectue apres reset"],
        "checks": ["Effectuer le cycle constructeur : ralenti, ville, route, decelerations"],
    },
    {
        "code": "U0100",
        "title": "Perte de communication avec le calculateur moteur",
        "symptoms": ["Tableau de bord fige", "Multiples voyants", "Vehicule en mode degrade"],
        "causes": ["Bus CAN interrompu", "Connecteur calculateur moteur", "Calculateur HS", "Alimentation calculateur"],
        "checks": ["Mesurer resistance bus CAN (60 ohms environ entre CAN H et CAN L a calculateur debranche)", "Controler alimentation et masse calculateur moteur"],
    },
    {
        "code": "U0101",
        "title": "Perte de communication avec calculateur transmission",
        "symptoms": ["BVA mode degrade", "Voyant gearbox"],
        "causes": ["Bus CAN", "Calculateur BVA"],
        "checks": ["Controle bus CAN", "Alimentation calculateur BVA"],
    },
    {
        "code": "U0121",
        "title": "Perte de communication avec calculateur ABS",
        "symptoms": ["Voyants ABS et ESP"],
        "causes": ["Bus CAN", "Calculateur ABS HS", "Connecteur"],
        "checks": ["Diag sur calculateur ABS", "Bus CAN"],
    },
    {
        "code": "C0035",
        "title": "Capteur de vitesse roue avant gauche : defaut",
        "symptoms": ["Voyant ABS", "Voyant ESP"],
        "causes": ["Capteur HS", "Cible crantee sale", "Cablage"],
        "checks": ["Lire vitesse roue au diag", "Entrefer capteur / cible"],
    },
    {
        "code": "C0040",
        "title": "Capteur de vitesse roue avant droite : defaut",
        "symptoms": ["Voyant ABS / ESP"],
        "causes": ["Capteur HS", "Cible", "Cablage"],
        "checks": ["Lire vitesse roue", "Entrefer"],
    },
    {
        "code": "B1000",
        "title": "Defaut calculateur carrosserie (BCM)",
        "symptoms": ["Defauts electriques multiples (vitres, centralisation)"],
        "causes": ["BCM HS ou mise a jour necessaire"],
        "checks": ["Lire DTC complets sur BCM"],
    },
    # ---- Diesel specifiques ----
    {
        "code": "P0401",
        "title": "EGR : debit insuffisant",
        "symptoms": ["Perte de puissance", "Fumees", "Voyant moteur"],
        "causes": ["Vanne EGR encrassee ou grippee", "Capteur temperature EGR", "Refroidisseur EGR bouche"],
        "checks": ["Depose et inspection vanne EGR", "Commande active vanne au diag"],
    },
    {
        "code": "P0402",
        "title": "EGR : debit excessif",
        "symptoms": ["Ralenti instable", "Cale au ralenti"],
        "causes": ["Vanne EGR restee ouverte", "Joint vanne fuitard"],
        "checks": ["Depose vanne", "Commande active"],
    },
    {
        "code": "P2002",
        "title": "FAP : efficacite sous seuil",
        "symptoms": ["Voyant FAP", "Perte de puissance", "Mode degrade possible"],
        "causes": ["FAP sature", "Differentiel de pression FAP HS", "Injecteur de carburant FAP (si present)"],
        "checks": ["Lire pression differentielle FAP au ralenti et a 2500 tr/min", "Regeneration forcee au diag"],
    },
    {
        "code": "P244A",
        "title": "Differentiel de pression FAP trop bas",
        "symptoms": ["Voyant moteur"],
        "causes": ["Capteur de pression differentielle HS", "Durites prise de pression bouchees ou deconnectees"],
        "checks": ["Lire valeur brute capteur", "Controle physique durites"],
    },
    {
        "code": "P244B",
        "title": "Differentiel de pression FAP trop eleve",
        "symptoms": ["Perte de puissance", "Mode degrade"],
        "causes": ["FAP sature", "Durites inversees"],
        "checks": ["Regeneration forcee", "Remplacement FAP si echec"],
    },
    {
        "code": "P20E8",
        "title": "Pression AdBlue trop basse",
        "symptoms": ["Voyant AdBlue", "Mode degrade ou interdiction de demarrage imminente"],
        "causes": ["Pompe AdBlue HS", "Injecteur AdBlue bouche", "Qualite AdBlue"],
        "checks": ["Commande active pompe AdBlue", "Pression nominale au diag"],
    },
]


def _doc_text(entry: dict, structure: dict) -> str:
    """Compose a clean text body for RAG indexing."""
    lines: List[str] = []
    lines.append(f"Code DTC : {entry['code']}")
    lines.append(f"Titre : {entry['title']}")
    if structure:
        lines.append(f"Categorie : {structure.get('category', '')}")
        if structure.get("subsystem_hint"):
            lines.append(f"Sous-systeme : {structure['subsystem_hint']}")
        lines.append(f"Portee : {structure.get('scope', '')}")
    if entry.get("symptoms"):
        lines.append("Symptomes frequents :")
        for s in entry["symptoms"]:
            lines.append(f"- {s}")
    if entry.get("causes"):
        lines.append("Causes probables :")
        for c in entry["causes"]:
            lines.append(f"- {c}")
    if entry.get("checks"):
        lines.append("Controles et diagnostic :")
        for ch in entry["checks"]:
            lines.append(f"- {ch}")
    lines.append(
        "Sources : structure de code SAE J2012 (norme publique), "
        "contenu redige pour Auris Garage Beta a partir de connaissances "
        "factuelles generales sur le diagnostic automobile."
    )
    return "\n".join(lines)


class DTCDictionaryAdapter(SourceAdapter):
    name = "dtc_dictionary"
    license = "CC-BY-4.0 (contenu original Auris)"

    def fetch(self) -> Iterable[NormalizedDoc]:
        for entry in _CURATED:
            code = normalize_dtc(entry["code"])
            structure = decode_structure(code)
            text = _doc_text(entry, structure)
            yield NormalizedDoc(
                doc_id=f"dtc::{code}",
                source=self.name,
                title=f"{code} - {entry['title']}",
                text=text,
                lang="fr",
                category="dtc",
                license=self.license,
                extra={
                    "code": code,
                    "symptoms": entry.get("symptoms", []),
                    "causes": entry.get("causes", []),
                    "checks": entry.get("checks", []),
                    "structure": structure,
                },
            )


def lookup_curated(code: str) -> dict:
    """Return curated entry + structure for a DTC, or structure-only if not curated."""
    code = normalize_dtc(code)
    if not is_valid_dtc(code):
        return {"code": code, "valid": False}
    structure = decode_structure(code)
    for entry in _CURATED:
        if entry["code"] == code:
            return {
                "code": code,
                "valid": True,
                "curated": True,
                "title": entry["title"],
                "symptoms": entry["symptoms"],
                "causes": entry["causes"],
                "checks": entry["checks"],
                "structure": structure,
            }
    return {
        "code": code,
        "valid": True,
        "curated": False,
        "title": f"{code} (non dans la base curee)",
        "structure": structure,
        "hint": (
            "Ce code n'est pas encore dans notre base curee. "
            "La categorie et le sous-systeme sont deduits de la norme SAE J2012. "
            "Consulter le manuel atelier du vehicule pour la description precise."
        ),
    }


def total_curated() -> int:
    return len(_CURATED)
