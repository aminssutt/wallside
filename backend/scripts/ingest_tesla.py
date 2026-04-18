"""
Tesla Official Manual Ingestion Script.

Downloads PDFs from Tesla's official owner's manual site using Playwright
(required because Tesla blocks automated requests), then indexes them
via the existing RAG pipeline.

Usage:
    python ingest_tesla.py discover
    python ingest_tesla.py download --model model3 --locale en_us
    python ingest_tesla.py download-all
    python ingest_tesla.py index --model model3
    python ingest_tesla.py index-all
    python ingest_tesla.py full            # download-all + index-all
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import CHUNK_SIZE, CHUNK_OVERLAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tesla_ingest")

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent
CAR_DATA_DIR = PROJECT_ROOT / "car data" / "Tesla"
GUIDES_DIR = BACKEND_DIR / "data" / "guides"
IMAGES_DIR = BACKEND_DIR / "data" / "vehicle_images"
MANIFEST_PATH = GUIDES_DIR / "manifest.json"

PARSER_VERSION = "1.0"

# Tesla model registry
TESLA_MODELS = {
    "model3": {
        "name": "Tesla Model 3",
        "years": "2024+",
        "segment": "berline",
        "slug": "tesla-model-3",
        "pdf_path": "model3",
    },
    "modely": {
        "name": "Tesla Model Y",
        "years": "2020-2025",
        "segment": "suv",
        "slug": "tesla-model-y",
        "pdf_path": "modely",
    },
    "models": {
        "name": "Tesla Model S",
        "years": "2021+",
        "segment": "berline",
        "slug": "tesla-model-s",
        "pdf_path": "models",
    },
    "modelx": {
        "name": "Tesla Model X",
        "years": "2021+",
        "segment": "suv",
        "slug": "tesla-model-x",
        "pdf_path": "modelx",
    },
}

LOCALES = ["en_us", "fr_fr"]


def get_pdf_url(model_key: str, locale: str) -> str:
    m = TESLA_MODELS[model_key]
    return f"https://www.tesla.com/ownersmanual/{m['pdf_path']}/{locale}/Owners_Manual.pdf"


def get_html_url(model_key: str, locale: str) -> str:
    m = TESLA_MODELS[model_key]
    return f"https://www.tesla.com/ownersmanual/{m['pdf_path']}/{locale}/"


def get_local_pdf_path(model_key: str, locale: str = "en_us") -> Path:
    m = TESLA_MODELS[model_key]
    suffix = f" ({locale})" if locale != "en_us" else ""
    return CAR_DATA_DIR / f"{m['name']}{suffix}.pdf"


def compute_checksum(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


# ============================================
# DISCOVER
# ============================================

def cmd_discover(args):
    """List available Tesla manuals."""
    log.info("=== Tesla Manual Discovery ===")
    for key, m in TESLA_MODELS.items():
        for locale in LOCALES:
            pdf_url = get_pdf_url(key, locale)
            local = get_local_pdf_path(key, locale)
            exists = "EXISTS" if local.exists() else "MISSING"
            log.info(f"  {m['name']} [{locale}]: {exists} -> {pdf_url}")


# ============================================
# DOWNLOAD (via Playwright)
# ============================================

def download_pdf_playwright(model_key: str, locale: str = "en_us") -> Path:
    """Download a Tesla manual PDF using Playwright to bypass bot protection."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
        sys.exit(1)

    pdf_url = get_pdf_url(model_key, locale)
    local_path = get_local_pdf_path(model_key, locale)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"Downloading {pdf_url} -> {local_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Navigate to the manual page first to get cookies
        html_url = get_html_url(model_key, locale)
        log.info(f"  Loading manual page for cookies: {html_url}")
        try:
            page.goto(html_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)
        except Exception as e:
            log.warning(f"  Manual page load warning: {e}")

        # Now download the PDF
        log.info(f"  Downloading PDF...")
        try:
            with page.expect_download(timeout=60000) as download_info:
                page.goto(pdf_url)
            download = download_info.value
            download.save_as(str(local_path))
        except Exception:
            # Fallback: try direct navigation
            response = page.goto(pdf_url, timeout=60000)
            if response and response.ok:
                body = response.body()
                with open(local_path, "wb") as f:
                    f.write(body)
            else:
                log.error(f"  Failed to download: HTTP {response.status if response else 'N/A'}")
                browser.close()
                return None

        browser.close()

    # Verify it's a real PDF
    with open(local_path, "rb") as f:
        header = f.read(5)
    if header != b"%PDF-":
        log.error(f"  Downloaded file is not a valid PDF (header: {header})")
        local_path.unlink(missing_ok=True)
        return None

    size_mb = local_path.stat().st_size / (1024 * 1024)
    log.info(f"  OK: {local_path.name} ({size_mb:.1f} MB)")
    return local_path


def cmd_download(args):
    """Download a specific Tesla manual."""
    model = args.model
    locale = args.locale or "en_us"
    if model not in TESLA_MODELS:
        log.error(f"Unknown model: {model}. Available: {list(TESLA_MODELS.keys())}")
        return
    result = download_pdf_playwright(model, locale)
    if result:
        log.info(f"Downloaded: {result}")
    else:
        log.error("Download failed.")


def cmd_download_all(args):
    """Download all Tesla manuals."""
    for key in TESLA_MODELS:
        for locale in LOCALES:
            local = get_local_pdf_path(key, locale)
            if local.exists():
                log.info(f"  SKIP (exists): {local.name}")
                continue
            download_pdf_playwright(key, locale)


# ============================================
# INDEX (reuses existing pipeline)
# ============================================

def index_tesla_pdf(model_key: str, locale: str = "en_us", force: bool = False) -> bool:
    """Index a Tesla PDF using the existing RAG pipeline."""
    from src.vector_store import get_embeddings
    from index_manuals import extract_pdf_with_fallback, slugify

    try:
        from src.text_chunker import split_documents as split_document_chunks
    except ImportError:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        def split_document_chunks(docs, chunk_size, chunk_overlap):
            splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            return splitter.split_documents(docs)

    m = TESLA_MODELS[model_key]
    pdf_path = get_local_pdf_path(model_key, locale)
    if not pdf_path.exists():
        log.error(f"PDF not found: {pdf_path}")
        return False

    slug = m["slug"]
    if locale != "en_us":
        slug += f"-{locale.replace('_', '-')}"

    name = f"{m['name']} ({m['years']})"
    if locale != "en_us":
        name += f" [{locale}]"

    # Check idempotency via checksum
    current_hash = compute_checksum(pdf_path)
    manifest = _load_manifest()
    existing = next((g for g in manifest if g["slug"] == slug), None)
    if existing and existing.get("source_hash") == current_hash and not force:
        log.info(f"  SKIP (unchanged): {slug}")
        return True

    log.info(f"Indexing {name} ({slug})...")

    # Extract
    docs, page_count, extraction_mode, _ = extract_pdf_with_fallback(
        pdf_path, allow_ocr=False, ocr_lang="eng+fra", ocr_max_pages=0
    )
    if not docs:
        log.error(f"  No text extracted from {pdf_path}")
        return False
    log.info(f"  Extracted {page_count} pages, {len(docs)} documents")

    # Chunk
    chunks = split_document_chunks(docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    log.info(f"  Chunked into {len(chunks)} segments")

    # Index (FAISS + BM25)
    vs_dir = GUIDES_DIR / slug / "vector_store"
    vs_dir.mkdir(parents=True, exist_ok=True)

    from index_manuals import build_indexes
    build_indexes(chunks, vs_dir)
    log.info(f"  Built FAISS + BM25 indexes")

    # Update manifest
    entry = {
        "slug": slug,
        "name": name,
        "brand": "Tesla",
        "image": _find_tesla_image(model_key),
        "source_pdf": str(pdf_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_hash": current_hash,
        "source_url": get_html_url(model_key, locale),
        "source_official": True,
        "source_type": "pdf",
        "locale": locale,
        "page_count": page_count,
        "chunk_count": len(chunks),
        "extraction_mode": extraction_mode,
        "parser_version": PARSER_VERSION,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "segment": m["segment"],
    }

    # Upsert in manifest
    manifest = [g for g in manifest if g["slug"] != slug]
    manifest.append(entry)
    _save_manifest(manifest)
    log.info(f"  Manifest updated: {slug} ({len(chunks)} chunks)")
    return True


def _find_tesla_image(model_key: str) -> str:
    """Find or return a vehicle image filename."""
    m = TESLA_MODELS[model_key]
    # Check existing images
    for pattern in [m["name"].lower(), model_key.replace("model", "model ")]:
        for img in IMAGES_DIR.glob("*"):
            if pattern in img.name.lower():
                return img.name
    return ""


def _load_manifest():
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_manifest(manifest):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def cmd_index(args):
    """Index a specific Tesla model."""
    model = args.model
    locale = args.locale or "en_us"
    force = args.force
    if model not in TESLA_MODELS:
        log.error(f"Unknown model: {model}. Available: {list(TESLA_MODELS.keys())}")
        return
    index_tesla_pdf(model, locale, force)


def cmd_index_all(args):
    """Index all downloaded Tesla PDFs."""
    force = getattr(args, "force", False)
    for key in TESLA_MODELS:
        for locale in LOCALES:
            local = get_local_pdf_path(key, locale)
            if local.exists():
                index_tesla_pdf(key, locale, force)


def cmd_full(args):
    """Download all + index all."""
    cmd_download_all(args)
    cmd_index_all(args)


# ============================================
# CLI
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Tesla Manual Ingestion")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("discover", help="List available Tesla manuals")

    dl = sub.add_parser("download", help="Download a Tesla manual")
    dl.add_argument("--model", required=True, choices=TESLA_MODELS.keys())
    dl.add_argument("--locale", default="en_us")

    sub.add_parser("download-all", help="Download all Tesla manuals")

    idx = sub.add_parser("index", help="Index a Tesla manual")
    idx.add_argument("--model", required=True, choices=TESLA_MODELS.keys())
    idx.add_argument("--locale", default="en_us")
    idx.add_argument("--force", action="store_true")

    idx_all = sub.add_parser("index-all", help="Index all downloaded Tesla PDFs")
    idx_all.add_argument("--force", action="store_true")

    sub.add_parser("full", help="Download all + index all")

    args = parser.parse_args()
    commands = {
        "discover": cmd_discover,
        "download": cmd_download,
        "download-all": cmd_download_all,
        "index": cmd_index,
        "index-all": cmd_index_all,
        "full": cmd_full,
    }
    cmd = commands.get(args.command)
    if cmd:
        cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
