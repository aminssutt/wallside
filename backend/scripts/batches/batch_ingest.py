"""Batch ingest vehicles from notice-utilisation-voiture.fr"""
import sys, os, time, json, hashlib, tempfile
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
    # Toyota (8)
    ("Toyota", "toyota", "yaris", "Toyota Yaris (2020)", "citadine"),
    ("Toyota", "toyota", "yaris-cross", "Toyota Yaris Cross (2021)", "suv"),
    ("Toyota", "toyota", "c-hr", "Toyota C-HR (2017)", "suv"),
    ("Toyota", "toyota", "rav4", "Toyota RAV4 (2019)", "suv"),
    ("Toyota", "toyota", "corolla", "Toyota Corolla (2019)", "berline"),
    ("Toyota", "toyota", "aygo-x", "Toyota Aygo X (2022)", "citadine"),
    ("Toyota", "toyota", "camry", "Toyota Camry (2019)", "berline"),
    ("Toyota", "toyota", "land-cruiser", "Toyota Land Cruiser (2024)", "suv"),
    # BMW (7)
    ("BMW", "bmw", "serie-1", "BMW Serie 1 (2019)", "berline"),
    ("BMW", "bmw", "serie-5", "BMW Serie 5 (2024)", "berline"),
    ("BMW", "bmw", "x1", "BMW X1 (2023)", "suv"),
    ("BMW", "bmw", "x3", "BMW X3 (2018)", "suv"),
    ("BMW", "bmw", "x5", "BMW X5 (2019)", "suv"),
    ("BMW", "bmw", "ix", "BMW iX (2022)", "suv"),
    ("BMW", "bmw", "i4", "BMW i4 (2022)", "berline"),
    # Mercedes (6)
    ("Mercedes", "mercedes-benz", "classe-a", "Mercedes Classe A (2018)", "berline"),
    ("Mercedes", "mercedes-benz", "classe-b", "Mercedes Classe B (2019)", "monospace"),
    ("Mercedes", "mercedes-benz", "classe-e", "Mercedes Classe E (2024)", "berline"),
    ("Mercedes", "mercedes-benz", "glc", "Mercedes GLC (2023)", "suv"),
    ("Mercedes", "mercedes-benz", "gle", "Mercedes GLE (2019)", "suv"),
    ("Mercedes", "mercedes-benz", "gla", "Mercedes GLA (2020)", "suv"),
    # Ford (5)
    ("Ford", "ford", "puma", "Ford Puma (2020)", "suv"),
    ("Ford", "ford", "focus", "Ford Focus (2018)", "berline"),
    ("Ford", "ford", "fiesta", "Ford Fiesta (2017)", "citadine"),
    ("Ford", "ford", "kuga", "Ford Kuga (2020)", "suv"),
    ("Ford", "ford", "mustang-mach-e", "Ford Mustang Mach-E (2021)", "suv"),
    # Volvo (5)
    ("Volvo", "volvo", "xc40", "Volvo XC40 (2018)", "suv"),
    ("Volvo", "volvo", "xc60", "Volvo XC60 (2017)", "suv"),
    ("Volvo", "volvo", "xc90", "Volvo XC90 (2015)", "suv"),
    ("Volvo", "volvo", "v60", "Volvo V60 (2019)", "break"),
    ("Volvo", "volvo", "s60", "Volvo S60 (2019)", "berline"),
    # Fiat (4)
    ("Fiat", "fiat", "500", "Fiat 500 (2020)", "citadine"),
    ("Fiat", "fiat", "500x", "Fiat 500X (2019)", "suv"),
    ("Fiat", "fiat", "tipo", "Fiat Tipo (2016)", "berline"),
    ("Fiat", "fiat", "panda", "Fiat Panda (2012)", "citadine"),
    # Opel (4)
    ("Opel", "opel", "corsa", "Opel Corsa (2020)", "citadine"),
    ("Opel", "opel", "astra", "Opel Astra (2022)", "berline"),
    ("Opel", "opel", "mokka", "Opel Mokka (2021)", "suv"),
    ("Opel", "opel", "crossland", "Opel Crossland (2017)", "suv"),
    # Nissan (3)
    ("Nissan", "nissan", "qashqai", "Nissan Qashqai (2022)", "suv"),
    ("Nissan", "nissan", "juke", "Nissan Juke (2020)", "suv"),
    ("Nissan", "nissan", "leaf", "Nissan Leaf (2018)", "berline"),
    # Mazda (2)
    ("Mazda", "mazda", "cx-5", "Mazda CX-5 (2017)", "suv"),
    ("Mazda", "mazda", "3", "Mazda 3 (2019)", "berline"),
    # Cupra (1)
    ("Cupra", "cupra", "formentor", "Cupra Formentor (2021)", "suv"),
]


if __name__ == "__main__":
    print(f"Starting batch: {len(BATCH)} vehicles\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0", accept_downloads=True)
        ok = fail = 0
        for brand, bslug, mslug, name, seg in BATCH:
            print(f"{name:35s} ", end="", flush=True)
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
