"""Batch ingest wave 2: Maserati, Skoda, DS, Jaguar, Mini, Jeep, Subaru, Suzuki, Lexus, Abarth"""
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
    # Maserati (5 best)
    ("Maserati", "maserati", "levante", "Maserati Levante (2016)", "suv"),
    ("Maserati", "maserati", "grecale", "Maserati Grecale (2022)", "suv"),
    ("Maserati", "maserati", "ghibli", "Maserati Ghibli (2013)", "berline"),
    ("Maserati", "maserati", "quattroporte", "Maserati Quattroporte (2013)", "berline"),
    ("Maserati", "maserati", "mc20", "Maserati MC20 (2021)", "sportive"),
    # Skoda (6 best)
    ("Skoda", "skoda", "octavia", "Skoda Octavia (2020)", "berline"),
    ("Skoda", "skoda", "kodiaq", "Skoda Kodiaq (2017)", "suv"),
    ("Skoda", "skoda", "karoq", "Skoda Karoq (2018)", "suv"),
    ("Skoda", "skoda", "fabia", "Skoda Fabia (2021)", "citadine"),
    ("Skoda", "skoda", "kamiq", "Skoda Kamiq (2019)", "suv"),
    ("Skoda", "skoda", "enyaq", "Skoda Enyaq (2021)", "suv"),
    # DS (4 best)
    ("DS", "ds-automobiles", "ds7", "DS 7 (2018)", "suv"),
    ("DS", "ds-automobiles", "ds3-crossback", "DS 3 Crossback (2019)", "suv"),
    ("DS", "ds-automobiles", "ds4", "DS 4 (2021)", "berline"),
    ("DS", "ds-automobiles", "ds9", "DS 9 (2021)", "berline"),
    # Jaguar (5 best)
    ("Jaguar", "jaguar", "f-pace", "Jaguar F-Pace (2016)", "suv"),
    ("Jaguar", "jaguar", "e-pace", "Jaguar E-Pace (2018)", "suv"),
    ("Jaguar", "jaguar", "i-pace", "Jaguar I-Pace (2018)", "suv"),
    ("Jaguar", "jaguar", "xe", "Jaguar XE (2015)", "berline"),
    ("Jaguar", "jaguar", "xf", "Jaguar XF (2016)", "berline"),
    # Mini (4 best)
    ("Mini", "mini", "hatch", "Mini Hatch (2014)", "citadine"),
    ("Mini", "mini", "countryman", "Mini Countryman (2017)", "suv"),
    ("Mini", "mini", "clubman", "Mini Clubman (2015)", "break"),
    ("Mini", "mini", "electric", "Mini Electric (2020)", "citadine"),
    # Jeep (4 best)
    ("Jeep", "jeep", "renegade", "Jeep Renegade (2015)", "suv"),
    ("Jeep", "jeep", "compass", "Jeep Compass (2017)", "suv"),
    ("Jeep", "jeep", "avenger", "Jeep Avenger (2023)", "suv"),
    ("Jeep", "jeep", "grand-cherokee", "Jeep Grand Cherokee (2022)", "suv"),
    # Subaru (4 best)
    ("Subaru", "subaru", "forester", "Subaru Forester (2019)", "suv"),
    ("Subaru", "subaru", "outback", "Subaru Outback (2021)", "break"),
    ("Subaru", "subaru", "xv", "Subaru XV (2018)", "suv"),
    ("Subaru", "subaru", "impreza", "Subaru Impreza (2017)", "berline"),
    # Suzuki (4 best)
    ("Suzuki", "suzuki", "vitara", "Suzuki Vitara (2015)", "suv"),
    ("Suzuki", "suzuki", "swift", "Suzuki Swift (2017)", "citadine"),
    ("Suzuki", "suzuki", "s-cross", "Suzuki S-Cross (2022)", "suv"),
    ("Suzuki", "suzuki", "jimny", "Suzuki Jimny (2019)", "suv"),
    # Lexus (3 best)
    ("Lexus", "lexus", "nx", "Lexus NX (2022)", "suv"),
    ("Lexus", "lexus", "rx", "Lexus RX (2023)", "suv"),
    ("Lexus", "lexus", "ux", "Lexus UX (2019)", "suv"),
    # Abarth (2 best)
    ("Abarth", "abarth", "595", "Abarth 595 (2012)", "sportive"),
    ("Abarth", "abarth", "500e", "Abarth 500e (2023)", "sportive"),
]


if __name__ == "__main__":
    print(f"Starting batch wave 2: {len(BATCH)} vehicles\n")
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
