"""NHTSA recalls adapter.

Source : api.nhtsa.gov/recalls/recallsByVehicle (API publique,
aucune cle requise, donnees gouvernementales US libres).

Seed oriente marche France/Europe : constructeurs les plus presents
sur le parc roulant FR, periode 2018-2024.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, List, Tuple

from ..base import NormalizedDoc, SourceAdapter

log = logging.getLogger("auris.garage.nhtsa")

NHTSA_ENDPOINT = "https://api.nhtsa.gov/recalls/recallsByVehicle"
USER_AGENT = "AurisGarageBeta/0.1 (+https://auristraining.local)"
REQUEST_TIMEOUT = 20  # seconds

# Parc francais : focus sur les 20 couples marque/modele dominants.
# Nota : NHTSA ne couvre que les vehicules vendus aux USA. Certaines
# references (Clio, 208, C3) n'auront donc pas de rappel US ; c'est attendu.
DEFAULT_SEED: List[Tuple[str, str]] = [
    ("Volkswagen", "Golf"),
    ("Volkswagen", "Polo"),
    ("Volkswagen", "Tiguan"),
    ("Volkswagen", "Passat"),
    ("Toyota", "Yaris"),
    ("Toyota", "Corolla"),
    ("Toyota", "RAV4"),
    ("Toyota", "Camry"),
    ("Ford", "Fiesta"),
    ("Ford", "Focus"),
    ("Ford", "Kuga"),
    ("Ford", "Puma"),
    ("BMW", "Serie 1"),
    ("BMW", "Serie 3"),
    ("BMW", "X1"),
    ("BMW", "X3"),
    ("Mercedes-Benz", "Classe A"),
    ("Mercedes-Benz", "Classe C"),
    ("Mercedes-Benz", "GLA"),
    ("Audi", "A3"),
    ("Audi", "A4"),
    ("Audi", "Q3"),
    ("Nissan", "Qashqai"),
    ("Nissan", "Juke"),
    ("Hyundai", "i20"),
    ("Hyundai", "Tucson"),
    ("Kia", "Sportage"),
    ("Kia", "Picanto"),
    ("Fiat", "500"),
    ("Fiat", "Panda"),
    ("Opel", "Corsa"),
    ("Opel", "Astra"),
    ("Peugeot", "3008"),
    ("Peugeot", "508"),
    ("Renault", "Megane"),
    ("Renault", "Kadjar"),
    ("Dacia", "Duster"),
    ("Dacia", "Sandero"),
]

DEFAULT_YEARS = list(range(2019, 2025))


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _format_recall(rec: dict, make: str, model: str, year: str) -> NormalizedDoc:
    campaign = rec.get("NHTSACampaignNumber") or rec.get("NHTSAActionNumber") or "NA"
    summary = rec.get("Summary") or ""
    consequence = rec.get("Consequence") or ""
    remedy = rec.get("Remedy") or ""
    component = rec.get("Component") or ""
    report_date = rec.get("ReportReceivedDate") or ""

    body_parts = [
        f"Campagne NHTSA : {campaign}",
        f"Vehicule cible : {make} {model} {year}",
        f"Composant : {component}" if component else "",
        f"Date de declaration : {report_date}" if report_date else "",
        "",
        f"Defaut : {summary}" if summary else "",
        "",
        f"Consequence : {consequence}" if consequence else "",
        "",
        f"Remediation : {remedy}" if remedy else "",
        "",
        "Source : NHTSA (USA), donnees publiques. A croiser avec les rappels "
        "europeens (RappelConso FR, Safety Gate UE) pour un vehicule immatricule "
        "en France.",
    ]
    text = "\n".join(p for p in body_parts if p != "")

    return NormalizedDoc(
        doc_id=f"nhtsa::{campaign}::{make}::{model}::{year}",
        source="nhtsa_recalls",
        title=f"Rappel {campaign} - {make} {model} {year} - {component or 'composant non specifie'}",
        text=text,
        url=f"https://www.nhtsa.gov/recalls?nhtsaId={campaign}",
        lang="fr",
        brand=make,
        model=model,
        year=str(year),
        category="recall",
        license="US gov public data",
        extra={"campaign": campaign, "component": component, "report_date": report_date},
    )


class NHTSARecallsAdapter(SourceAdapter):
    name = "nhtsa_recalls"
    license = "US gov public data"

    def __init__(
        self,
        seed: List[Tuple[str, str]] | None = None,
        years: List[int] | None = None,
        cache_dir: Path | None = None,
        sleep_between_calls: float = 0.25,
    ) -> None:
        self.seed = seed or DEFAULT_SEED
        self.years = years or DEFAULT_YEARS
        self.cache_dir = cache_dir
        self.sleep_between_calls = sleep_between_calls

    def _fetch_one(self, make: str, model: str, year: int) -> dict:
        params = urllib.parse.urlencode(
            {"make": make, "model": model, "modelYear": str(year)}
        )
        url = f"{NHTSA_ENDPOINT}?{params}"

        cache_file = None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            safe_key = (
                f"{make}_{model}_{year}".lower()
                .replace(" ", "_")
                .replace("/", "_")
            )
            cache_file = self.cache_dir / f"{safe_key}.json"
            if cache_file.exists():
                try:
                    return json.loads(cache_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

        try:
            data = _http_get_json(url)
        except Exception as exc:  # network, 5xx, etc.
            log.warning("NHTSA fetch failed for %s %s %s: %s", make, model, year, exc)
            return {"results": [], "_error": str(exc)}

        if cache_file:
            try:
                cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return data

    def fetch(self) -> Iterable[NormalizedDoc]:
        seen: set[str] = set()
        for (make, model) in self.seed:
            for year in self.years:
                data = self._fetch_one(make, model, year)
                results = data.get("results") or []
                for rec in results:
                    doc = _format_recall(rec, make, model, str(year))
                    if doc.doc_id in seen:
                        continue
                    seen.add(doc.doc_id)
                    yield doc
                if self.sleep_between_calls:
                    time.sleep(self.sleep_between_calls)
