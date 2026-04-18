"""CLI entry point to build Garage Beta corpora.

Usage (from backend/):
    python -m garage_scraping.run_ingest
    python -m garage_scraping.run_ingest --corpus dtc
    python -m garage_scraping.run_ingest --corpus recalls --nhtsa-years 2021,2022,2023
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow running from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garage_scraping.adapters.datagouv_recalls import RappelConsoAdapter
from garage_scraping.adapters.dtc_dictionary import DTCDictionaryAdapter
from garage_scraping.adapters.nhtsa_recalls import NHTSARecallsAdapter
from garage_scraping.pipeline import run_ingestion

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_CACHE_DIR = DATA_DIR / "garage_raw"
DTC_OUT = DATA_DIR / "garage_dtc"
RECALLS_OUT = DATA_DIR / "garage_recalls"
REPORTS_DIR = DATA_DIR / "garage_reports"


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def ingest_dtc() -> dict:
    adapters = [DTCDictionaryAdapter()]
    report = run_ingestion("garage_dtc", adapters, DTC_OUT)
    return report.to_dict()


def ingest_recalls(
    nhtsa_years: list[int] | None,
    rappelconso_max: int,
    skip_nhtsa: bool,
    skip_rappelconso: bool,
) -> dict:
    adapters = []
    if not skip_rappelconso:
        adapters.append(
            RappelConsoAdapter(
                max_records=rappelconso_max,
                cache_dir=RAW_CACHE_DIR / "rappelconso",
            )
        )
    if not skip_nhtsa:
        adapters.append(
            NHTSARecallsAdapter(
                years=nhtsa_years,
                cache_dir=RAW_CACHE_DIR / "nhtsa",
            )
        )
    report = run_ingestion("garage_recalls", adapters, RECALLS_OUT)
    return report.to_dict()


def _save_global_report(payload: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS_DIR / f"ingest_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Garage Beta data sources")
    parser.add_argument(
        "--corpus",
        choices=["all", "dtc", "recalls"],
        default="all",
    )
    parser.add_argument(
        "--nhtsa-years",
        type=str,
        default="",
        help="Comma-separated years, e.g. 2020,2021,2022. Empty = default.",
    )
    parser.add_argument("--rappelconso-max", type=int, default=500)
    parser.add_argument("--skip-nhtsa", action="store_true")
    parser.add_argument("--skip-rappelconso", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _configure_logging(args.verbose)

    years = None
    if args.nhtsa_years:
        try:
            years = [int(y.strip()) for y in args.nhtsa_years.split(",") if y.strip()]
        except ValueError:
            print("Invalid --nhtsa-years, expected e.g. 2020,2021,2022", file=sys.stderr)
            return 2

    combined = {"dtc": None, "recalls": None}

    if args.corpus in ("all", "dtc"):
        print("[ingest] Building DTC corpus...")
        combined["dtc"] = ingest_dtc()
        print(json.dumps(combined["dtc"], ensure_ascii=False, indent=2))

    if args.corpus in ("all", "recalls"):
        print("[ingest] Building recalls corpus (NHTSA + RappelConso)...")
        combined["recalls"] = ingest_recalls(
            nhtsa_years=years,
            rappelconso_max=args.rappelconso_max,
            skip_nhtsa=args.skip_nhtsa,
            skip_rappelconso=args.skip_rappelconso,
        )
        print(json.dumps(combined["recalls"], ensure_ascii=False, indent=2))

    out = _save_global_report(combined)
    print(f"[ingest] Global report saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
