"""Batch ingest wave 3: Asian popular + Sporty vehicles (part 1: 20 vehicles)"""
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

MIN_PDF_SIZE = 50_000      # 50 KB minimum — skip tiny/broken PDFs
MIN_PAGES = 20             # skip manuals with fewer than 20 pages
MIN_CHUNKS = 30            # skip if too few chunks for useful RAG


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
            "pdf_url": pdf_url, "source_url": f"{BASE}/notices/{brand_slug}/{model_slug}",
            "source_type": "external_pdf", "page_count": pages, "chunk_count": len(chunks),
            "extraction_mode": mode, "indexed_at": datetime.now(timezone.utc).isoformat(),
            "segment": segment,
        })
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        return f"OK {pages}p {len(chunks)}ch ({pdf_size_kb} KB)"
    finally:
        os.unlink(tmp.name)


BATCH = [
    # === Asian best-sellers (14) ===
    # Kia — manquants, gros manuels attendus
    ("Kia", "kia", "ev6", "Kia EV6 (2022)", "suv"),
    ("Kia", "kia", "niro", "Kia Niro (2022)", "suv"),
    ("Kia", "kia", "picanto", "Kia Picanto (2021)", "citadine"),
    ("Kia", "kia", "stonic", "Kia Stonic (2021)", "suv"),
    # Hyundai — best-sellers mondiaux manquants
    ("Hyundai", "hyundai", "tucson", "Hyundai Tucson (2021)", "suv"),
    ("Hyundai", "hyundai", "kona", "Hyundai Kona (2023)", "suv"),
    ("Hyundai", "hyundai", "ioniq-5", "Hyundai Ioniq 5 (2022)", "suv"),
    ("Hyundai", "hyundai", "i20", "Hyundai i20 (2020)", "citadine"),
    ("Hyundai", "hyundai", "santa-fe", "Hyundai Santa Fe (2021)", "suv"),
    # Honda — manquants
    ("Honda", "honda", "cr-v", "Honda CR-V (2023)", "suv"),
    ("Honda", "honda", "hr-v", "Honda HR-V (2022)", "suv"),
    ("Honda", "honda", "jazz", "Honda Jazz (2020)", "citadine"),
    # Toyota — manquants
    ("Toyota", "toyota", "rav4", "Toyota RAV4 (2019)", "suv"),
    ("Toyota", "toyota", "c-hr", "Toyota C-HR (2024)", "suv"),

    # === Sportives (6) ===
    ("Porsche", "porsche", "911", "Porsche 911 (2019)", "sportive"),
    ("Porsche", "porsche", "cayenne", "Porsche Cayenne (2023)", "suv"),
    ("Porsche", "porsche", "taycan", "Porsche Taycan (2020)", "sportive"),
    ("Porsche", "porsche", "macan", "Porsche Macan (2022)", "suv"),
    ("Alpine", "alpine", "a110", "Alpine A110 (2018)", "sportive"),
    ("Kia", "kia", "stinger", "Kia Stinger (2018)", "sportive"),
]


if __name__ == "__main__":
    print(f"=== Batch wave 3 (Asian + Sport): {len(BATCH)} vehicles ===")
    print(f"Quality gates: min {MIN_PDF_SIZE//1000}KB, min {MIN_PAGES} pages, min {MIN_CHUNKS} chunks\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0", accept_downloads=True)
        ok = fail = skip = 0
        for brand, bslug, mslug, name, seg in BATCH:
            print(f"  {name:35s} ", end="", flush=True)
            try:
                result = ingest(ctx, brand, bslug, mslug, name, seg)
                print(result)
                if result.startswith("OK"):
                    ok += 1
                elif result == "SKIP":
                    skip += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"ERROR: {e!s:.60}")
                fail += 1
            time.sleep(0.5)
        browser.close()
    print(f"\n=== Done! Added: {ok} | Skipped: {skip} | Failed: {fail} ===")
