"""
PDF processor for a user session.
Handles extraction, chunking and vector indexing.
Optimised pipeline: parallel extraction, junk filtering,
section-aware chunking, batched embeddings, BM25 index.
"""
import json
import traceback
import threading
import importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from .config import CHUNK_SIZE, CHUNK_OVERLAP
from .vector_store import get_embeddings
from .text_chunker import split_documents as split_document_chunks, is_junk_page
from .session_manager import session_manager, SessionStatus


# ── BM25 helpers ──────────────────────────────────────────────
def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercased tokenizer for BM25."""
    import re
    return re.findall(r"[a-zà-ÿ0-9]{2,}", text.lower())


def _build_and_save_bm25(chunks: List[Document], save_dir: Path):
    """Build a BM25 index from chunks and persist it alongside FAISS."""
    from rank_bm25 import BM25Okapi
    import pickle

    corpus = [_tokenize(c.page_content) for c in chunks]
    bm25 = BM25Okapi(corpus)

    bm25_path = save_dir / "bm25_index.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)

    print(f"BM25 index saved to {bm25_path} ({len(chunks)} docs)")


# ── PDF Processor ─────────────────────────────────────────────
class PDFProcessor:
    """PDF processor for a single session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)

        if not self.session:
            raise ValueError(f"Session {session_id} introuvable")

    def process_pdfs_async(self):
        """Start processing in a background thread."""
        thread = threading.Thread(target=self._process_pdfs)
        thread.daemon = True
        thread.start()

    def _process_pdfs(self):
        """Process all PDFs of the session."""
        try:
            session_manager.update_progress(
                self.session_id,
                status=SessionStatus.PROCESSING,
                progress=5,
                message="Demarrage du traitement...",
                current_step="initialization",
            )

            # 1. List PDFs
            pdf_files = list(self.session.pdf_dir.glob("*.pdf"))
            if not pdf_files:
                raise ValueError("Aucun fichier PDF trouve")

            session_manager.update_progress(
                self.session_id,
                progress=10,
                message=f"{len(pdf_files)} PDF(s) trouve(s)",
                current_step="listing",
            )

            # 2. Extract text (parallel pages)
            all_documents: List[Document] = []
            total_pages = 0

            for pdf_path in pdf_files:
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(str(pdf_path))
                    total_pages += len(reader.pages)
                except Exception:
                    pass

            session_manager.update_progress(
                self.session_id,
                total_pages=total_pages,
                message=f"Extraction de {total_pages} pages...",
            )

            processed_pages = 0
            for pdf_path in pdf_files:
                docs = self._extract_pdf(pdf_path, processed_pages, total_pages)
                all_documents.extend(docs)
                processed_pages += len(docs)

            if not all_documents:
                raise ValueError("Aucun texte extrait des PDFs")

            session_manager.update_progress(
                self.session_id,
                progress=50,
                message=f"{len(all_documents)} pages extraites",
                current_step="extraction_complete",
                processed_pages=processed_pages,
            )

            # 3. Smart chunk (section-aware + junk filtering)
            session_manager.update_progress(
                self.session_id,
                progress=55,
                message="Decoupage intelligent...",
                current_step="chunking",
            )

            chunks = self._chunk_documents(all_documents)

            session_manager.update_progress(
                self.session_id,
                progress=65,
                message=f"{len(chunks)} segments utiles",
                current_step="chunking_complete",
            )

            # 4. Create FAISS vector store (batched embeddings)
            session_manager.update_progress(
                self.session_id,
                progress=70,
                message="Indexation vectorielle...",
                current_step="indexing",
            )

            self._create_vector_store(chunks)

            # 5. Build BM25 lexical index
            session_manager.update_progress(
                self.session_id,
                progress=92,
                message="Index lexical BM25...",
                current_step="bm25",
            )

            _build_and_save_bm25(chunks, self.session.vector_store_dir)

            # 6. Done
            session_manager.update_progress(
                self.session_id,
                status=SessionStatus.READY,
                progress=100,
                message="Chatbot pret !",
                current_step="complete",
            )

            print(f"Session {self.session_id} processed: {len(chunks)} chunks")

        except Exception as e:
            print(f"ERROR processing session {self.session_id}: {e}")
            traceback.print_exc()
            session_manager.update_progress(
                self.session_id,
                status=SessionStatus.ERROR,
                progress=0,
                message="Erreur lors du traitement",
                error=str(e),
            )

    # ── Extraction ────────────────────────────────────────────
    def _extract_pdf(
        self, pdf_path: Path, processed_so_far: int, total_pages: int
    ) -> List[Document]:
        """Extract text from a single PDF using parallel page extraction."""
        from pypdf import PdfReader

        documents: List[Document] = []

        try:
            reader = PdfReader(str(pdf_path))
            num_pages = len(reader.pages)

            def extract_page(page_index):
                text = reader.pages[page_index].extract_text()
                if text and text.strip():
                    return Document(
                        page_content=text,
                        metadata={
                            "source_file": pdf_path.name,
                            "page": page_index + 1,
                            "total_pages": num_pages,
                        },
                    )
                return None

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(extract_page, i): i
                    for i in range(num_pages)
                }
                for future in as_completed(futures):
                    page_idx = futures[future]
                    try:
                        doc = future.result()
                        if doc:
                            documents.append(doc)
                    except Exception:
                        pass

                    current_processed = processed_so_far + page_idx + 1
                    progress = 10 + int((current_processed / max(total_pages, 1)) * 40)
                    session_manager.update_progress(
                        self.session_id,
                        progress=progress,
                        processed_pages=current_processed,
                        message=f"Extraction: {current_processed}/{total_pages} pages",
                    )

            # Sort by page number to maintain order
            documents.sort(key=lambda d: d.metadata.get("page", 0))

        except Exception as e:
            print(f"Warning: error reading {pdf_path.name}: {e}")

        return documents

    # ── Chunking ──────────────────────────────────────────────
    def _chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into smart section-aware chunks."""
        return split_document_chunks(
            documents=documents,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

    # ── Vector store ──────────────────────────────────────────
    def _create_vector_store(self, chunks: List[Document]):
        """Create FAISS vector store with batched embeddings."""
        if importlib.util.find_spec("faiss") is None:
            session_manager.update_progress(
                self.session_id,
                progress=91,
                message="FAISS indisponible, index lexical BM25 uniquement",
                current_step="indexing_skipped",
            )
            print("Warning: FAISS not available in this Python environment. Continuing with BM25 only.")
            return None

        embeddings = get_embeddings()

        batch_size = 200
        total_batches = (len(chunks) + batch_size - 1) // batch_size

        vector_store = None

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_num = i // batch_size + 1

            progress = 70 + int((batch_num / total_batches) * 22)
            session_manager.update_progress(
                self.session_id,
                progress=min(progress, 91),
                message=f"Indexation: lot {batch_num}/{total_batches}",
            )

            if vector_store is None:
                try:
                    vector_store = FAISS.from_documents(
                        documents=batch,
                        embedding=embeddings,
                    )
                except ImportError as exc:
                    if "faiss" in str(exc).lower():
                        session_manager.update_progress(
                            self.session_id,
                            progress=91,
                            message="FAISS indisponible, index lexical BM25 uniquement",
                            current_step="indexing_skipped",
                        )
                        print(f"Warning: {exc}")
                        return None
                    raise
            else:
                vector_store.add_documents(batch)

        # Save to disk
        if vector_store is not None:
            vector_store.save_local(str(self.session.vector_store_dir))

        return vector_store


def process_session_pdfs(session_id: str):
    """Utility function to launch processing."""
    processor = PDFProcessor(session_id)
    processor.process_pdfs_async()

