"""
Index vehicle manuals into FAISS + BM25 for the guide system.
Reads PDFs from the manuel/ folder, processes them,
and stores indexes under backend/data/guides/<slug>/.

Usage:
    cd backend
    python -m index_manuals
"""
import json
import sys
import traceback
from pathlib import Path

# Ensure backend src is importable
sys.path.insert(0, str(Path(__file__).parent))

from src.config import CHUNK_SIZE, CHUNK_OVERLAP
from src.guide_manager import GUIDES_DIR, slugify
from src.vector_store import get_embeddings
from src.text_chunker import split_documents as split_document_chunks, is_junk_page

MANUALS_DIR = Path(__file__).parent.parent / "manuel"
IMAGES_DIR = MANUALS_DIR / "voiture"


def _tokenize(text: str):
    import re
    return re.findall(r"[a-zà-ÿ0-9]{2,}", text.lower())


def extract_pdf(pdf_path: Path):
    """Extract text pages from a PDF."""
    from pypdf import PdfReader
    from langchain_core.documents import Document

    documents = []
    reader = PdfReader(str(pdf_path))

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            documents.append(Document(
                page_content=text,
                metadata={
                    "source_file": pdf_path.name,
                    "page": i + 1,
                    "total_pages": len(reader.pages),
                },
            ))

    documents.sort(key=lambda d: d.metadata.get("page", 0))
    return documents


def index_single_manual(pdf_path: Path, guide_name: str, image_filename: str = None):
    """Process and index a single PDF manual."""
    import importlib.util
    from langchain_community.vectorstores import FAISS
    from rank_bm25 import BM25Okapi
    import pickle

    slug = slugify(guide_name)
    guide_dir = GUIDES_DIR / slug
    vs_dir = guide_dir / "vector_store"
    vs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Indexing: {guide_name}")
    print(f"  PDF: {pdf_path.name}")
    print(f"  Slug: {slug}")
    print(f"  Output: {vs_dir}")
    print(f"{'='*60}")

    # 1. Extract
    print("  [1/4] Extracting pages...")
    documents = extract_pdf(pdf_path)
    print(f"         {len(documents)} pages extracted")

    # 2. Chunk
    print("  [2/4] Smart chunking...")
    chunks = split_document_chunks(
        documents=documents,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    print(f"         {len(chunks)} chunks created")

    if not chunks:
        print("  ERROR: No chunks produced, skipping.")
        return None

    # 3. FAISS index
    if importlib.util.find_spec("faiss") is not None:
        print("  [3/4] Building FAISS index...")
        embeddings = get_embeddings()
        batch_size = 200
        vector_store = None

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            print(f"         Batch {batch_num}/{total_batches}...")

            if vector_store is None:
                vector_store = FAISS.from_documents(documents=batch, embedding=embeddings)
            else:
                vector_store.add_documents(batch)

        vector_store.save_local(str(vs_dir))
        print(f"         FAISS index saved")
    else:
        print("  [3/4] FAISS not available, skipping vector index")

    # 4. BM25 index
    print("  [4/4] Building BM25 index...")
    corpus = [_tokenize(c.page_content) for c in chunks]
    bm25 = BM25Okapi(corpus)

    bm25_path = vs_dir / "bm25_index.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)
    print(f"         BM25 index saved ({len(chunks)} docs)")

    return {
        "slug": slug,
        "name": guide_name,
        "image": image_filename,
    }


def derive_guide_name(pdf_name: str) -> str:
    """Derive a clean guide name from a PDF filename."""
    name = pdf_name.replace(".pdf", "").replace(".PDF", "")
    # Remove 'manuel' prefix
    name = name.replace("manuel ", "").replace("Manuel ", "")
    # Title case
    return name.strip().title()


def find_matching_image(guide_name: str) -> str | None:
    """Find a car image matching the guide name."""
    if not IMAGES_DIR.exists():
        return None

    slug = slugify(guide_name)
    for img in IMAGES_DIR.iterdir():
        if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            img_slug = slugify(img.stem)
            if img_slug == slug or slug in img_slug or img_slug in slug:
                return img.name
    return None


def main():
    print("\n" + "=" * 60)
    print("  Vehicle Manual Indexing")
    print("=" * 60)

    if not MANUALS_DIR.exists():
        print(f"\nERROR: Manuel directory not found: {MANUALS_DIR}")
        print("  Create a 'manuel/' folder at project root with your PDFs.")
        sys.exit(1)

    pdf_files = list({p.resolve(): p for p in (list(MANUALS_DIR.glob("*.pdf")) + list(MANUALS_DIR.glob("*.PDF")))}.values())
    if not pdf_files:
        print(f"\nNo PDF files found in {MANUALS_DIR}")
        sys.exit(1)

    print(f"\nFound {len(pdf_files)} PDF(s):")
    for p in pdf_files:
        print(f"  - {p.name}")

    manifest = []

    for pdf_path in pdf_files:
        try:
            guide_name = derive_guide_name(pdf_path.name)
            image = find_matching_image(guide_name)
            result = index_single_manual(pdf_path, guide_name, image)
            if result:
                manifest.append(result)
        except Exception as e:
            print(f"\n  ERROR indexing {pdf_path.name}: {e}")
            traceback.print_exc()

    # Write manifest
    manifest_path = GUIDES_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  Done! {len(manifest)} guide(s) indexed.")
    print(f"  Manifest: {manifest_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
