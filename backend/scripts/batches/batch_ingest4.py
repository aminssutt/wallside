"""Batch ingest wave 4: Top 20 missing popular vehicles (FR market priority)"""
import sys, os, time, json, hashlib, tempfile, re, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.index_manuals import extract_pdf_with_fallback, build_indexes
from src.config import CHUNK_SIZE, CHUNK_OVERLAP
try:
    from src.text_chunker import split_documents as split_document_chunks
except Exception:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    def split_document_chunks(docs, chunk_size, chunk_overlap):
        return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap).split_documents(docs)

BASE = "https://www.notice-utilisation-voiture.fr"
MANIFEST = Path(__file__).parent / "data" / "guides" / "manifest.json"
GUIDES_DIR = Path(__file__).parent / "data" / "guides"

MIN_PDF_SIZE = 50_000      # 50 KB minimum
MIN_PAGES = 15             # lowered slightly — some EV manuals are shorter
MIN_CHUNKS = 25


# ============================================================
# Source 1: notice-utilisation-voiture.fr (primary)
# ============================================================

def deep_find_pdf(ctx, brand, model):
    """Try to find PDF URL on notice-utilisation-voiture.fr"""
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/notices/{brand}/{model}", wait_until="networkidle", timeout=10000)
        time.sleep(1)
        links = set(page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"))
        versions = sorted([l for l in links if f"/{brand}/{model}/" in l and "#" not in l.split(model+"/")[-1]])
    except Exception:
        return None
    finally:
        page.close()
    if not versions:
        return None
    latest = versions[-1]
    page2 = ctx.new_page()
    try:
        page2.goto(latest, wait_until="networkidle", timeout=10000)
        time.sleep(1)
        links2 = set(page2.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"))
        fra = sorted([l for l in links2 if "FRA" in l])
        subs = sorted([l for l in links2 if latest.rstrip("/")+"/"+""  in l and "#" not in l.split("/")[-1] and l != latest])
    finally:
        page2.close()
    candidates = []
    if fra:
        candidates = fra
    elif subs:
        for sv in subs[-2:]:
            p3 = ctx.new_page()
            try:
                p3.goto(sv, wait_until="networkidle", timeout=8000)
                time.sleep(1)
                f3 = sorted([l for l in set(p3.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")) if "FRA" in l])
            finally:
                p3.close()
            if f3:
                candidates.extend(f3)
                break
    if not candidates:
        candidates = [latest]
    target = candidates[-1]
    p4 = ctx.new_page()
    try:
        p4.goto(target.rstrip("/") + "/telechargement/", wait_until="networkidle", timeout=10000)
        time.sleep(2)
        embeds = p4.eval_on_selector_all('embed[type="application/pdf"]', "els => els.map(e => e.src)")
    finally:
        p4.close()
    return embeds[0] if embeds else None


# ============================================================
# Source 2: Alternative sites (fallback)
# ============================================================

ALTERNATIVE_SOURCES = [
    # Format: (url_pattern, how_to_find_pdf)
    "https://www.manualslib.com",
    "https://manuals.info.apple.com",  # some car manuals end up here
]


def search_pdf_web(ctx, brand_name, model_name, display_name):
    """Search DuckDuckGo for the owner's manual PDF as fallback"""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return None

    queries = [
        f"{display_name} owner's manual PDF download",
        f"{display_name} notice utilisation PDF",
        f"{brand_name} {model_name} manual PDF filetype:pdf",
        f"{display_name} Bedienungsanleitung PDF",  # German manuals often available
    ]

    for query in queries:
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=10, region="wt-wt")
                for r in results:
                    url = r.get("href", "")
                    # Look for direct PDF links or known manual sites
                    if url.endswith(".pdf"):
                        return url
                    if "manualslib.com" in url or "manualzz.com" in url:
                        # Try to get the PDF from these sites
                        pdf_url = try_extract_pdf_from_manual_site(ctx, url)
                        if pdf_url:
                            return pdf_url
        except Exception as e:
            print(f"    DDG search failed for '{query[:50]}': {e}")
            continue
        time.sleep(0.5)

    return None


def try_extract_pdf_from_manual_site(ctx, url):
    """Try to extract a downloadable PDF from manualslib, manualzz, etc."""
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=15000)
        time.sleep(2)
        # Look for PDF embeds or download links
        embeds = page.eval_on_selector_all(
            'embed[type="application/pdf"], iframe[src*=".pdf"], a[href$=".pdf"]',
            "els => els.map(e => e.src || e.href)"
        )
        if embeds:
            return embeds[0]
    except Exception:
        pass
    finally:
        page.close()
    return None


def download_pdf(ctx, pdf_url):
    """Download a PDF and return the bytes + size info"""
    page = ctx.new_page()
    try:
        resp = page.request.get(pdf_url, timeout=60000)
        data = resp.body()
        return data
    except Exception as e:
        print(f"    Download failed: {e}")
        return None
    finally:
        page.close()


def ingest(ctx, brand_name, brand_slug, model_slug, display_name, segment):
    slug = f"{brand_slug}-{model_slug}".replace(" ", "-").lower()

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    if any(g["slug"] == slug for g in manifest):
        return "SKIP (already indexed)"

    # --- Try primary source first ---
    pdf_url = deep_find_pdf(ctx, brand_slug, model_slug)
    source_type = "external_pdf"

    # --- Fallback: web search ---
    if not pdf_url:
        print("→ primary failed, searching web...", end=" ", flush=True)
        pdf_url = search_pdf_web(ctx, brand_name, model_slug, display_name)
        source_type = "web_search_pdf"

    if not pdf_url:
        return "NO PDF FOUND (primary + web search)"

    # --- Download ---
    data = download_pdf(ctx, pdf_url)
    if not data:
        return f"DOWNLOAD FAILED"

    pdf_size_kb = len(data) // 1024
    if len(data) < MIN_PDF_SIZE:
        return f"TOO SMALL ({pdf_size_kb} KB)"

    # --- Extract and index ---
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(data)
    tmp.close()

    try:
        docs, pages, mode, _ = extract_pdf_with_fallback(Path(tmp.name), False, "fra+eng", 0)
        if not docs:
            return f"NO TEXT ({pdf_size_kb} KB)"
        if pages < MIN_PAGES:
            return f"TOO FEW PAGES ({pages}p, {pdf_size_kb} KB)"

        chunks = split_document_chunks(docs, CHUNK_SIZE, CHUNK_OVERLAP)
        if len(chunks) < MIN_CHUNKS:
            return f"TOO FEW CHUNKS ({len(chunks)}ch, {pages}p)"

        vs_dir = GUIDES_DIR / slug / "vector_store"
        vs_dir.mkdir(parents=True, exist_ok=True)
        build_indexes(chunks, vs_dir)

        manifest.append({
            "slug": slug, "name": display_name, "brand": brand_name,
            "image": None, "source_pdf": None,
            "source_hash": hashlib.sha256(data).hexdigest(),
            "pdf_url": pdf_url,
            "source_type": source_type,
            "page_count": pages, "chunk_count": len(chunks),
            "extraction_mode": mode,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "segment": segment,
        })

        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return f"OK {pages}p {len(chunks)}ch ({pdf_size_kb} KB) [{source_type}]"

    finally:
        os.unlink(tmp.name)


# ============================================================
# BATCH 4: Top 20 missing popular vehicles
# ============================================================

BATCH = [
    # --- French best-sellers missing ---
    ("Peugeot", "peugeot", "5008", "Peugeot 5008 (2024)", "suv"),
    ("Renault", "renault", "clio-5", "Renault Clio 5 (2024)", "citadine"),
    ("Renault", "renault", "megane-e-tech", "Renault Megane E-Tech (2023)", "berline"),
    ("Dacia", "dacia", "spring", "Dacia Spring (2024)", "citadine"),
    ("Dacia", "dacia", "jogger", "Dacia Jogger (2023)", "utilitaire"),
    ("Citroën", "citroen", "c4", "Citroën C4 (2024)", "berline"),
    ("Citroën", "citroen", "c5-aircross", "Citroën C5 Aircross (2023)", "suv"),

    # --- German best-sellers missing ---
    ("Volkswagen", "volkswagen", "id-3", "Volkswagen ID.3 (2023)", "citadine"),
    ("Volkswagen", "volkswagen", "id-4", "Volkswagen ID.4 (2023)", "suv"),
    ("Volkswagen", "volkswagen", "tiguan", "Volkswagen Tiguan (2024)", "suv"),
    ("Audi", "audi", "a3", "Audi A3 (2024)", "berline"),
    ("Audi", "audi", "q3", "Audi Q3 (2023)", "suv"),
    ("BMW", "bmw", "ix1", "BMW iX1 (2023)", "suv"),
    ("Mercedes-Benz", "mercedes", "gla", "Mercedes GLA (2024)", "suv"),
    ("Skoda", "skoda", "octavia", "Skoda Octavia (2024)", "berline"),
    ("Skoda", "skoda", "kodiaq", "Skoda Kodiaq (2024)", "suv"),

    # --- Asian best-sellers missing ---
    ("Toyota", "toyota", "rav4", "Toyota RAV4 (2024)", "suv"),
    ("Toyota", "toyota", "c-hr", "Toyota C-HR (2024)", "suv"),
    ("Hyundai", "hyundai", "kona", "Hyundai Kona (2024)", "suv"),
    ("Kia", "kia", "ev6", "Kia EV6 (2024)", "suv"),
]


if __name__ == "__main__":
    print(f"{'='*70}")
    print(f"  MECHORA — Batch Wave 4: {len(BATCH)} vehicles")
    print(f"  Quality: min {MIN_PDF_SIZE//1000}KB, min {MIN_PAGES}p, min {MIN_CHUNKS} chunks")
    print(f"  Sources: notice-utilisation-voiture.fr -> DuckDuckGo fallback")
    print(f"{'='*70}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            accept_downloads=True,
        )

        ok = fail = skip = 0
        results = []

        for brand, bslug, mslug, name, seg in BATCH:
            print(f"  [{ok+fail+skip+1:2d}/{len(BATCH)}] {name:40s} ", end="", flush=True)
            try:
                result = ingest(ctx, brand, bslug, mslug, name, seg)
                print(result)
                results.append((name, result))
                if result.startswith("OK"):
                    ok += 1
                elif "SKIP" in result:
                    skip += 1
                else:
                    fail += 1
            except Exception as e:
                msg = f"ERROR: {e!s:.80}"
                print(msg)
                results.append((name, msg))
                fail += 1
            time.sleep(1)

        browser.close()

    print(f"\n{'='*70}")
    print(f"  RESULTS: Added {ok} | Skipped {skip} | Failed {fail}")
    print(f"{'='*70}")

    if fail > 0:
        print(f"\n  FAILED vehicles (need manual PDF sourcing):")
        for name, result in results:
            if not result.startswith("OK") and "SKIP" not in result:
                print(f"    - {name}: {result}")
