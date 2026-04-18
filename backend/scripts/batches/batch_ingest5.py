"""Batch ingest wave 5: More popular vehicles from notice-utilisation-voiture.fr"""
import sys, os, io, time, json, hashlib, tempfile
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
MIN_PDF_SIZE = 50_000
MIN_PAGES = 15
MIN_CHUNKS = 25


def deep_find_pdf(ctx, brand, model):
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
    candidates = fra if fra else []
    if not candidates and subs:
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


def ingest(ctx, brand_name, brand_slug, model_slug, display_name, segment):
    slug = f"{brand_slug}-{model_slug}".replace(" ", "-").lower()
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    if any(g["slug"] == slug for g in manifest):
        return "SKIP"
    pdf_url = deep_find_pdf(ctx, brand_slug, model_slug)
    if not pdf_url:
        return "NO PDF"
    page = ctx.new_page()
    try:
        resp = page.request.get(pdf_url, timeout=60000)
        data = resp.body()
    finally:
        page.close()
    pdf_size_kb = len(data) // 1024
    if len(data) < MIN_PDF_SIZE:
        return f"TOO SMALL ({pdf_size_kb} KB)"
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(data)
    tmp.close()
    try:
        docs, pages, mode, _ = extract_pdf_with_fallback(Path(tmp.name), False, "fra+eng", 0)
        if not docs:
            return f"NO TEXT ({pdf_size_kb} KB)"
        if pages < MIN_PAGES:
            return f"TOO FEW PAGES ({pages}p)"
        chunks = split_document_chunks(docs, CHUNK_SIZE, CHUNK_OVERLAP)
        if len(chunks) < MIN_CHUNKS:
            return f"TOO FEW CHUNKS ({len(chunks)}ch)"
        vs_dir = GUIDES_DIR / slug / "vector_store"
        vs_dir.mkdir(parents=True, exist_ok=True)
        build_indexes(chunks, vs_dir)
        manifest.append({
            "slug": slug, "name": display_name, "brand": brand_name,
            "image": None, "source_pdf": None,
            "source_hash": hashlib.sha256(data).hexdigest(),
            "pdf_url": pdf_url, "source_type": "external_pdf",
            "page_count": pages, "chunk_count": len(chunks),
            "extraction_mode": mode, "indexed_at": datetime.now(timezone.utc).isoformat(),
            "segment": segment,
        })
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        return f"OK {pages}p {len(chunks)}ch ({pdf_size_kb} KB)"
    finally:
        os.unlink(tmp.name)


BATCH = [
    # Popular models not yet indexed
    # Renault
    ("Renault", "renault", "scenic", "Renault Scenic (2024)", "suv"),
    ("Renault", "renault", "twingo", "Renault Twingo (2019)", "citadine"),
    ("Renault", "renault", "kangoo", "Renault Kangoo (2021)", "utilitaire"),
    ("Renault", "renault", "espace", "Renault Espace (2023)", "suv"),
    # Peugeot
    ("Peugeot", "peugeot", "508", "Peugeot 508 (2019)", "berline"),
    ("Peugeot", "peugeot", "partner", "Peugeot Partner (2019)", "utilitaire"),
    ("Peugeot", "peugeot", "e-208", "Peugeot e-208 (2023)", "citadine"),
    # Citroen
    ("Citroen", "citroen", "berlingo", "Citroen Berlingo (2019)", "utilitaire"),
    ("Citroen", "citroen", "c3-aircross", "Citroen C3 Aircross (2023)", "suv"),
    # Dacia
    ("Dacia", "dacia", "lodgy", "Dacia Lodgy (2012)", "utilitaire"),
    # Toyota
    ("Toyota", "toyota", "land-cruiser", "Toyota Land Cruiser (2024)", "suv"),
    ("Toyota", "toyota", "hilux", "Toyota Hilux (2016)", "utilitaire"),
    ("Toyota", "toyota", "supra", "Toyota Supra (2019)", "sportive"),
    # Nissan
    ("Nissan", "nissan", "x-trail", "Nissan X-Trail (2023)", "suv"),
    ("Nissan", "nissan", "ariya", "Nissan Ariya (2023)", "suv"),
    # Ford
    ("Ford", "ford", "kuga", "Ford Kuga (2020)", "suv"),
    ("Ford", "ford", "ranger", "Ford Ranger (2023)", "utilitaire"),
    # Hyundai
    ("Hyundai", "hyundai", "bayon", "Hyundai Bayon (2021)", "suv"),
    ("Hyundai", "hyundai", "ioniq-6", "Hyundai Ioniq 6 (2023)", "berline"),
    # Kia
    ("Kia", "kia", "ceed", "Kia Ceed (2022)", "berline"),
    ("Kia", "kia", "picanto", "Kia Picanto (2021)", "citadine"),
    # Volvo
    ("Volvo", "volvo", "ex30", "Volvo EX30 (2024)", "suv"),
    # Mini
    ("Mini", "mini", "cooper", "Mini Cooper (2021)", "citadine"),
    # Fiat
    ("Fiat", "fiat", "500-electrique", "Fiat 500 Electrique (2021)", "citadine"),
]


if __name__ == "__main__":
    print(f"=== Batch wave 5: {len(BATCH)} vehicles ===\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", accept_downloads=True)
        ok = fail = skip = 0
        for brand, bslug, mslug, name, seg in BATCH:
            print(f"  [{ok+fail+skip+1:2d}/{len(BATCH)}] {name:40s} ", end="", flush=True)
            try:
                result = ingest(ctx, brand, bslug, mslug, name, seg)
                print(result)
                if result.startswith("OK"): ok += 1
                elif result == "SKIP": skip += 1
                else: fail += 1
            except Exception as e:
                print(f"ERROR: {e!s:.60}")
                fail += 1
            time.sleep(1)
        browser.close()
    print(f"\n=== Done! Added: {ok} | Skipped: {skip} | Failed: {fail} ===")
