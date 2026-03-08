"""
Vector store module using FAISS for the RAG pipeline.
"""
from typing import List, Optional
import importlib.util

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

from .config import VECTOR_STORE_DIR, TOP_K_RESULTS, EMBEDDING_MODEL


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Initialise le modele d'embeddings Google."""
    return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)


def _faiss_available() -> bool:
    return importlib.util.find_spec("faiss") is not None


def create_vector_store(
    documents: List[Document], persist_directory: Optional[str] = None
) -> FAISS:
    """Create a new FAISS vector store from documents and save it."""
    if not documents:
        raise ValueError("Aucun document a indexer")
    if not _faiss_available():
        raise RuntimeError(
            "FAISS indisponible dans cet environnement Python. "
            "Utilisez Python 3.12 + faiss-cpu, ou activez le mode BM25 uniquement."
        )

    embeddings = get_embeddings()
    vector_store = FAISS.from_documents(documents=documents, embedding=embeddings)

    save_dir = persist_directory or str(VECTOR_STORE_DIR)
    vector_store.save_local(save_dir)
    print(f"Vector store created and saved to {save_dir}")
    return vector_store


def load_vector_store(persist_directory: Optional[str] = None) -> Optional[FAISS]:
    """Load an existing FAISS vector store."""
    from pathlib import Path

    if not _faiss_available():
        return None

    save_dir = persist_directory or str(VECTOR_STORE_DIR)
    index_path = Path(save_dir) / "index.faiss"

    if not index_path.exists():
        return None

    embeddings = get_embeddings()
    try:
        vector_store = FAISS.load_local(
            save_dir, embeddings, allow_dangerous_deserialization=True
        )
        return vector_store
    except Exception as e:
        print(f"Error loading vector store: {e}")
        return None


def search_documents(
    query: str,
    vector_store: Optional[FAISS] = None,
    k: int = TOP_K_RESULTS,
) -> List[Document]:
    """Search for the most relevant documents."""
    if vector_store is None:
        vector_store = load_vector_store()
    if vector_store is None:
        return []
    return vector_store.similarity_search(query, k=k)


def delete_vector_store(persist_directory: Optional[str] = None):
    """Delete the vector store."""
    import shutil
    from pathlib import Path

    save_dir = persist_directory or str(VECTOR_STORE_DIR)
    path = Path(save_dir)
    if path.exists():
        shutil.rmtree(path)
        print(f"Vector store deleted: {save_dir}")
