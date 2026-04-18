"""Batch ingest vintage/classic vehicles"""
import sys, os, time, json, hashlib, tempfile
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from index_manuals import extract_pdf_with_fallback, build_indexes
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


def deep_find_pdf(ctx, brand, model):
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/notices/{brand}/{model}", wait_until="networkidle", timeout=10000)
        time.sleep(1)
        links = set(page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"))
        versions = sorted([l for l in links if f"/{brand}/{model}/" in l and "#" not in l.split(model+"/")[-1]])
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
        resp = page.request.get(pdf_url, timeout=30000)
        data = resp.body()
    finally:
        page.close()
    if len(data) < 5000:
        return "TOO SMALL"
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(data)
    tmp.close()
    try:
        docs, pages, mode, _ = extract_pdf_with_fallback(Path(tmp.name), False, "fra+eng", 0)
        if not docs:
            return "NO TEXT"
        chunks = split_document_chunks(docs, CHUNK_SIZE, CHUNK_OVERLAP)
        vs_dir = GUIDES_DIR / slug / "vector_store"
        vs_dir.mkdir(parents=True, exist_ok=True)
        build_indexes(chunks, vs_dir)
        manifest.append({
            "slug": slug, "name": display_name, "brand": brand_name,
            "image": None, "source_pdf": None,
            "source_hash": hashlib.sha256(data).hexdigest(),
            "pdf_url": pdf_url, "source_url": f"{BASE}/notices/{brand_slug}/{model_slug}",
            "source_type": "external_pdf", "page_count": pages, "chunk_count": len(chunks),
            "extraction_mode": mode, "indexed_at": datetime.now(timezone.utc).isoformat(),
            "segment": segment,
        })
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        return f"{pages}p {len(chunks)}ch"
    finally:
        os.unlink(tmp.name)


BATCH = [
    # French icons
    ("Citroën", "citroen", "2cv", "Citroën 2CV", "classique"),
    ("Citroën", "citroen", "cx", "Citroën CX (1974-1991)", "classique"),
    ("Citroën", "citroen", "bx", "Citroën BX (1982-1994)", "classique"),
    ("Citroën", "citroen", "saxo", "Citroën Saxo (1996-2003)", "citadine"),
    ("Renault", "renault", "5", "Renault 5 (1972-1996)", "classique"),
    ("Renault", "renault", "21", "Renault 21 (1986-1994)", "classique"),
    ("Renault", "renault", "19", "Renault 19 (1988-1997)", "classique"),
    ("Renault", "renault", "laguna", "Renault Laguna (1994-2015)", "berline"),
    ("Renault", "renault", "safrane", "Renault Safrane (1992-2000)", "classique"),
    ("Renault", "renault", "megane", "Renault Megane (1995-2016)", "berline"),
    ("Peugeot", "peugeot", "406", "Peugeot 406 (1995-2004)", "berline"),
    ("Peugeot", "peugeot", "107", "Peugeot 107 (2005-2014)", "citadine"),
    # Italian classics
    ("Fiat", "fiat", "uno", "Fiat Uno (1983-1995)", "classique"),
    ("Fiat", "fiat", "punto", "Fiat Punto (1993-2018)", "citadine"),
    ("Alfa Romeo", "alfa-romeo", "147", "Alfa Romeo 147 (2000-2010)", "berline"),
    ("Alfa Romeo", "alfa-romeo", "156", "Alfa Romeo 156 (1997-2007)", "berline"),
    ("Alfa Romeo", "alfa-romeo", "159", "Alfa Romeo 159 (2005-2011)", "berline"),
    ("Lancia", "lancia", "ypsilon", "Lancia Ypsilon (2003-2023)", "citadine"),
    # German
    ("Volkswagen", "volkswagen", "golf", "Volkswagen Golf (toutes gen.)", "berline"),
    # Japanese
    ("Honda", "honda", "civic", "Honda Civic (1972-2021)", "berline"),
    ("Nissan", "nissan", "micra", "Nissan Micra (1982-2022)", "citadine"),
    # British
    ("Jaguar", "jaguar", "xj", "Jaguar XJ (1968-2019)", "berline"),
    ("Jaguar", "jaguar", "xk", "Jaguar XK (1996-2014)", "sportive"),
    # American
    ("Ford", "ford", "mustang", "Ford Mustang (1964-2024)", "sportive"),
    ("Chevrolet", "chevrolet", "camaro", "Chevrolet Camaro (1966-2024)", "sportive"),
]


if __name__ == "__main__":
    print(f"Starting vintage batch: {len(BATCH)} vehicles\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0", accept_downloads=True)
        ok = fail = 0
        for brand, bslug, mslug, name, seg in BATCH:
            print(f"{name:40s} ", end="", flush=True)
            try:
                result = ingest(ctx, brand, bslug, mslug, name, seg)
                print(result)
                if "ch" in result or result == "SKIP":
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"ERROR: {e!s:.50}")
                fail += 1
            time.sleep(0.5)
        browser.close()
    print(f"\nDone! OK: {ok}, Failed: {fail}")
