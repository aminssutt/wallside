"""
Index vehicle manuals into FAISS + BM25 for the guide system.

Primary source format:
    car data/<brand>/*.pdf

Each PDF becomes one guide chatbot. Indexes are stored in:
    backend/data/guides/<slug>/vector_store/

Supports incremental indexing:
- unchanged PDFs are skipped (no re-RAG)
- changed/new PDFs are indexed
- failed extraction PDFs are excluded and removed from manifest/chat
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure backend/ (one level up) is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import CHUNK_SIZE, CHUNK_OVERLAP, DATA_DIR
from src.guide_manager import GUIDES_DIR, slugify
from src.vector_store import get_embeddings
from src.text_chunker import split_documents as split_document_chunks


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

CAR_DATA_DIR = PROJECT_ROOT / "car data"
MANUALS_DIR = PROJECT_ROOT / "manuel"
IMAGES_DIR = MANUALS_DIR / "voiture"

VEHICLE_IMAGES_DIR = DATA_DIR / "vehicle_images"
VEHICLE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _tokenize(text: str):
    return re.findall(r"[a-zà-ÿ0-9]{2,}", text.lower())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_brand(brand: Optional[str]) -> str:
    raw = (brand or "").strip()
    if not raw:
        return "Autres"
    raw = re.sub(r"[_-]+", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw.title()


def infer_brand_from_guide_name(guide_name: str, current_brand: Optional[str] = None) -> str:
    """Infer brand when metadata is missing/legacy."""
    normalized_current = normalize_brand(current_brand)
    if normalized_current.lower() != "autres":
        return normalized_current

    name = (guide_name or "").strip()
    lower_name = name.lower()

    direct_map = [
        ("clio", "Renault"),
        ("tesla", "Tesla"),
        ("toyota", "Toyota"),
        ("auris", "Toyota"),
    ]
    for token, brand in direct_map:
        if token in lower_name:
            return brand

    words = re.findall(r"[a-z0-9]+", lower_name)
    if words:
        first = words[0]
        if first in {"manuel", "guide"} and len(words) > 1:
            first = words[1]
        if first:
            return first.title()

    return "Autres"


def derive_guide_name(pdf_name: str) -> str:
    stem = Path(pdf_name).stem
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"(?i)^\s*manuel\s+", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem.title()


def guide_is_indexed(slug: str) -> bool:
    vs_dir = GUIDES_DIR / slug / "vector_store"
    bm25_ok = (vs_dir / "bm25_index.pkl").exists()
    faiss_ok = (vs_dir / "index.faiss").exists()
    return bm25_ok or faiss_ok


def delete_guide_data(slug: str) -> bool:
    guide_dir = GUIDES_DIR / slug
    if not guide_dir.exists():
        return False
    shutil.rmtree(guide_dir)
    return True


def discover_manuals_from_car_data() -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []

    if not CAR_DATA_DIR.exists():
        return entries

    brand_dirs = sorted(
        [p for p in CAR_DATA_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.name.lower(),
    )

    for brand_dir in brand_dirs:
        brand = normalize_brand(brand_dir.name)
        pdf_files = sorted(
            [
                p for p in brand_dir.rglob("*")
                if p.is_file() and p.suffix.lower() == ".pdf"
            ],
            key=lambda p: p.name.lower(),
        )

        for pdf_path in pdf_files:
            rel_path = str(pdf_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            entries.append({
                "pdf_path": str(pdf_path),
                "source_pdf": rel_path,
                "guide_name": derive_guide_name(pdf_path.name),
                "brand": brand,
            })

    return entries


def discover_legacy_manuals() -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []

    if not MANUALS_DIR.exists():
        return entries

    pdf_files = sorted(
        [
            p for p in MANUALS_DIR.iterdir()
            if p.is_file() and p.suffix.lower() == ".pdf"
        ],
        key=lambda p: p.name.lower(),
    )

    for pdf_path in pdf_files:
        guide_name = derive_guide_name(pdf_path.name)
        rel_path = str(pdf_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        entries.append({
            "pdf_path": str(pdf_path),
            "source_pdf": rel_path,
            "guide_name": guide_name,
            "brand": infer_brand_from_guide_name(guide_name, "Autres"),
        })

    return entries


def _candidate_image_dirs() -> List[Path]:
    dirs = [VEHICLE_IMAGES_DIR, IMAGES_DIR]
    return [p for p in dirs if p.exists()]


def find_matching_image(guide_name: str, brand: Optional[str]) -> Optional[str]:
    image_dirs = _candidate_image_dirs()
    if not image_dirs:
        return None

    guide_slug = slugify(guide_name)
    brand_slug = slugify(brand or "")
    combined_slug = slugify(f"{brand or ''} {guide_name}")

    candidates = {guide_slug, combined_slug}
    if brand_slug and guide_slug.startswith(f"{brand_slug}-"):
        candidates.add(guide_slug[len(brand_slug) + 1:])

    for image_dir in image_dirs:
        for img in image_dir.iterdir():
            if img.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            img_slug = slugify(img.stem)
            if img_slug in candidates:
                return img.name
            if any(c and (c in img_slug or img_slug in c) for c in candidates):
                return img.name

    return None


def extract_pdf_pypdf(pdf_path: Path):
    from pypdf import PdfReader
    from langchain_core.documents import Document

    documents = []
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            documents.append(Document(
                page_content=text,
                metadata={
                    "source_file": pdf_path.name,
                    "page": i + 1,
                    "total_pages": total_pages,
                },
            ))

    documents.sort(key=lambda d: d.metadata.get("page", 0))
    return documents, total_pages


def _ocr_runtime_ready() -> Tuple[bool, str]:
    missing = []
    if importlib.util.find_spec("fitz") is None:
        missing.append("pymupdf")
    if importlib.util.find_spec("PIL") is None:
        missing.append("pillow")
    if importlib.util.find_spec("pytesseract") is None:
        missing.append("pytesseract")

    import shutil as _shutil
    if _shutil.which("tesseract") is None:
        missing.append("tesseract-binary")

    if missing:
        return False, "ocr_unavailable:" + ",".join(missing)

    return True, ""


def extract_pdf_ocr(pdf_path: Path, ocr_lang: str, ocr_max_pages: int):
    from io import BytesIO

    import fitz
    import pytesseract
    from PIL import Image
    from langchain_core.documents import Document

    documents = []
    pdf = fitz.open(str(pdf_path))
    total_pages = pdf.page_count

    page_limit = total_pages
    if ocr_max_pages and ocr_max_pages > 0:
        page_limit = min(total_pages, ocr_max_pages)

    for i in range(page_limit):
        page = pdf.load_page(i)
        pix = page.get_pixmap(dpi=220, alpha=False)
        image = Image.open(BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(image, lang=ocr_lang)
        image.close()

        if text and text.strip():
            documents.append(Document(
                page_content=text,
                metadata={
                    "source_file": pdf_path.name,
                    "page": i + 1,
                    "total_pages": total_pages,
                    "extraction": "ocr",
                },
            ))

    if documents:
        return documents, total_pages, ""

    if page_limit < total_pages:
        return [], total_pages, f"ocr_no_text_first_{page_limit}_pages"

    return [], total_pages, "ocr_no_text"


def extract_pdf_with_fallback(
    pdf_path: Path,
    allow_ocr: bool,
    ocr_lang: str,
    ocr_max_pages: int,
):
    docs, total_pages = extract_pdf_pypdf(pdf_path)
    if docs:
        return docs, total_pages, "pypdf", ""

    if not allow_ocr:
        return [], total_pages, "none", "no_extractable_text_and_ocr_disabled"

    runtime_ok, runtime_reason = _ocr_runtime_ready()
    if not runtime_ok:
        return [], total_pages, "none", runtime_reason

    ocr_docs, ocr_total_pages, ocr_reason = extract_pdf_ocr(
        pdf_path=pdf_path,
        ocr_lang=ocr_lang,
        ocr_max_pages=ocr_max_pages,
    )
    if ocr_docs:
        return ocr_docs, ocr_total_pages, "ocr", ""

    return [], max(total_pages, ocr_total_pages), "none", ocr_reason or "no_extractable_text"


def build_indexes(chunks, vs_dir: Path):
    import pickle
    from rank_bm25 import BM25Okapi

    if vs_dir.exists():
        shutil.rmtree(vs_dir)
    vs_dir.mkdir(parents=True, exist_ok=True)

    faiss_available = importlib.util.find_spec("faiss") is not None
    if faiss_available:
        from langchain_community.vectorstores import FAISS

        embeddings = get_embeddings()
        batch_size = 200
        vector_store = None

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            if vector_store is None:
                vector_store = FAISS.from_documents(documents=batch, embedding=embeddings)
            else:
                vector_store.add_documents(batch)

        vector_store.save_local(str(vs_dir))

    corpus = [_tokenize(c.page_content) for c in chunks]
    bm25 = BM25Okapi(corpus)

    bm25_path = vs_dir / "bm25_index.pkl"
    with bm25_path.open("wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)


def _reserve_slug(base_slug: str, used: set[str]) -> str:
    safe_base = base_slug or "guide"
    slug = safe_base
    idx = 2
    while slug in used:
        slug = f"{safe_base}-{idx}"
        idx += 1
    used.add(slug)
    return slug


def _load_existing_manifest() -> List[dict]:
    manifest_path = GUIDES_DIR / "manifest.json"
    if not manifest_path.exists():
        return []

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass

    return []


def index_single_manual(
    pdf_path: Path,
    guide_name: str,
    image_filename: Optional[str] = None,
    brand: Optional[str] = None,
    slug: Optional[str] = None,
    source_pdf: Optional[str] = None,
    source_hash: Optional[str] = None,
    allow_ocr: bool = True,
    ocr_lang: str = "fra+eng",
    ocr_max_pages: int = 0,
):
    guide_slug = slug or slugify(guide_name)
    guide_dir = GUIDES_DIR / guide_slug
    vs_dir = guide_dir / "vector_store"

    print(f"\n{'=' * 60}")
    print(f"Indexing: {guide_name}")
    print(f"  Brand: {brand or 'Autres'}")
    print(f"  PDF: {pdf_path.name}")
    print(f"  Slug: {guide_slug}")
    print(f"  Output: {vs_dir}")
    print(f"{'=' * 60}")

    print("  [1/3] Extracting text...")
    docs, total_pages, extraction_mode, extraction_note = extract_pdf_with_fallback(
        pdf_path=pdf_path,
        allow_ocr=allow_ocr,
        ocr_lang=ocr_lang,
        ocr_max_pages=ocr_max_pages,
    )
    print(f"         pages with text: {len(docs)} / total pages: {total_pages}")
    print(f"         mode: {extraction_mode}")

    if not docs:
        reason = extraction_note or "no_extractable_text"
        print(f"  FAILED: {reason}")
        return {
            "ok": False,
            "reason": reason,
            "slug": guide_slug,
            "name": guide_name,
            "brand": normalize_brand(brand),
            "source_pdf": source_pdf,
        }

    print("  [2/3] Chunking...")
    chunks = split_document_chunks(
        documents=docs,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    print(f"         chunks: {len(chunks)}")

    if not chunks:
        reason = "chunking_failed_no_chunks"
        print(f"  FAILED: {reason}")
        return {
            "ok": False,
            "reason": reason,
            "slug": guide_slug,
            "name": guide_name,
            "brand": normalize_brand(brand),
            "source_pdf": source_pdf,
        }

    print("  [3/3] Building indexes...")
    try:
        build_indexes(chunks, vs_dir)
    except ModuleNotFoundError as exc:
        reason = f"missing_dependency:{exc.name}"
        print(f"  FAILED: {reason}")
        return {
            "ok": False,
            "reason": reason,
            "slug": guide_slug,
            "name": guide_name,
            "brand": normalize_brand(brand),
            "source_pdf": source_pdf,
        }

    entry = {
        "slug": guide_slug,
        "name": guide_name,
        "brand": normalize_brand(brand),
        "image": image_filename,
        "source_pdf": source_pdf,
        "source_hash": source_hash,
        "page_count": int(total_pages),
        "chunk_count": len(chunks),
        "extraction_mode": extraction_mode,
        "indexed_at": now_iso(),
    }

    return {
        "ok": True,
        "entry": entry,
    }


def _summary_item(slug: str, name: str, brand: str, source_pdf: Optional[str], reason: Optional[str] = None):
    item = {
        "slug": slug,
        "name": name,
        "brand": brand,
        "source_pdf": source_pdf,
    }
    if reason:
        item["reason"] = reason
    return item


def _print_group(title: str, items: List[dict]):
    print(f"\n{title}: {len(items)}")
    if not items:
        return
    for item in items:
        reason = item.get("reason")
        if reason:
            print(f"  - [{item['brand']}] {item['name']} ({item['slug']}) -> {reason}")
        else:
            print(f"  - [{item['brand']}] {item['name']} ({item['slug']})")


def parse_args():
    parser = argparse.ArgumentParser(description="Incremental vehicle manual indexing")
    parser.add_argument("--summary-json", help="Optional path to write a JSON summary")
    parser.add_argument("--force", action="store_true", help="Force re-indexing even when unchanged")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback for scanned PDFs")
    parser.add_argument(
        "--prune-missing-sources",
        action="store_true",
        help="Remove existing guides whose source_pdf is missing from car data",
    )
    parser.add_argument(
        "--ocr-lang",
        default=os.getenv("OCR_LANG", "fra+eng+kor"),
        help="Tesseract OCR languages (default: fra+eng+kor)",
    )
    parser.add_argument(
        "--ocr-max-pages",
        type=int,
        default=int(os.getenv("OCR_MAX_PAGES", "0")),
        help="Limit OCR to first N pages (0 = all pages)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("\n" + "=" * 60)
    print("  Vehicle Manual Indexing (Incremental)")
    print("=" * 60)

    discovered = discover_manuals_from_car_data()
    source_mode = "car_data"

    if not discovered:
        discovered = discover_legacy_manuals()
        source_mode = "legacy"

    if not discovered:
        print(f"\nERROR: No PDF files found in {CAR_DATA_DIR} or {MANUALS_DIR}")
        print("Expected structure: car data/<brand>/<vehicle>.pdf")
        sys.exit(1)

    print(f"\nSource mode: {source_mode}")
    print(f"PDFs discovered: {len(discovered)}")

    existing_manifest = _load_existing_manifest()

    managed_existing_by_source: Dict[str, dict] = {}
    kept_existing: List[dict] = []

    for entry in existing_manifest:
        if not isinstance(entry, dict):
            continue

        slug = (entry.get("slug") or "").strip()
        if not slug:
            continue

        source_pdf = (entry.get("source_pdf") or "").strip().replace("\\", "/")

        if source_mode == "car_data" and source_pdf.startswith("car data/"):
            managed_existing_by_source[source_pdf] = entry
            continue

        legacy_name = entry.get("name", slug)
        legacy_brand = infer_brand_from_guide_name(legacy_name, entry.get("brand"))
        entry = dict(entry)
        entry["brand"] = legacy_brand

        if guide_is_indexed(slug):
            kept_existing.append(entry)

    manifest: List[dict] = []
    used_slugs = set()

    for entry in kept_existing:
        slug = entry.get("slug")
        if slug and slug not in used_slugs:
            used_slugs.add(slug)
            manifest.append(entry)

    summary = {
        "timestamp": now_iso(),
        "source_mode": source_mode,
        "discovered_total": len(discovered),
        "indexed_new": [],
        "reindexed": [],
        "skipped_unchanged": [],
        "failed": [],
        "removed_failed": [],
        "removed_missing": [],
        "kept_without_source": [],
        "chat_added": [],
        "chat_already_available": [],
        "chat_removed": [],
        "manifest_total": 0,
    }

    processed_sources = set()

    discovered_sorted = sorted(
        discovered,
        key=lambda d: (d["brand"].lower(), d["guide_name"].lower(), d["source_pdf"].lower()),
    )

    for item in discovered_sorted:
        pdf_path = Path(item["pdf_path"])
        source_pdf = item["source_pdf"]
        guide_name = item["guide_name"]
        brand = infer_brand_from_guide_name(guide_name, item.get("brand"))
        processed_sources.add(source_pdf)

        if not pdf_path.exists():
            continue

        source_hash = compute_sha256(pdf_path)
        image = find_matching_image(guide_name, brand)

        existing = managed_existing_by_source.get(source_pdf)
        existing_slug = (existing or {}).get("slug")
        existing_hash = (existing or {}).get("source_hash")

        if existing_slug and existing_slug in used_slugs:
            existing_slug = None

        if existing_slug:
            slug = existing_slug
            used_slugs.add(slug)
        else:
            slug = _reserve_slug(slugify(guide_name), used_slugs)

        unchanged = (
            (not args.force)
            and existing is not None
            and bool(existing_hash)
            and existing_hash == source_hash
            and guide_is_indexed(slug)
        )

        if unchanged:
            kept_entry = dict(existing)
            kept_entry.update({
                "slug": slug,
                "name": guide_name,
                "brand": brand,
                "image": image,
                "source_pdf": source_pdf,
                "source_hash": source_hash,
            })
            manifest.append(kept_entry)

            item_summary = _summary_item(slug, guide_name, brand, source_pdf)
            summary["skipped_unchanged"].append(item_summary)
            summary["chat_already_available"].append(item_summary)
            print(f"SKIP unchanged: [{brand}] {guide_name}")
            continue

        try:
            result = index_single_manual(
                pdf_path=pdf_path,
                guide_name=guide_name,
                image_filename=image,
                brand=brand,
                slug=slug,
                source_pdf=source_pdf,
                source_hash=source_hash,
                allow_ocr=not args.no_ocr,
                ocr_lang=args.ocr_lang,
                ocr_max_pages=args.ocr_max_pages,
            )
        except Exception as exc:
            traceback.print_exc()
            result = {
                "ok": False,
                "reason": f"exception:{exc}",
                "slug": slug,
                "name": guide_name,
                "brand": brand,
                "source_pdf": source_pdf,
            }

        if result["ok"]:
            entry = result["entry"]
            manifest.append(entry)

            item_summary = _summary_item(slug, guide_name, brand, source_pdf)
            if existing is None:
                summary["indexed_new"].append(item_summary)
            else:
                summary["reindexed"].append(item_summary)
            summary["chat_added"].append(item_summary)
        else:
            reason = result.get("reason", "indexing_failed")
            fail_item = _summary_item(slug, guide_name, brand, source_pdf, reason)
            summary["failed"].append(fail_item)

            removed = False
            if delete_guide_data(slug):
                removed = True

            if existing and existing.get("slug") and existing.get("slug") != slug:
                if delete_guide_data(existing.get("slug")):
                    removed = True

            if removed:
                removed_item = _summary_item(slug, guide_name, brand, source_pdf, reason)
                summary["removed_failed"].append(removed_item)
                summary["chat_removed"].append(removed_item)

    if source_mode == "car_data":
        for source_pdf, entry in managed_existing_by_source.items():
            if source_pdf in processed_sources:
                continue

            slug = entry.get("slug")
            name = entry.get("name", slug)
            brand = normalize_brand(entry.get("brand"))
            if args.prune_missing_sources:
                removed = False
                if slug:
                    removed = delete_guide_data(slug)

                removed_item = _summary_item(
                    slug=slug or "",
                    name=name,
                    brand=brand,
                    source_pdf=source_pdf,
                    reason="source_pdf_missing",
                )
                if removed:
                    summary["removed_missing"].append(removed_item)
                    summary["chat_removed"].append(removed_item)
                continue

            if not slug:
                continue
            if slug in used_slugs:
                continue
            if not guide_is_indexed(slug):
                continue

            kept_entry = dict(entry)
            kept_entry["brand"] = brand
            manifest.append(kept_entry)
            used_slugs.add(slug)

            kept_item = _summary_item(
                slug=slug,
                name=name,
                brand=brand,
                source_pdf=source_pdf,
                reason="source_pdf_missing_but_kept",
            )
            summary["kept_without_source"].append(kept_item)
            summary["chat_already_available"].append(_summary_item(slug, name, brand, source_pdf))

    manifest.sort(key=lambda g: (str(g.get("brand", "")).lower(), str(g.get("name", "")).lower()))

    manifest_path = GUIDES_DIR / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    summary["manifest_total"] = len(manifest)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    _print_group("Indexed (new)", summary["indexed_new"])
    _print_group("Re-indexed (changed)", summary["reindexed"])
    _print_group("Skipped (unchanged)", summary["skipped_unchanged"])
    _print_group("Failed (not added)", summary["failed"])
    _print_group("Removed (failed extraction)", summary["removed_failed"])
    _print_group("Removed (missing source)", summary["removed_missing"])
    _print_group("Kept (missing source, no prune)", summary["kept_without_source"])

    print(f"\nChats added/updated: {len(summary['chat_added'])}")
    print(f"Chats already available: {len(summary['chat_already_available'])}")
    print(f"Chats removed: {len(summary['chat_removed'])}")
    print(f"\nManifest total guides: {summary['manifest_total']}")
    print(f"Manifest path: {manifest_path}")

    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"Summary JSON: {summary_path}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
