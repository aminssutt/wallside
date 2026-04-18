"""Adapter RappelConso (data.economie.gouv.fr).

Source : https://data.economie.gouv.fr/explore/dataset/rappelconso0/
API Opendatasoft v2.1, donnees publiques licence Etalab 2.0.
Filtre : categorie vehicules / moyens de deplacement.
"""
from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, List, Optional

from ..base import NormalizedDoc, SourceAdapter

log = logging.getLogger("auris.garage.rappelconso")

BASE_URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/"
    "datasets/rappelconso-v2-gtin-espaces/records"
)
USER_AGENT = "AurisGarageBeta/0.1 (+https://auristraining.local)"
REQUEST_TIMEOUT = 20
PAGE_SIZE = 100
DEFAULT_MAX_RECORDS = 500

# Valeur exacte exposee par le dataset (minuscules, accents unicode).
CATEGORY_FILTER = 'categorie_produit = "automobiles et moyens de d\u00e9placement"'


def _build_ssl_context() -> Optional[ssl.SSLContext]:
    """Return an SSL context using certifi bundle when available.

    Windows + Python 3.13 ship sans bundle CA lisible pour data.economie.gouv.fr.
    On retombe sur le contexte par defaut si certifi est absent.
    """
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


_SSL_CONTEXT = _build_ssl_context()


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    kwargs = {"timeout": REQUEST_TIMEOUT}
    if _SSL_CONTEXT is not None:
        kwargs["context"] = _SSL_CONTEXT
    with urllib.request.urlopen(req, **kwargs) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _pick(record: dict, *keys: str) -> str:
    for k in keys:
        val = record.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _normalize(record: dict) -> NormalizedDoc:
    # v2 dataset uses categorie_produit / marque_produit / numero_fiche / date_publication
    ref = _pick(record, "numero_fiche", "rappel_guid", "id")
    brand = _pick(record, "marque_produit", "marque_de_produit")
    model = _pick(record, "modeles_ou_references")
    libelle = _pick(record, "libelle")
    motif = _pick(record, "motif_rappel", "motif_du_rappel")
    risques = _pick(record, "risques_encourus", "risques_encourus_par_le_consommateur")
    conduite = _pick(
        record,
        "conduites_a_tenir_par_le_consommateur",
        "conduite_a_tenir",
    )
    description = _pick(
        record,
        "description_complementaire_risque",
        "description_complementaire_du_risque",
    )
    date_pub = _pick(record, "date_publication", "date_de_publication")
    lien = _pick(record, "lien_vers_affichette_pdf", "lien_vers_la_fiche_rappel")
    distributeurs = _pick(record, "distributeurs")
    zone = _pick(record, "zone_geographique_de_vente")

    body = [
        f"Rappel RappelConso : {ref}" if ref else "Rappel RappelConso",
        f"Date de publication : {date_pub}" if date_pub else "",
        f"Marque : {brand}" if brand else "",
        f"Modeles / references : {model}" if model else "",
        f"Libelle : {libelle}" if libelle else "",
        f"Zone de vente : {zone}" if zone else "",
        f"Distributeurs : {distributeurs}" if distributeurs else "",
        "",
        f"Motif : {motif}" if motif else "",
        "",
        f"Risque : {risques}" if risques else "",
        "",
        f"Description : {description}" if description else "",
        "",
        f"Conduite a tenir : {conduite}" if conduite else "",
        "",
        "Source : data.economie.gouv.fr / RappelConso (licence Etalab 2.0).",
    ]
    text = "\n".join(p for p in body if p != "")

    title_bits = [b for b in [brand, model] if b]
    title = f"Rappel FR {ref}" + (f" - {' '.join(title_bits)}" if title_bits else "")

    return NormalizedDoc(
        doc_id=f"rappelconso::{ref or 'anonymous'}::{brand[:40]}::{model[:60]}",
        source="rappelconso_fr",
        title=title,
        text=text,
        url=lien,
        lang="fr",
        brand=brand,
        model=model,
        year="",
        category="recall",
        license="Etalab 2.0",
        extra={
            "numero_fiche": ref,
            "date_publication": date_pub,
            "motif": motif,
            "risques": risques,
            "conduite_a_tenir": conduite,
            "libelle": libelle,
        },
    )


class RappelConsoAdapter(SourceAdapter):
    name = "rappelconso_fr"
    license = "Etalab 2.0"

    def __init__(
        self,
        max_records: int = DEFAULT_MAX_RECORDS,
        cache_dir: Path | None = None,
        sleep_between_calls: float = 0.25,
    ) -> None:
        self.max_records = max_records
        self.cache_dir = cache_dir
        self.sleep_between_calls = sleep_between_calls

    def _fetch_page(self, offset: int) -> dict:
        params = urllib.parse.urlencode(
            {
                "where": CATEGORY_FILTER,
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
                "order_by": "date_publication DESC",
            }
        )
        url = f"{BASE_URL}?{params}"

        cache_file = None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self.cache_dir / f"page_offset_{offset:05d}.json"
            if cache_file.exists():
                try:
                    return json.loads(cache_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

        try:
            data = _http_get_json(url)
        except Exception as exc:
            log.warning("RappelConso fetch failed at offset %d: %s", offset, exc)
            return {"results": [], "_error": str(exc)}

        if cache_file:
            try:
                cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return data

    def fetch(self) -> Iterable[NormalizedDoc]:
        offset = 0
        emitted = 0
        seen: set[str] = set()
        while emitted < self.max_records:
            page = self._fetch_page(offset)
            results: List[dict] = page.get("results") or []
            if not results:
                break
            for rec in results:
                doc = _normalize(rec)
                if doc.doc_id in seen:
                    continue
                seen.add(doc.doc_id)
                emitted += 1
                yield doc
                if emitted >= self.max_records:
                    break
            offset += PAGE_SIZE
            if self.sleep_between_calls:
                time.sleep(self.sleep_between_calls)
