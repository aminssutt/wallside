"""
Best-effort vehicle image fetcher from Wikipedia/Wikimedia.

Reads PDFs from:
    car data/<brand>/*.pdf

For each model without an image in backend/data/vehicle_images, it tries to fetch
an image and stores it as JPEG. Background removal is handled by process_vehicle_images.py.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.config import DATA_DIR


BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
CAR_DATA_DIR = PROJECT_ROOT / "car data"
IMAGES_DIR = DATA_DIR / "vehicle_images"
SOURCES_PATH = IMAGES_DIR / "sources.json"
SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "Mozilla/5.0 (AurisTrainingImageBot/1.0)"


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch missing vehicle images from Wikipedia")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if image already exists")
    parser.add_argument("--summary-json", help="Optional JSON summary output path")
    return parser.parse_args()


def derive_guide_name(pdf_name: str) -> str:
    stem = Path(pdf_name).stem
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"(?i)^\s*manuel\s+", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem.title()


def normalize_ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def slugify(text: str) -> str:
    s = normalize_ascii(text)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def discover_models() -> List[Dict[str, str]]:
    models: List[Dict[str, str]] = []
    if not CAR_DATA_DIR.exists():
        return models

    for pdf in sorted(CAR_DATA_DIR.rglob("*.pdf"), key=lambda p: p.name.lower()):
        rel = str(pdf.relative_to(PROJECT_ROOT)).replace("\\", "/")
        models.append(
            {
                "guide_name": derive_guide_name(pdf.name),
                "source_pdf": rel,
            }
        )
    return models


def has_matching_image(guide_name: str) -> bool:
    target = slugify(guide_name)
    for image in IMAGES_DIR.iterdir() if IMAGES_DIR.exists() else []:
        if not image.is_file() or image.suffix.lower() not in SUPPORTED_IMAGE_EXT:
            continue
        if slugify(image.stem) == target:
            return True
    return False


def request_json(params: Dict[str, str]) -> Dict:
    query = urlencode(params)
    req = Request(f"{WIKI_API}?{query}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def title_to_image(title: str) -> Optional[str]:
    data = request_json(
        {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": "1280",
            "titles": title,
        }
    )

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        thumb = page.get("thumbnail", {})
        src = thumb.get("source")
        if src:
            return src
    return None


def search_titles(query: str, limit: int = 6) -> List[str]:
    data = request_json(
        {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": str(limit),
        }
    )
    return [item.get("title", "") for item in data.get("query", {}).get("search", []) if item.get("title")]


def candidate_queries(guide_name: str) -> List[str]:
    base = normalize_ascii(guide_name)
    queries = [guide_name]

    no_year = re.sub(r"\b\d{4}(?:\s*[-/]\s*\d{4})?\b", "", guide_name).strip()
    no_year = re.sub(r"\s+", " ", no_year)
    if no_year and no_year not in queries:
        queries.append(no_year)

    ascii_name = re.sub(r"\s+", " ", base.title()).strip()
    if ascii_name and ascii_name not in queries:
        queries.append(ascii_name)

    return queries


def fetch_image_bytes(url: str) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://en.wikipedia.org/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=60) as response:
        return response.read()


def load_sources() -> List[dict]:
    if not SOURCES_PATH.exists():
        return []
    try:
        return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def upsert_source_entry(entries: List[dict], vehicle: str, image_name: str, source_page: str, image_url: str):
    key = vehicle.strip().lower()
    index = None
    for i, entry in enumerate(entries):
        if str(entry.get("vehicle", "")).strip().lower() == key:
            index = i
            break

    payload = {
        "vehicle": vehicle,
        "image": image_name,
        "source_page": source_page,
        "image_url": image_url,
    }

    if index is None:
        entries.append(payload)
    else:
        entries[index] = payload


def main() -> int:
    args = parse_args()
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    models = discover_models()
    summary = {"downloaded": [], "skipped": [], "failed": []}

    sources = load_sources()

    for model in models:
        guide_name = model["guide_name"]

        if not args.force and has_matching_image(guide_name):
            summary["skipped"].append({"name": guide_name, "reason": "image_exists"})
            continue

        save_base = normalize_ascii(guide_name)
        if not save_base:
            summary["failed"].append({"name": guide_name, "reason": "invalid_name"})
            continue
        save_name = f"{save_base}.jpg"
        save_path = IMAGES_DIR / save_name

        selected_url = None
        selected_title = None

        queries = candidate_queries(guide_name)
        tried_titles = []

        try:
            for query in queries:
                # 1) direct title
                url = title_to_image(query)
                if url:
                    selected_url = url
                    selected_title = query
                    break

                # 2) search fallback
                titles = search_titles(query)
                for title in titles:
                    if title in tried_titles:
                        continue
                    tried_titles.append(title)
                    url = title_to_image(title)
                    if url:
                        selected_url = url
                        selected_title = title
                        break
                if selected_url:
                    break
        except Exception as exc:
            summary["failed"].append({"name": guide_name, "reason": f"api_error:{exc}"})
            continue

        if not selected_url:
            summary["failed"].append({"name": guide_name, "reason": "no_image_found"})
            continue

        downloaded = False
        last_error = None
        for attempt in range(1, 5):
            try:
                content = fetch_image_bytes(selected_url)
                save_path.write_bytes(content)
                downloaded = True
                break
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * attempt)

        if not downloaded:
            summary["failed"].append({"name": guide_name, "reason": f"download_error:{last_error}"})
            continue

        png_name = f"{save_base}.png"
        source_page = f"https://en.wikipedia.org/wiki/{selected_title.replace(' ', '_')}" if selected_title else ""
        upsert_source_entry(
            entries=sources,
            vehicle=guide_name,
            image_name=png_name,
            source_page=source_page,
            image_url=selected_url,
        )

        summary["downloaded"].append(
            {
                "name": guide_name,
                "image": save_name,
                "source_title": selected_title,
                "source_url": selected_url,
            }
        )

    sources.sort(key=lambda x: str(x.get("vehicle", "")).lower())
    SOURCES_PATH.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nVehicle image fetch")
    print(f"Downloaded: {len(summary['downloaded'])}")
    print(f"Skipped: {len(summary['skipped'])}")
    print(f"Failed: {len(summary['failed'])}")

    if summary["failed"]:
        print("\nFailed items:")
        for item in summary["failed"]:
            print(f" - {item['name']} -> {item['reason']}")

    if args.summary_json:
        out = Path(args.summary_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Summary JSON: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
