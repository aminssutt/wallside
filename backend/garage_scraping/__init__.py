"""Garage Beta data ingestion pipeline.

Sources open data legales uniquement:
- Dictionnaire DTC OBD-II (faits publics, descriptions authored-in-house)
- Rappels NHTSA (USA) via api.nhtsa.gov
- Rappels RappelConso France via data.economie.gouv.fr

Aucun contenu copyrighte n'est collecte ou redistribue.
"""

__all__ = ["base", "pipeline", "adapters"]
