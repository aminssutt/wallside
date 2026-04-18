"""
Universal Vehicle Manual Ingestion from notice-utilisation-voiture.fr.

Downloads PDFs from notice-utilisation-voiture.fr, extracts the inspirauto.fr
embed URL for frontend iframe display, indexes via the existing RAG pipeline,
and stores the external PDF URL in the manifest.

Usage:
    # Index a single vehicle
    python ingest_vehicle.py --brand "Bugatti" --model "chiron" \
        --url "https://www.notice-utilisation-voiture.fr/notices/bugatti/chiron" \
        --name "Bugatti Chiron" --segment "sportive"

    # Discover all models for a brand
    python ingest_vehicle.py --discover --brand "bugatti"

    # Batch-download and index all models for a brand
    python ingest_vehicle.py --batch --brand "bugatti"

    # Migrate existing manifest entries to add pdf_url
    python ingest_vehicle.py --migrate-urls

    # Force re-index even if checksum unchanged
    python ingest_vehicle.py --brand "Bugatti" --model "chiron" \
        --url "..." --name "Bugatti Chiron" --force

    # Keep the local PDF after indexing (default: delete after indexing)
    python ingest_vehicle.py --brand "Bugatti" --model "chiron" \
        --url "..." --name "Bugatti Chiron" --keep-pdf
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, quote
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import CHUNK_SIZE, CHUNK_OVERLAP, DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ingest_vehicle")

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
CAR_DATA_DIR = PROJECT_ROOT / "car data"
GUIDES_DIR = DATA_DIR / "guides"
IMAGES_DIR = DATA_DIR / "vehicle_images"
MANIFEST_PATH = GUIDES_DIR / "manifest.json"
SOURCES_PATH = IMAGES_DIR / "sources.json"

PARSER_VERSION = "2.0"

NOTICE_BASE_URL = "https://www.notice-utilisation-voiture.fr"
NOTICE_BRANDS_URL = f"{NOTICE_BASE_URL}/marques"

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ============================================================================
# Utility helpers
# ============================================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    s = name.lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "guide"


def compute_checksum(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def normalize_brand(brand: str) -> str:
    raw = (brand or "").strip()
    if not raw:
        return "Autres"
    raw = re.sub(r"[_-]+", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw.title()


def normalize_ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


# ============================================================================
# Manifest I/O
# ============================================================================

def _load_manifest() -> List[dict]:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _save_manifest(manifest: List[dict]):
    GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    manifest.sort(
        key=lambda g: (
            str(g.get("brand", "")).lower(),
            str(g.get("name", "")).lower(),
        )
    )
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# ============================================================================
# Web scraping: notice-utilisation-voiture.fr
# ============================================================================

def _ensure_playwright():
    """Import playwright, with a helpful error if missing."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        log.error(
            "Playwright not installed. Run:\n"
            "  pip install playwright && python -m playwright install chromium"
        )
        sys.exit(1)


def discover_brand_models(brand_slug: str) -> List[Dict[str, str]]:
    """
    Discover all model pages for a brand on notice-utilisation-voiture.fr.

    Returns a list of dicts: {name, model_slug, url}
    """
    sync_playwright = _ensure_playwright()
    brand_url = f"{NOTICE_BASE_URL}/notices/{brand_slug}"

    log.info(f"Discovering models for brand '{brand_slug}' at {brand_url}")

    models = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        try:
            page.goto(brand_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # The page lists model links under the brand
            # Look for links that point to /notices/<brand>/<model>
            links = page.query_selector_all("a[href]")
            seen = set()

            for link in links:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").strip()

                # Normalize href
                if href.startswith("/"):
                    href = f"{NOTICE_BASE_URL}{href}"

                # Match pattern: /notices/<brand>/<model>
                pattern = f"/notices/{brand_slug}/"
                if pattern not in href.lower():
                    continue

                # Extract model slug from URL
                parts = href.rstrip("/").split("/")
                if len(parts) < 2:
                    continue
                model_slug = parts[-1].lower()

                # Skip duplicates and brand-level page
                if model_slug == brand_slug or model_slug in seen:
                    continue
                seen.add(model_slug)

                name = text or model_slug.replace("-", " ").title()
                models.append({
                    "name": name,
                    "model_slug": model_slug,
                    "url": href,
                })

        except Exception as e:
            log.error(f"Failed to discover models: {e}")
        finally:
            browser.close()

    log.info(f"  Found {len(models)} models for '{brand_slug}'")
    return models


def extract_pdf_embed_url(page_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Navigate to a vehicle page on notice-utilisation-voiture.fr and extract
    the inspirauto.fr PDF embed URL.

    The site typically has a "telechargement" sub-page or an iframe/embed
    pointing to inspirauto.fr/getPdf.php?...

    Returns: (pdf_url, download_page_url)
    """
    sync_playwright = _ensure_playwright()

    log.info(f"Extracting PDF URL from {page_url}")

    pdf_url = None
    download_page = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        try:
            # First try the main page
            page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # Look for inspirauto.fr URL in iframes, links, or embedded content
            pdf_url = _find_inspirauto_url(page)

            if not pdf_url:
                # Try the /telechargement sub-page
                telechargement_url = page_url.rstrip("/") + "/telechargement"
                download_page = telechargement_url
                log.info(f"  Trying telechargement page: {telechargement_url}")

                try:
                    page.goto(
                        telechargement_url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    time.sleep(3)
                    pdf_url = _find_inspirauto_url(page)
                except Exception as e:
                    log.warning(f"  Telechargement page error: {e}")

            if not pdf_url:
                # Try alternative paths
                for suffix in ["/notice", "/pdf", "/manuel"]:
                    alt_url = page_url.rstrip("/") + suffix
                    try:
                        page.goto(
                            alt_url,
                            wait_until="domcontentloaded",
                            timeout=15000,
                        )
                        time.sleep(2)
                        pdf_url = _find_inspirauto_url(page)
                        if pdf_url:
                            download_page = alt_url
                            break
                    except Exception:
                        continue

        except Exception as e:
            log.error(f"  Navigation error: {e}")
        finally:
            browser.close()

    if pdf_url:
        log.info(f"  Found PDF URL: {pdf_url}")
    else:
        log.warning(f"  No inspirauto.fr PDF URL found for {page_url}")

    return pdf_url, download_page


def _find_inspirauto_url(page) -> Optional[str]:
    """
    Search the current page DOM for an inspirauto.fr PDF URL.
    Looks in iframes, object/embed tags, links, and inline scripts.
    """
    # 1. Check iframes
    iframes = page.query_selector_all("iframe[src]")
    for iframe in iframes:
        src = iframe.get_attribute("src") or ""
        if "inspirauto.fr" in src:
            return src

    # 2. Check object/embed tags
    for tag in ["object[data]", "embed[src]"]:
        elements = page.query_selector_all(tag)
        for el in elements:
            attr = el.get_attribute("data") or el.get_attribute("src") or ""
            if "inspirauto.fr" in attr:
                return attr

    # 3. Check links with inspirauto.fr
    links = page.query_selector_all("a[href]")
    for link in links:
        href = link.get_attribute("href") or ""
        if "inspirauto.fr" in href and ("getPdf" in href or ".pdf" in href.lower()):
            return href

    # 4. Check page source / inline scripts for inspirauto URLs
    try:
        html_content = page.content()
        # Match inspirauto.fr URLs in the HTML
        patterns = [
            r'(https?://[^"\'<>\s]*inspirauto\.fr[^"\'<>\s]*getPdf[^"\'<>\s]*)',
            r'(https?://[^"\'<>\s]*inspirauto\.fr[^"\'<>\s]*\.pdf[^"\'<>\s]*)',
            r'(//[^"\'<>\s]*inspirauto\.fr[^"\'<>\s]*getPdf[^"\'<>\s]*)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            if matches:
                url = matches[0]
                if url.startswith("//"):
                    url = "https:" + url
                return url
    except Exception:
        pass

    return None


def download_pdf_from_url(
    pdf_url: str,
    dest_path: Path,
    timeout: int = 120,
) -> bool:
    """Download a PDF from a URL (inspirauto.fr or direct) to a local path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    log.info(f"  Downloading PDF to {dest_path.name}...")

    # inspirauto.fr sometimes requires browser-like headers
    sync_playwright = _ensure_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        try:
            # Try to navigate directly to the PDF URL
            response = page.goto(pdf_url, timeout=timeout * 1000)

            if response and response.ok:
                content_type = response.headers.get("content-type", "")
                if "pdf" in content_type.lower() or "octet-stream" in content_type.lower():
                    body = response.body()
                    dest_path.write_bytes(body)
                else:
                    # Might be an HTML page with embedded PDF; try to get the body anyway
                    body = response.body()
                    if body[:5] == b"%PDF-":
                        dest_path.write_bytes(body)
                    else:
                        log.warning(
                            f"  Response is not a PDF (content-type: {content_type}). "
                            "Trying expect_download approach..."
                        )
                        browser.close()
                        return _download_pdf_with_expect(pdf_url, dest_path, timeout)
            else:
                status = response.status if response else "N/A"
                log.error(f"  Download failed: HTTP {status}")
                browser.close()
                return False

        except Exception as e:
            log.warning(f"  Direct download failed ({e}), trying alternative...")
            browser.close()
            return _download_pdf_with_expect(pdf_url, dest_path, timeout)

        browser.close()

    # Verify it's a real PDF
    if dest_path.exists():
        with open(dest_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            log.error(f"  Downloaded file is not a valid PDF (header: {header!r})")
            dest_path.unlink(missing_ok=True)
            return False

        size_mb = dest_path.stat().st_size / (1024 * 1024)
        log.info(f"  OK: {dest_path.name} ({size_mb:.1f} MB)")
        return True

    return False


def _download_pdf_with_expect(
    pdf_url: str,
    dest_path: Path,
    timeout: int = 120,
) -> bool:
    """Fallback: use Playwright expect_download to capture the file."""
    sync_playwright = _ensure_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        try:
            with page.expect_download(timeout=timeout * 1000) as download_info:
                page.goto(pdf_url)
            download = download_info.value
            download.save_as(str(dest_path))
        except Exception as e:
            log.error(f"  expect_download also failed: {e}")
            browser.close()
            return False

        browser.close()

    # Verify
    if dest_path.exists():
        with open(dest_path, "rb") as f:
            header = f.read(5)
        if header == b"%PDF-":
            size_mb = dest_path.stat().st_size / (1024 * 1024)
            log.info(f"  OK: {dest_path.name} ({size_mb:.1f} MB)")
            return True
        else:
            log.error(f"  File is not a valid PDF (header: {header!r})")
            dest_path.unlink(missing_ok=True)

    return False


# ============================================================================
# Wikipedia image download
# ============================================================================

def _wiki_request_json(params: Dict[str, str]) -> dict:
    from urllib.parse import urlencode as _urlencode
    query = _urlencode(params)
    req = Request(f"{WIKI_API}?{query}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _wiki_title_to_image(title: str) -> Optional[str]:
    data = _wiki_request_json({
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": "1280",
        "titles": title,
    })
    pages = data.get("query", {}).get("pages", {})
    for page_data in pages.values():
        thumb = page_data.get("thumbnail", {})
        src = thumb.get("source")
        if src:
            return src
    return None


def _wiki_search_titles(query: str, limit: int = 6) -> List[str]:
    data = _wiki_request_json({
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srlimit": str(limit),
    })
    return [
        item.get("title", "")
        for item in data.get("query", {}).get("search", [])
        if item.get("title")
    ]


def fetch_vehicle_image(
    guide_name: str,
    force: bool = False,
) -> Optional[str]:
    """
    Download a vehicle image from Wikipedia and process with rembg.
    Returns the image filename if successful, None otherwise.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    save_base = normalize_ascii(guide_name)
    if not save_base:
        log.warning(f"  Cannot derive image name from '{guide_name}'")
        return None

    # Check if image already exists
    existing_slug = slugify(guide_name)
    if not force:
        for img in IMAGES_DIR.iterdir():
            if not img.is_file():
                continue
            if img.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            if slugify(img.stem) == existing_slug:
                log.info(f"  Image already exists: {img.name}")
                return img.name

    # Search Wikipedia
    queries = [guide_name]
    no_year = re.sub(r"\b\d{4}(?:\s*[-/]\s*\d{4})?\b", "", guide_name).strip()
    no_year = re.sub(r"\s+", " ", no_year)
    if no_year and no_year != guide_name:
        queries.append(no_year)

    selected_url = None
    selected_title = None

    try:
        for query in queries:
            # Direct title lookup
            url = _wiki_title_to_image(query)
            if url:
                selected_url = url
                selected_title = query
                break

            # Search fallback
            titles = _wiki_search_titles(query)
            for title in titles:
                url = _wiki_title_to_image(title)
                if url:
                    selected_url = url
                    selected_title = title
                    break
            if selected_url:
                break
    except Exception as e:
        log.warning(f"  Wikipedia image search failed: {e}")
        return None

    if not selected_url:
        log.warning(f"  No Wikipedia image found for '{guide_name}'")
        return None

    # Download
    save_name = f"{save_base}.jpg"
    save_path = IMAGES_DIR / save_name

    downloaded = False
    for attempt in range(1, 4):
        try:
            req = Request(
                selected_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": "https://en.wikipedia.org/",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                },
            )
            with urlopen(req, timeout=60) as response:
                content = response.read()
            save_path.write_bytes(content)
            downloaded = True
            break
        except Exception as e:
            log.warning(f"  Image download attempt {attempt} failed: {e}")
            time.sleep(1.5 * attempt)

    if not downloaded:
        log.warning(f"  Failed to download image for '{guide_name}'")
        return None

    log.info(f"  Downloaded image: {save_name}")

    # Process with rembg (background removal) if available
    png_name = f"{save_base}.png"
    png_path = IMAGES_DIR / png_name
    try:
        from PIL import Image
        from rembg import remove

        input_bytes = save_path.read_bytes()
        output_bytes = remove(input_bytes)
        png_path.write_bytes(output_bytes)
        save_path.unlink(missing_ok=True)  # remove JPG, keep PNG
        log.info(f"  Background removed: {png_name}")
        final_name = png_name
    except ImportError:
        log.info("  rembg not installed, keeping image as-is")
        final_name = save_name
    except Exception as e:
        log.warning(f"  Background removal failed: {e}")
        final_name = save_name

    # Update sources.json
    try:
        sources = []
        if SOURCES_PATH.exists():
            sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        source_page = (
            f"https://en.wikipedia.org/wiki/{selected_title.replace(' ', '_')}"
            if selected_title else ""
        )
        # Upsert
        key = guide_name.strip().lower()
        found = False
        for entry in sources:
            if str(entry.get("vehicle", "")).strip().lower() == key:
                entry.update({
                    "vehicle": guide_name,
                    "image": final_name,
                    "source_page": source_page,
                    "image_url": selected_url,
                })
                found = True
                break
        if not found:
            sources.append({
                "vehicle": guide_name,
                "image": final_name,
                "source_page": source_page,
                "image_url": selected_url,
            })
        sources.sort(key=lambda x: str(x.get("vehicle", "")).lower())
        SOURCES_PATH.write_text(
            json.dumps(sources, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning(f"  Failed to update sources.json: {e}")

    return final_name


# ============================================================================
# Indexing: extract -> chunk -> FAISS + BM25
# ============================================================================

def index_vehicle_pdf(
    pdf_path: Path,
    guide_name: str,
    brand: str,
    slug: str,
    pdf_url: Optional[str],
    source_url: Optional[str],
    segment: Optional[str] = None,
    image_filename: Optional[str] = None,
    force: bool = False,
) -> dict:
    """
    Index a vehicle PDF using the existing RAG pipeline.
    Returns a result dict with 'ok' and 'entry' or 'reason'.
    """
    from index_manuals import extract_pdf_with_fallback, build_indexes
    from src.text_chunker import split_documents as split_document_chunks

    log.info(f"Indexing '{guide_name}' (slug: {slug})...")

    if not pdf_path.exists():
        return {"ok": False, "reason": f"PDF not found: {pdf_path}"}

    current_hash = compute_checksum(pdf_path)

    # Check idempotency via checksum
    if not force:
        manifest = _load_manifest()
        existing = next((g for g in manifest if g["slug"] == slug), None)
        if existing and existing.get("source_hash") == current_hash:
            log.info(f"  SKIP (unchanged checksum): {slug}")
            return {"ok": True, "entry": existing, "skipped": True}

    # Step 1: Extract text
    log.info("  [1/3] Extracting text...")
    docs, page_count, extraction_mode, note = extract_pdf_with_fallback(
        pdf_path, allow_ocr=True, ocr_lang="fra+eng", ocr_max_pages=0
    )
    if not docs:
        reason = note or "no_extractable_text"
        log.error(f"  FAILED: {reason}")
        return {"ok": False, "reason": reason}

    log.info(f"         {len(docs)} docs, {page_count} pages, mode: {extraction_mode}")

    # Step 2: Chunk
    log.info("  [2/3] Chunking...")
    chunks = split_document_chunks(
        documents=docs,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    log.info(f"         {len(chunks)} chunks")

    if not chunks:
        return {"ok": False, "reason": "chunking_failed_no_chunks"}

    # Step 3: Build indexes
    log.info("  [3/3] Building FAISS + BM25 indexes...")
    vs_dir = GUIDES_DIR / slug / "vector_store"
    vs_dir.mkdir(parents=True, exist_ok=True)

    try:
        build_indexes(chunks, vs_dir)
    except Exception as e:
        return {"ok": False, "reason": f"index_build_error: {e}"}

    # Build manifest entry
    entry = {
        "slug": slug,
        "name": guide_name,
        "brand": normalize_brand(brand),
        "image": image_filename,
        "source_pdf": None,  # No local PDF stored in manifest for external sources
        "source_hash": current_hash,
        "pdf_url": pdf_url,         # External inspirauto.fr URL for iframe
        "source_url": source_url,   # notice-utilisation-voiture.fr page
        "source_type": "external_pdf",
        "page_count": page_count,
        "chunk_count": len(chunks),
        "extraction_mode": extraction_mode,
        "parser_version": PARSER_VERSION,
        "indexed_at": now_iso(),
    }

    if segment:
        entry["segment"] = segment

    log.info(f"  Indexed: {slug} ({len(chunks)} chunks)")
    return {"ok": True, "entry": entry}


# ============================================================================
# Full ingestion pipeline for a single vehicle
# ============================================================================

def ingest_single_vehicle(
    brand: str,
    model_slug: str,
    page_url: str,
    guide_name: str,
    segment: Optional[str] = None,
    force: bool = False,
    keep_pdf: bool = False,
) -> bool:
    """
    Full pipeline for a single vehicle:
    1. Extract inspirauto.fr PDF URL from the notice page
    2. Download PDF to a temp location
    3. Index via RAG pipeline
    4. Store external PDF URL in manifest
    5. Fetch Wikipedia image
    6. Clean up temp PDF (unless --keep-pdf)
    """
    slug = slugify(guide_name)

    log.info(f"\n{'=' * 60}")
    log.info(f"Ingesting: {guide_name}")
    log.info(f"  Brand: {brand}")
    log.info(f"  Slug: {slug}")
    log.info(f"  Page: {page_url}")
    log.info(f"{'=' * 60}")

    # Step 1: Extract inspirauto.fr PDF URL
    pdf_url, download_page = extract_pdf_embed_url(page_url)

    if not pdf_url:
        log.error(f"  Could not find PDF URL for {guide_name}")
        log.error("  You can provide it manually with --pdf-url")
        return False

    # Step 2: Download PDF to temp location for text extraction
    temp_dir = Path(tempfile.mkdtemp(prefix="auris_ingest_"))
    pdf_filename = f"{slug}.pdf"
    temp_pdf = temp_dir / pdf_filename

    # Optionally also store in car data/ for caching
    cache_dir = CAR_DATA_DIR / normalize_brand(brand)
    cache_pdf = cache_dir / f"{guide_name}.pdf"

    download_ok = download_pdf_from_url(pdf_url, temp_pdf)
    if not download_ok:
        log.error(f"  Failed to download PDF from {pdf_url}")
        # Cleanup
        temp_pdf.unlink(missing_ok=True)
        temp_dir.rmdir()
        return False

    # Step 3: Fetch Wikipedia image
    image_filename = fetch_vehicle_image(guide_name, force=force)

    # Step 4: Index the PDF
    result = index_vehicle_pdf(
        pdf_path=temp_pdf,
        guide_name=guide_name,
        brand=brand,
        slug=slug,
        pdf_url=pdf_url,
        source_url=page_url,
        segment=segment,
        image_filename=image_filename,
        force=force,
    )

    if not result["ok"]:
        log.error(f"  Indexing failed: {result.get('reason')}")
        temp_pdf.unlink(missing_ok=True)
        temp_dir.rmdir()
        return False

    # Step 5: Update manifest
    entry = result["entry"]
    manifest = _load_manifest()
    manifest = [g for g in manifest if g["slug"] != slug]
    manifest.append(entry)
    _save_manifest(manifest)
    log.info(f"  Manifest updated: {slug}")

    # Step 6: Handle local PDF
    if keep_pdf:
        cache_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(str(temp_pdf), str(cache_pdf))
        log.info(f"  PDF cached at: {cache_pdf}")

    # Cleanup temp
    temp_pdf.unlink(missing_ok=True)
    try:
        temp_dir.rmdir()
    except OSError:
        pass

    log.info(f"  Done: {guide_name}")
    return True


# ============================================================================
# Migration: add pdf_url to existing manifest entries
# ============================================================================

def migrate_existing_urls():
    """
    For each existing guide in the manifest that lacks a pdf_url,
    try to find its page on notice-utilisation-voiture.fr and extract
    the inspirauto.fr PDF URL.

    This is best-effort: not all vehicles will have pages on the site.
    """
    manifest = _load_manifest()
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    log.info(f"\n{'=' * 60}")
    log.info("Migrating existing manifest entries to add pdf_url")
    log.info(f"{'=' * 60}")
    log.info(f"  Total entries: {len(manifest)}")

    for entry in manifest:
        slug = entry.get("slug", "")
        name = entry.get("name", "")
        brand = entry.get("brand", "")

        # Skip entries that already have a pdf_url
        if entry.get("pdf_url"):
            skipped_count += 1
            continue

        # Skip entries that are from non-PDF sources
        source_pdf = entry.get("source_pdf", "")
        if not source_pdf:
            skipped_count += 1
            continue

        # Try to construct a notice-utilisation-voiture.fr URL
        brand_slug = slugify(brand)
        # Try to extract model name from the guide name
        model_name = name
        # Remove brand prefix if present
        model_name_lower = model_name.lower()
        brand_lower = brand.lower()
        if model_name_lower.startswith(brand_lower):
            model_name = model_name[len(brand):].strip()

        # Remove year ranges like (2013-2020) or 2013-2020
        model_name = re.sub(r"\s*\(?\d{4}\s*[-/]\s*\d{4}\)?\s*", "", model_name).strip()
        model_name = re.sub(r"\s*\(?\d{4}\+?\)?\s*$", "", model_name).strip()

        model_slug = slugify(model_name)
        if not model_slug:
            skipped_count += 1
            continue

        page_url = f"{NOTICE_BASE_URL}/notices/{brand_slug}/{model_slug}"

        log.info(f"  Trying: {name} -> {page_url}")

        try:
            pdf_url, _ = extract_pdf_embed_url(page_url)
            if pdf_url:
                entry["pdf_url"] = pdf_url
                entry["source_url"] = page_url
                updated_count += 1
                log.info(f"    Found: {pdf_url}")
            else:
                failed_count += 1
                log.info(f"    Not found")
        except Exception as e:
            failed_count += 1
            log.warning(f"    Error: {e}")

        # Be polite to the server
        time.sleep(1)

    _save_manifest(manifest)

    log.info(f"\nMigration complete:")
    log.info(f"  Updated: {updated_count}")
    log.info(f"  Skipped (already has pdf_url): {skipped_count}")
    log.info(f"  Failed (no URL found): {failed_count}")


# ============================================================================
# CLI commands
# ============================================================================

def cmd_ingest(args):
    """Ingest a single vehicle."""
    if not args.url:
        log.error("--url is required for single vehicle ingestion")
        sys.exit(1)

    brand = args.brand
    model = args.model or ""
    page_url = args.url
    name = args.name or f"{normalize_brand(brand)} {model.replace('-', ' ').title()}".strip()
    segment = args.segment

    # Allow manually specifying the pdf_url to skip scraping
    if args.pdf_url:
        # Direct indexing with a known PDF URL
        slug = slugify(name)
        temp_dir = Path(tempfile.mkdtemp(prefix="auris_ingest_"))
        temp_pdf = temp_dir / f"{slug}.pdf"

        download_ok = download_pdf_from_url(args.pdf_url, temp_pdf)
        if not download_ok:
            log.error(f"Failed to download PDF from {args.pdf_url}")
            temp_pdf.unlink(missing_ok=True)
            temp_dir.rmdir()
            sys.exit(1)

        image_filename = fetch_vehicle_image(name, force=args.force)

        result = index_vehicle_pdf(
            pdf_path=temp_pdf,
            guide_name=name,
            brand=brand,
            slug=slug,
            pdf_url=args.pdf_url,
            source_url=page_url,
            segment=segment,
            image_filename=image_filename,
            force=args.force,
        )

        if result["ok"]:
            entry = result["entry"]
            manifest = _load_manifest()
            manifest = [g for g in manifest if g["slug"] != slug]
            manifest.append(entry)
            _save_manifest(manifest)
            log.info(f"Done: {name}")
        else:
            log.error(f"Indexing failed: {result.get('reason')}")

        temp_pdf.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass
        return

    success = ingest_single_vehicle(
        brand=brand,
        model_slug=model,
        page_url=page_url,
        guide_name=name,
        segment=segment,
        force=args.force,
        keep_pdf=args.keep_pdf,
    )

    if not success:
        sys.exit(1)


def cmd_discover(args):
    """Discover and list all models for a brand."""
    brand = args.brand
    brand_slug = slugify(brand)

    models = discover_brand_models(brand_slug)

    if not models:
        log.info(f"No models found for '{brand}'")
        log.info(f"Check the URL: {NOTICE_BASE_URL}/notices/{brand_slug}")
        return

    print(f"\nModels for {normalize_brand(brand)}:")
    print(f"{'=' * 60}")
    for m in sorted(models, key=lambda x: x["name"].lower()):
        print(f"  {m['name']}")
        print(f"    Slug: {m['model_slug']}")
        print(f"    URL:  {m['url']}")
        print()

    print(f"Total: {len(models)} models")
    print(f"\nTo ingest a model, run:")
    print(f"  python ingest_vehicle.py --brand \"{brand}\" --model \"<model_slug>\" \\")
    print(f"    --url \"<url>\" --name \"<Full Name>\"")
    print(f"\nTo ingest all models:")
    print(f"  python ingest_vehicle.py --batch --brand \"{brand}\"")


def cmd_batch(args):
    """Batch-download and index all models for a brand."""
    brand = args.brand
    brand_slug = slugify(brand)
    segment = args.segment

    models = discover_brand_models(brand_slug)

    if not models:
        log.error(f"No models found for '{brand}'")
        return

    log.info(f"\nBatch ingestion: {len(models)} models for {normalize_brand(brand)}")

    successes = []
    failures = []

    for m in models:
        model_name = m["name"]
        model_url = m["url"]
        model_slug_val = m["model_slug"]

        # Build a proper guide name
        brand_norm = normalize_brand(brand)
        if not model_name.lower().startswith(brand_norm.lower()):
            guide_name = f"{brand_norm} {model_name}"
        else:
            guide_name = model_name

        success = ingest_single_vehicle(
            brand=brand,
            model_slug=model_slug_val,
            page_url=model_url,
            guide_name=guide_name,
            segment=segment,
            force=args.force,
            keep_pdf=args.keep_pdf,
        )

        if success:
            successes.append(guide_name)
        else:
            failures.append(guide_name)

        # Be polite between requests
        time.sleep(2)

    log.info(f"\n{'=' * 60}")
    log.info(f"Batch complete for {normalize_brand(brand)}")
    log.info(f"  Succeeded: {len(successes)}")
    log.info(f"  Failed:    {len(failures)}")
    if failures:
        log.info(f"  Failed models:")
        for name in failures:
            log.info(f"    - {name}")


def cmd_migrate(args):
    """Migrate existing manifest entries to add pdf_url."""
    migrate_existing_urls()


# ============================================================================
# CLI entry point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Universal Vehicle Manual Ingestion from notice-utilisation-voiture.fr",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single vehicle
  python ingest_vehicle.py --brand "Bugatti" --model "chiron" \\
      --url "https://www.notice-utilisation-voiture.fr/notices/bugatti/chiron" \\
      --name "Bugatti Chiron" --segment "sportive"

  # Discover models
  python ingest_vehicle.py --discover --brand "bugatti"

  # Batch all models for a brand
  python ingest_vehicle.py --batch --brand "bugatti"

  # Migrate existing entries
  python ingest_vehicle.py --migrate-urls

  # Direct PDF URL (skip scraping)
  python ingest_vehicle.py --brand "Bugatti" --model "chiron" \\
      --url "https://www.notice-utilisation-voiture.fr/notices/bugatti/chiron" \\
      --name "Bugatti Chiron" --pdf-url "https://inspirauto.fr/getPdf.php?id=123"
""",
    )

    # Mode selectors
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--discover",
        action="store_true",
        help="List all models for a brand on notice-utilisation-voiture.fr",
    )
    mode_group.add_argument(
        "--batch",
        action="store_true",
        help="Download and index ALL models for a brand",
    )
    mode_group.add_argument(
        "--migrate-urls",
        action="store_true",
        help="Add pdf_url to existing manifest entries (best-effort)",
    )

    # Vehicle identification
    parser.add_argument("--brand", help="Vehicle brand (e.g. 'Bugatti')")
    parser.add_argument("--model", help="Model slug (e.g. 'chiron')")
    parser.add_argument(
        "--url",
        help="Full URL on notice-utilisation-voiture.fr",
    )
    parser.add_argument(
        "--name",
        help="Full display name (e.g. 'Bugatti Chiron'). Auto-generated if omitted.",
    )
    parser.add_argument(
        "--segment",
        help="Vehicle segment (e.g. 'sportive', 'berline', 'suv', 'classique')",
    )
    parser.add_argument(
        "--pdf-url",
        help="Direct inspirauto.fr PDF URL (skip scraping step)",
    )

    # Options
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-index even if checksum is unchanged",
    )
    parser.add_argument(
        "--keep-pdf",
        action="store_true",
        help="Keep a copy of the PDF in 'car data/<brand>/' after indexing",
    )

    args = parser.parse_args()

    # Route to the correct command
    if args.migrate_urls:
        cmd_migrate(args)
    elif args.discover:
        if not args.brand:
            parser.error("--discover requires --brand")
        cmd_discover(args)
    elif args.batch:
        if not args.brand:
            parser.error("--batch requires --brand")
        cmd_batch(args)
    else:
        # Single vehicle ingestion
        if not args.brand:
            parser.error("--brand is required for single vehicle ingestion")
        cmd_ingest(args)


if __name__ == "__main__":
    main()
