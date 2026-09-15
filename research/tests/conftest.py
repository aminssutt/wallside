import os
import tempfile

# Indexes built by tests must never land in research/data.
os.environ.setdefault("RAGSCALE_DATA_DIR", tempfile.mkdtemp(prefix="ragscale-test-"))

import numpy as np
import pandas as pd
import pytest

from ragscale.corpus import Corpus
from ragscale.retrievers.base import Query, ScoringRetriever

MANUALS = [
    # manual, name, brand, vehicle, lang
    ("peugeot-208", "Peugeot 208 (2023)", "Peugeot", "peugeot-208", "fr"),
    ("peugeot-2008", "Peugeot 2008 (2019)", "Peugeot", "peugeot-2008", "fr"),
    ("renault-clio", "Renault Clio 5 (2025)", "Renault", "renault-clio", "fr"),
    ("renault-clio-media", "Renault Clio 5 Easy Link Multimedia", "Renault", "renault-clio", "fr"),
]
TEXTS = {
    "peugeot-208": ["Le réservoir de carburant a une capacité de 44 litres.", "Pour ouvrir le capot, tirez la manette sous la planche de bord."],
    "peugeot-2008": ["La capacité du réservoir est de 52 litres environ.", "Pression des pneumatiques indiquée sur la portière conducteur."],
    "renault-clio": ["Réglage de l'heure : appuyez longuement sur le bouton de l'écran.", "Le frein de parking électrique se serre automatiquement."],
    "renault-clio-media": ["Connexion Bluetooth du téléphone depuis le menu Téléphone.", "Mise à jour de la cartographie via le port USB."],
}


@pytest.fixture(scope="session")
def tiny_corpus() -> Corpus:
    rows = []
    for manual, *_ in MANUALS:
        for i, text in enumerate(TEXTS[manual]):
            rows.append({"chunk_id": f"{manual}::{i:05d}", "manual": manual, "chunk_index": i, "page_label": str(10 + i),
                         "page_start": 10 + i, "page_end": 10 + i, "text": text, "n_chars": len(text),
                         "norm_hash": f"{manual}{i}", "dup_count": 1, "dup_manuals": 1, "stopword_ratio": 0.3,
                         "garbled": False})
    chunks = pd.DataFrame(rows)
    chunks.insert(0, "row", np.arange(len(chunks)))
    manuals = pd.DataFrame([
        {"manual": m, "name": n, "brand": b, "brand_key": b.lower(), "vehicle": v, "segment": "", "lang": lang,
         "extraction_mode": "pypdf", "page_count": 2, "n_chunks": 2, "source_hash": m, "duplicate_of": None,
         "garbled_share": 0.0}
        for m, n, b, v, lang in MANUALS
    ])
    return Corpus(chunks, manuals)


class FixedScores(ScoringRetriever):
    """Deterministic scorer for composite-retriever tests: score = table[query text][row]."""

    def __init__(self, corpus, table: dict[str, list[float]], name: str = "fixed"):
        super().__init__(corpus)
        self.table, self.name = table, name

    def score_batch(self, queries: list[Query]) -> np.ndarray:
        return np.array([self.table[q.text] for q in queries], dtype=np.float32)
