"""
Guide-scoped RAG chatbot with hybrid retrieval (FAISS + BM25).
Works with pre-indexed guides instead of user sessions.
Supports multilingual responses (French, English, Korean).
"""
from typing import Optional, List, Tuple, Dict
import pickle
import re
import importlib.util
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from google import genai
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from .config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    TOP_K_RESULTS,
    ENABLE_WEB_ENRICHMENT,
    WEB_MAX_RESULTS,
    WEB_SEARCH_REGION,
)
from .vector_store import get_embeddings
from .guide_manager import guide_manager, Guide

try:
    from duckduckgo_search import DDGS
except Exception:
    DDGS = None


MAX_RESPONSE_CHARS = 900
MAX_RESPONSE_LINES = 14

LANGUAGE_PATTERNS = {
    "ko": re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]"),
    "en": re.compile(
        r"\b(?:what|how|where|when|why|which|can|does|is|are|do|the|"
        r"this|that|my|your|please|help|tell|explain|show)\b",
        re.IGNORECASE,
    ),
}


def detect_language(text: str) -> str:
    """Detect input language: 'fr', 'en', or 'ko'."""
    if LANGUAGE_PATTERNS["ko"].search(text):
        return "ko"
    en_matches = len(LANGUAGE_PATTERNS["en"].findall(text))
    if en_matches >= 2:
        return "en"
    return "fr"


LANG_INSTRUCTIONS = {
    "fr": "Reponds en francais.",
    "en": "Answer in English.",
    "ko": "한국어로 답변하세요.",
}

LANG_OFF_TOPIC = {
    "fr": (
        "Question hors sujet:\n"
        "Je suis specialise pour le vehicule {vehicle}.\n\n"
        "Exemples utiles:\n"
        "- Comment fonctionne le systeme de freinage ?\n"
        "- Quelle est la pression recommandee des pneus ?\n"
        "- Que signifie le voyant moteur ?\n\n"
        "Sources:\n"
        "- Aucune page precise du manuel retrouvee pour cette question (reponse generale)."
    ),
    "en": (
        "Off-topic question:\n"
        "I am specialized for the {vehicle}.\n\n"
        "Useful examples:\n"
        "- How does the braking system work?\n"
        "- What is the recommended tire pressure?\n"
        "- What does the engine warning light mean?\n\n"
        "Sources:\n"
        "- No specific manual page found for this question (general response)."
    ),
    "ko": (
        "주제와 관련 없는 질문:\n"
        "{vehicle} 전문 어시스턴트입니다.\n\n"
        "유용한 질문 예시:\n"
        "- 브레이크 시스템은 어떻게 작동하나요?\n"
        "- 권장 타이어 공기압은 얼마인가요?\n"
        "- 엔진 경고등은 무엇을 의미하나요?\n\n"
        "Sources:\n"
        "- 이 질문에 대한 매뉴얼 페이지를 찾을 수 없습니다 (일반 응답)."
    ),
}

VEHICLE_KEYWORDS = [
    "voiture", "vehicule", "automobile", "car", "vehicle",
    "moteur", "engine", "batterie", "battery", "frein", "brake",
    "pneu", "tire", "tyre", "vidange", "maintenance", "entretien",
    "manuel", "manual", "toyota", "auris", "hybride", "hybrid",
    "voyant", "diagnostic", "direction", "steering", "huile", "oil",
    "climatisation", "air conditioning", "carburant", "fuel",
    "clio", "renault", "demarrage", "demarrer", "start",
    # Korean car terms
    "자동차", "엔진", "브레이크", "타이어", "정비", "경고등",
]

NON_VEHICLE_KEYWORDS = [
    "recette", "cuisine", "gateau", "pizza", "soupe",
    "meteo", "pluie", "neige", "president", "election",
    "football", "basket", "film", "musique", "hopital",
]

LANG_QUESTION_PATTERNS = re.compile(
    r"(?:parle|parler|speak|talk|answer|respond|repondre|reponds)"
    r".*(?:anglais|english|francais|french|coreen|korean|langue|language)"
    r"|(?:anglais|english|francais|french|coreen|korean)"
    r".*(?:parle|speak|talk|answer|respond|repondre|reponds)"
    r"|(?:can you|peux.tu|tu peux|do you).*(?:anglais|english|francais|french|coreen|korean|langue|language)"
    r"|(?:change|switch|changer).*(?:langue|language)",
    re.IGNORECASE,
)

LANG_QUESTION_RESPONSE = {
    "fr": (
        "Oui, je peux repondre en francais, anglais et coreen !\n"
        "Pour changer la langue, utilisez le bouton de selection de langue "
        "en haut a droite du chat.\n\n"
        "Sources:\n"
        "- Aucune page precise du manuel retrouvee pour cette question (reponse generale)."
    ),
    "en": (
        "Yes, I can respond in French, English and Korean!\n"
        "To change the language, use the language selector button "
        "in the top right corner of the chat.\n\n"
        "Sources:\n"
        "- No specific manual page found for this question (general response)."
    ),
    "ko": (
        "네, 프랑스어, 영어, 한국어로 답변할 수 있습니다!\n"
        "언어를 변경하려면 채팅 오른쪽 상단의 언어 선택 버튼을 사용하세요.\n\n"
        "Sources:\n"
        "- 이 질문에 대한 매뉴얼 페이지를 찾을 수 없습니다 (일반 응답)."
    ),
}

# Normalize Korean runtime strings to avoid mojibake on some Windows encodings.
LANG_INSTRUCTIONS["ko"] = "Answer in Korean."

LANG_OFF_TOPIC["ko"] = (
    "관련 없는 질문입니다:\n"
    "{vehicle} 전용 어시스턴트입니다.\n\n"
    "유용한 질문 예시:\n"
    "- 브레이크 시스템은 어떻게 작동하나요?\n"
    "- 권장 타이어 공기압은 얼마인가요?\n"
    "- 엔진 경고등은 무엇을 의미하나요?\n\n"
    "Sources:\n"
    "- 이 질문에 대한 매뉴얼 페이지를 찾을 수 없습니다 (일반 응답)."
)

LANG_QUESTION_RESPONSE["ko"] = (
    "네, 프랑스어, 영어, 한국어로 답변할 수 있습니다.\n"
    "언어를 변경하려면 채팅 오른쪽 상단의 언어 선택 버튼을 사용하세요.\n\n"
    "Sources:\n"
    "- 이 질문에 대한 매뉴얼 페이지를 찾을 수 없습니다 (일반 응답)."
)

for keyword in ("자동차", "엔진", "브레이크", "타이어", "정비", "경고등"):
    if keyword not in VEHICLE_KEYWORDS:
        VEHICLE_KEYWORDS.append(keyword)


VIDEO_LABELS = {
    "fr": "Video YouTube recommandee:",
    "en": "Recommended YouTube video:",
    "ko": "YouTube recommended video:",
}


WEB_CONTEXT_LABELS = {
    "fr": "Contexte web (enrichissement):",
    "en": "Web context (enrichment):",
    "ko": "Web context (enrichment):",
}


WEB_STOPWORDS = {
    "comment", "how", "what", "pourquoi", "quelle", "quelles", "quel", "which",
    "with", "sans", "avec", "the", "and", "for", "sur", "dans", "tutoriel",
    "tutorial", "guide", "manual", "owner", "owners", "remplacer", "replace",
}


YOUTUBE_ID_REGEX = re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([A-Za-z0-9_-]{6,})")


def _extract_youtube_id(url: str) -> str:
    match = YOUTUBE_ID_REGEX.search(url or "")
    if not match:
        return ""
    return match.group(1).strip()


def _canonical_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _youtube_html_search(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """Fallback search from YouTube public results page (no API key)."""
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    req = Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        },
    )

    try:
        with urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", "ignore")
    except Exception:
        return []

    found: List[Dict[str, str]] = []
    seen = set()
    for video_id in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html):
        if video_id in seen:
            continue
        seen.add(video_id)
        found.append(
            {
                "title": f"YouTube: {query}",
                "url": _canonical_youtube_url(video_id),
                "snippet": "",
                "domain": "youtube.com",
                "score": "1",
            }
        )
        if len(found) >= max_results:
            break

    return found


def trim_response(answer: str) -> str:
    """Limit response size while keeping coherent sections."""
    clean = (answer or "").replace("\r\n", "\n").strip()
    if not clean:
        return ""

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

    return trimmed


def clean_model_output(text: str) -> str:
    """Normalize model output into plain text."""
    if not text:
        return ""

    cleaned_lines: List[str] = []
    skip_sources_block = False

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            skip_sources_block = False
            cleaned_lines.append("")
            continue

        line = re.sub(r"^#{1,6}\s*", "", line)
        line = line.replace("**", "").replace("`", "")
        if line.startswith("_") and line.endswith("_") and len(line) > 2:
            line = line[1:-1].strip()

        if re.match(r"(?i)^sources?\s*:", line):
            skip_sources_block = True
            continue
        if skip_sources_block:
            continue

        cleaned_lines.append(line)

    clean_text = "\n".join(cleaned_lines)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
    return clean_text


def _safe_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.replace("www.", "")
    except Exception:
        return ""


def _tokens(text: str) -> List[str]:
    raw = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    return [t for t in raw if t not in WEB_STOPWORDS]


def _relevance_score(query: str, title: str, snippet: str, url: str) -> int:
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return 0
    haystack = f"{title} {snippet} {url}".lower()
    overlap = sum(1 for token in query_tokens if token in haystack)
    return overlap


def web_search_results(query: str, max_results: int = WEB_MAX_RESULTS) -> List[Dict[str, str]]:
    """Fetch lightweight web snippets for enrichment only."""
    if not ENABLE_WEB_ENRICHMENT or DDGS is None:
        return []

    found: List[Dict[str, str]] = []
    seen_urls = set()
    seen_domains = set()

    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max(1, max_results * 3), region=WEB_SEARCH_REGION)
            for item in results:
                title = str(item.get("title", "")).strip()
                url = str(item.get("href", "")).strip()
                snippet = str(item.get("body", "")).strip()
                if not title or not url:
                    continue
                if url in seen_urls:
                    continue

                domain = _safe_domain(url)
                if not domain:
                    continue

                # Keep variety and avoid low-value/social noise in enrichment.
                if any(x in domain for x in ("facebook.com", "instagram.com", "tiktok.com", "pinterest.")):
                    continue

                score = _relevance_score(query, title, snippet, url)
                if score < 2:
                    continue

                # keep at most one result per domain for diversity
                if domain in seen_domains:
                    continue

                seen_urls.add(url)
                seen_domains.add(domain)
                found.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "domain": domain,
                        "score": str(score),
                    }
                )
                if len(found) >= max_results:
                    break
    except Exception:
        return []

    return found


def youtube_video_suggestion(query: str) -> Dict[str, str]:
    """Return one relevant YouTube video. No API key required."""
    if not ENABLE_WEB_ENRICHMENT:
        return {}

    candidates: List[Dict[str, str]] = []
    seen_urls = set()

    if DDGS is not None:
        try:
            search_queries = [
                f"site:youtube.com/watch {query}",
                f"{query} tutorial",
                f"{query} review",
            ]
            with DDGS() as ddgs:
                for search_query in search_queries:
                    results = ddgs.text(search_query, max_results=10, region=WEB_SEARCH_REGION)
                    for item in results:
                        title = str(item.get("title", "")).strip()
                        url = str(item.get("href", "")).strip()
                        snippet = str(item.get("body", "")).strip()
                        if not title or not url:
                            continue
                        video_id = _extract_youtube_id(url)
                        if not video_id:
                            continue
                        canonical_url = _canonical_youtube_url(video_id)
                        if canonical_url in seen_urls:
                            continue
                        seen_urls.add(canonical_url)
                        score = _relevance_score(query, title, snippet, canonical_url)
                        candidates.append(
                            {
                                "title": title,
                                "url": canonical_url,
                                "score": str(score),
                            }
                        )
        except Exception:
            pass

    if not candidates:
        fallback_results = _youtube_html_search(query, max_results=8)
        for item in fallback_results:
            canonical_url = item.get("url", "")
            if not canonical_url or canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)
            title = item.get("title", "").strip() or "YouTube"
            score = _relevance_score(query, title, "", canonical_url)
            candidates.append(
                {
                    "title": title,
                    "url": canonical_url,
                    "score": str(score),
                }
            )

    if not candidates:
        return {}

    candidates.sort(key=lambda item: int(item.get("score", "0")), reverse=True)
    best = candidates[0]
    return {"title": best.get("title", "YouTube"), "url": best.get("url", "")}


def format_video_block(video: Dict[str, str], lang: str) -> str:
    label = VIDEO_LABELS.get(lang, VIDEO_LABELS["fr"])
    title = (video or {}).get("title", "").strip() or "YouTube"
    url = (video or {}).get("url", "").strip()
    if not url:
        return ""
    return f"{label}\n- {title}: {url}"


def format_web_context(web_results: List[Dict[str, str]], lang: str) -> str:
    if not web_results:
        return ""
    label = WEB_CONTEXT_LABELS.get(lang, WEB_CONTEXT_LABELS["fr"])
    parts = [label]
    for item in web_results[:WEB_MAX_RESULTS]:
        title = item.get("title", "").strip()
        snippet = item.get("snippet", "").strip()
        domain = item.get("domain", "").strip()
        parts.append(f"[{domain}] {title}\n{snippet}")
    return "\n\n".join(parts)


def format_sources(documents: List[Document], web_results: Optional[List[Dict[str, str]]] = None) -> str:
    """Build a deterministic source block from manual docs + optional web refs."""
    refs: List[str] = []

    seen_manual = set()
    for doc in documents or []:
        source_file = str(doc.metadata.get("source_file", "manuel.pdf"))
        page = doc.metadata.get("page", "?")
        page_label = str(page) if str(page).strip() else "?"
        ref = f"Manual: {source_file}, page {page_label}"
        if ref not in seen_manual:
            seen_manual.add(ref)
            refs.append(ref)

    seen_web = set()
    for item in (web_results or []):
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        domain = str(item.get("domain", "")).strip()
        if not title or not url:
            continue
        ref = f"Web: {title} ({domain}) - {url}"
        if ref not in seen_web:
            seen_web.add(ref)
            refs.append(ref)

    if not refs:
        return (
            "Sources:\n"
            "- Aucune page precise du manuel retrouvee pour cette question (reponse generale)."
        )

    return "Sources:\n" + "\n".join(f"- {ref}" for ref in refs[:8])


def is_vehicle_related(question: str) -> Tuple[bool, float]:
    """Return whether the question is vehicle-related and confidence score.
    
    Permissive: only rejects clearly non-vehicle questions.
    When in doubt, let the RAG pipeline decide relevance.
    """
    text = question.lower()

    negative_matches = sum(1 for kw in NON_VEHICLE_KEYWORDS if kw in text)
    if negative_matches >= 2:
        return False, 0.0

    matches = sum(1 for keyword in VEHICLE_KEYWORDS if keyword in text)
    if matches >= 1:
        return True, 1.0

    # If no strong negative signal, assume it could be vehicle-related
    # and let the RAG retrieval handle relevance
    if negative_matches == 0:
        return True, 0.5

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


class GuideChatbot:
    """RAG chatbot attached to a pre-indexed guide with hybrid retrieval."""

    def __init__(self, guide: Guide):
        self.guide = guide
        self.vector_store = self._load_vector_store()
        self.bm25_index, self.bm25_chunks = self._load_bm25()
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_name = LLM_MODEL.replace("models/", "", 1)
        self.conversation_history: List[dict] = []

    def _load_vector_store(self) -> Optional[FAISS]:
        vs_dir = self.guide.vector_store_dir
        index_path = vs_dir / "index.faiss"
        if not index_path.exists():
            return None

        if importlib.util.find_spec("faiss") is None:
            return None

        embeddings = get_embeddings()
        try:
            return FAISS.load_local(
                str(vs_dir), embeddings, allow_dangerous_deserialization=True
            )
        except ImportError:
            return None

    def _load_bm25(self):
        bm25_path = self.guide.vector_store_dir / "bm25_index.pkl"
        if not bm25_path.exists():
            return None, []
        try:
            with open(bm25_path, "rb") as f:
                data = pickle.load(f)
            return data["bm25"], data["chunks"]
        except Exception:
            return None, []

    def _hybrid_search(self, question: str, k: int = TOP_K_RESULTS) -> List[Document]:
        """Combine FAISS semantic search + BM25 lexical search."""
        seen_contents = set()
        results: List[Tuple[Document, float]] = []

        if self.vector_store:
            faiss_docs = self.vector_store.similarity_search_with_score(question, k=k)
            for doc, score in faiss_docs:
                key = doc.page_content[:200]
                if key not in seen_contents:
                    seen_contents.add(key)
                    results.append((doc, 1.0 / (1.0 + score)))

        if self.bm25_index and self.bm25_chunks:
            tokens = re.findall(r"[a-z0-9]{2,}", question.lower())
            if tokens:
                scores = self.bm25_index.get_scores(tokens)
                top_indices = sorted(
                    range(len(scores)),
                    key=lambda i: scores[i],
                    reverse=True,
                )[:k]
                max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0
                for idx in top_indices:
                    if scores[idx] <= 0:
                        continue
                    doc = self.bm25_chunks[idx]
                    key = doc.page_content[:200]
                    if key not in seen_contents:
                        seen_contents.add(key)
                        results.append((doc, scores[idx] / max_score * 0.8))

        results.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in results[:k]]

    def chat(self, question: str, lang: str = None) -> str:
        """Generate a response. If lang is provided, use it; otherwise auto-detect."""
        if not lang:
            lang = detect_language(question)

        if LANG_QUESTION_PATTERNS.search(question):
            return LANG_QUESTION_RESPONSE.get(lang, LANG_QUESTION_RESPONSE["fr"])

        is_vehicle, confidence = is_vehicle_related(question)

        if not is_vehicle and confidence < 0.5:
            return LANG_OFF_TOPIC.get(lang, LANG_OFF_TOPIC["fr"]).format(
                vehicle=self.guide.name
            )

        docs: List[Document] = []
        context = ""
        if self.vector_store or self.bm25_index:
            docs = self._hybrid_search(question, k=TOP_K_RESULTS)
            context = format_context(docs)

        enrichment_query = f"{self.guide.name} {question}".strip()
        web_results = web_search_results(enrichment_query, max_results=WEB_MAX_RESULTS)
        web_context = format_web_context(web_results, lang=lang)
        video = youtube_video_suggestion(f"{self.guide.name} {question} tutorial")

        sources_block = format_sources(docs, web_results=web_results)
        video_block = format_video_block(video, lang=lang)
        lang_instruction = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["fr"])

        prompt = f"""Tu es un assistant expert pour le vehicule {self.guide.name}.

Regles:
1) {lang_instruction}
2) Base-toi sur le contexte fourni en priorite.
3) Le contexte web est un enrichissement uniquement. En cas de conflit, le manuel prime toujours.
4) Si le contexte est incomplet, complete avec des connaissances automobiles generales fiables.
5) Reponse concise: 80 a 130 mots max.
6) Pas de markdown (pas de ###, **, ```, etc.). Texte brut uniquement.
7) N'ajoute pas de section "Sources" (elle sera ajoutee automatiquement).
8) Orthographe, grammaire et ponctuation impeccables. Utilise des phrases claires et naturelles.

Contexte:
{context}

{web_context}

Question: {question}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            raw_answer = (getattr(response, "text", "") or "").strip()
            clean_answer = clean_model_output(raw_answer)
            answer = trim_response(clean_answer)
            if not answer:
                answer = "Je n'ai pas trouve de reponse exploitable."

            blocks = [answer]
            if video_block:
                blocks.append(video_block)
            blocks.append(sources_block)
            final_answer = "\n\n".join(blocks)

            self.conversation_history.append({"role": "user", "content": question})
            self.conversation_history.append({"role": "assistant", "content": final_answer})
            return final_answer

        except Exception as exc:
            return (
                "Erreur:\n"
                f"Impossible de generer une reponse ({str(exc)}).\n\n"
                "Sources:\n"
                "- Indisponibles (erreur interne)."
            )

    def get_history(self) -> list:
        return self.conversation_history

    def clear_history(self):
        self.conversation_history = []


# Cache chatbots by guide slug + a simple instance id
_guide_chatbot_cache: dict[str, GuideChatbot] = {}


def get_guide_chatbot(slug: str) -> GuideChatbot:
    """Get or create a chatbot for a guide slug."""
    if slug not in _guide_chatbot_cache:
        guide = guide_manager.get_guide(slug)
        if not guide:
            raise ValueError(f"Guide '{slug}' not found")
        if not guide.is_indexed:
            raise ValueError(f"Guide '{slug}' is not indexed yet")
        _guide_chatbot_cache[slug] = GuideChatbot(guide)
    return _guide_chatbot_cache[slug]


def clear_guide_chatbot_cache(slug: str = None):
    if slug:
        _guide_chatbot_cache.pop(slug, None)
    else:
        _guide_chatbot_cache.clear()
