"""
Session-scoped RAG chatbot with hybrid retrieval (FAISS + BM25).
"""
from typing import Optional, List, Tuple
import pickle
import re

import google.generativeai as genai
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from .config import GOOGLE_API_KEY, LLM_MODEL, TOP_K_RESULTS
from .vector_store import get_embeddings
from .session_manager import session_manager


genai.configure(api_key=GOOGLE_API_KEY)

VEHICLE_KEYWORDS = [
    "voiture", "vehicule", "automobile", "car", "vehicle",
    "moteur", "engine", "batterie", "battery", "frein", "brake",
    "pneu", "tire", "tyre", "vidange", "maintenance", "entretien",
    "manuel", "manual", "toyota", "auris", "hybride", "hybrid",
    "voyant", "diagnostic", "direction", "steering", "huile", "oil",
    "climatisation", "air conditioning", "carburant", "fuel",
]

NON_VEHICLE_KEYWORDS = [
    "recette", "cuisine", "gateau", "pizza", "soupe",
    "meteo", "pluie", "neige", "president", "election",
    "football", "basket", "film", "musique", "hopital",
    "chien", "chat",
]

MAX_RESPONSE_CHARS = 900
MAX_RESPONSE_LINES = 14


def trim_response(answer: str) -> str:
    """Limit response size while keeping coherent sections."""
    clean = (answer or "").replace("\r\n", "\n").strip()
    if not clean:
        return "Je n'ai pas trouve de reponse exploitable."

    if len(clean) <= MAX_RESPONSE_CHARS and clean.count("\n") <= MAX_RESPONSE_LINES:
        return clean

    sentences = re.split(r"(?<=[.!?])\s+", clean)
    kept = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        projected = current_length + len(sentence) + 1
        if projected > MAX_RESPONSE_CHARS:
            break

        kept.append(sentence)
        current_length = projected

    if kept:
        trimmed = " ".join(kept).strip()
    else:
        trimmed = clean[:MAX_RESPONSE_CHARS].rsplit(" ", 1)[0].strip()

    lines = trimmed.split("\n")
    if len(lines) > MAX_RESPONSE_LINES:
        trimmed = "\n".join(lines[:MAX_RESPONSE_LINES]).strip()

    return f"{trimmed}\n\n_Resume pour garder une reponse courte._"


def is_vehicle_related(question: str) -> Tuple[bool, float]:
    """Return whether the question is vehicle-related and confidence score."""
    text = question.lower()

    for negative in NON_VEHICLE_KEYWORDS:
        if negative in text:
            return False, 0.0

    matches = sum(1 for keyword in VEHICLE_KEYWORDS if keyword in text)

    if matches >= 2:
        return True, 1.0
    if matches == 1:
        return True, 0.7
    return False, 0.0


def format_context(documents: List[Document]) -> str:
    """Format retrieved docs for prompt context."""
    if not documents:
        return "Aucune information specifique trouvee dans les documents."

    parts = []
    for doc in documents:
        source = doc.metadata.get("source_file", "Document")
        page = doc.metadata.get("page", "?")
        parts.append(f"[Source: {source}, Page {page}]\n{doc.page_content}")

    return "\n\n---\n\n".join(parts)


class SessionChatbot:
    """RAG chatbot attached to one user session with hybrid retrieval."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session = session_manager.get_session(session_id)
        if not self.session:
            raise ValueError(f"Session {session_id} introuvable")

        self.vector_store = self._load_vector_store()
        self.bm25_index, self.bm25_chunks = self._load_bm25()
        self.model = genai.GenerativeModel(LLM_MODEL)
        self.conversation_history = []

    def _load_vector_store(self) -> Optional[FAISS]:
        vs_dir = self.session.vector_store_dir
        index_path = vs_dir / "index.faiss"

        if not index_path.exists():
            return None

        embeddings = get_embeddings()
        return FAISS.load_local(
            str(vs_dir), embeddings, allow_dangerous_deserialization=True
        )

    def _load_bm25(self):
        """Load the BM25 index if available."""
        bm25_path = self.session.vector_store_dir / "bm25_index.pkl"
        if not bm25_path.exists():
            return None, []
        try:
            with open(bm25_path, "rb") as f:
                data = pickle.load(f)
            return data["bm25"], data["chunks"]
        except Exception as e:
            print(f"Warning: could not load BM25 index: {e}")
            return None, []

    def _hybrid_search(self, question: str, k: int = TOP_K_RESULTS) -> List[Document]:
        """Combine FAISS vector search + BM25 lexical search."""
        seen_contents = set()
        results: List[Tuple[Document, float]] = []

        # FAISS semantic search
        if self.vector_store:
            faiss_docs = self.vector_store.similarity_search_with_score(question, k=k)
            for doc, score in faiss_docs:
                key = doc.page_content[:200]
                if key not in seen_contents:
                    seen_contents.add(key)
                    # FAISS returns L2 distance — lower is better; normalise to 0-1 score
                    results.append((doc, 1.0 / (1.0 + score)))

        # BM25 lexical search
        if self.bm25_index and self.bm25_chunks:
            tokens = re.findall(r"[a-zà-ÿ0-9]{2,}", question.lower())
            if tokens:
                scores = self.bm25_index.get_scores(tokens)
                top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
                for idx in top_indices:
                    if scores[idx] <= 0:
                        continue
                    doc = self.bm25_chunks[idx]
                    key = doc.page_content[:200]
                    if key not in seen_contents:
                        seen_contents.add(key)
                        # Normalise BM25 score
                        max_score = max(scores) if max(scores) > 0 else 1.0
                        results.append((doc, scores[idx] / max_score * 0.8))

        # Sort by score descending, return top k
        results.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in results[:k]]

    def chat(self, question: str) -> str:
        """Generate a concise structured response for a user question."""
        is_vehicle, confidence = is_vehicle_related(question)

        if not is_vehicle and confidence < 0.5:
            return (
                "### Question hors sujet\n"
                f"Je suis specialise pour **{self.session.vehicle_name}**.\n\n"
                "### Exemples utiles\n"
                "- Comment fonctionne le systeme de freinage ?\n"
                "- Quelle est la pression recommandee des pneus ?\n"
                "- Que signifie le voyant moteur ?"
            )

        context = ""
        if self.vector_store or self.bm25_index:
            docs = self._hybrid_search(question, k=TOP_K_RESULTS)
            context = format_context(docs)

        prompt = f"""Tu es un assistant expert pour le vehicule {self.session.vehicle_name}.

Regles:
1) Reponds en francais.
2) Base-toi sur le contexte si possible.
3) Si le contexte est incomplet, utilise des connaissances auto generales.
4) Reponse courte: 80 a 130 mots max.
5) Format markdown obligatoire:
### Reponse rapide
- 2 ou 3 points max
### Etapes conseillees
- 2 ou 3 actions max
### Source
- 1 ligne
6) Evite les longs paragraphes.

Contexte:
{context}

Question: {question}
"""

        try:
            response = self.model.generate_content(prompt)
            raw_answer = (getattr(response, "text", "") or "").strip()
            answer = trim_response(raw_answer)

            self.conversation_history.append({"role": "user", "content": question})
            self.conversation_history.append({"role": "assistant", "content": answer})

            return answer
        except Exception as exc:
            return f"### Erreur\nImpossible de generer une reponse ({str(exc)})."

    def get_history(self) -> list:
        return self.conversation_history

    def clear_history(self):
        self.conversation_history = []


_chatbot_cache = {}


def get_session_chatbot(session_id: str) -> SessionChatbot:
    if session_id not in _chatbot_cache:
        _chatbot_cache[session_id] = SessionChatbot(session_id)
    return _chatbot_cache[session_id]


def clear_chatbot_cache(session_id: str):
    if session_id in _chatbot_cache:
        del _chatbot_cache[session_id]
