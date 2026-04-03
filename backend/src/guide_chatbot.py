"""
Guide-scoped RAG chatbot with hybrid retrieval (FAISS + BM25).
Works with pre-indexed guides instead of user sessions.
Supports multilingual responses (French, English, Korean).
"""
from typing import Optional, List, Tuple, Dict, Iterator, Any
from collections import OrderedDict
import logging
import pickle
import re
import importlib.util
import time
import hashlib
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from google import genai
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from .config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
    TOP_K_RESULTS,
    ENABLE_WEB_ENRICHMENT,
    ENABLE_DEEP_WEB_ENRICHMENT,
    ENRICHMENT_TIME_BUDGET_SECONDS,
    WEB_MAX_RESULTS,
    WEB_SEARCH_REGION,
    RELEVANCE_THRESHOLD,
    MAX_CONVERSATION_HISTORY,
    MAX_CACHED_GUIDES,
)
from .vector_store import get_embeddings
from .guide_manager import guide_manager, Guide

log = logging.getLogger("auris")

try:
    # Preferred package name (duckduckgo-search was renamed to ddgs).
    from ddgs import DDGS  # type: ignore
except Exception:
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except Exception:
        DDGS = None


MAX_RESPONSE_CHARS = 30000
MAX_RESPONSE_LINES = 500

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
    "ko": "\ud55c\uad6d\uc5b4\ub85c \ub2f5\ubcc0\ud558\uc138\uc694.",
}

LANG_OFF_TOPIC = {
    "fr": (
        "Question hors sujet:\n"
        "Je suis specialise pour le vehicule {vehicle}.\n\n"
        "Exemples utiles:\n"
        "- Comment fonctionne le systeme de freinage ?\n"
        "- Quelle est la pression recommandee des pneus ?\n"
        "- Que signifie le voyant moteur ?"
    ),
    "en": (
        "Off-topic question:\n"
        "I am specialized for the {vehicle}.\n\n"
        "Useful examples:\n"
        "- How does the braking system work?\n"
        "- What is the recommended tire pressure?\n"
        "- What does the engine warning light mean?"
    ),
    "ko": (
        "\uc8fc\uc81c\uc640 \uad00\ub828 \uc5c6\ub294 \uc9c8\ubb38\uc785\ub2c8\ub2e4:\n"
        "{vehicle} \uc804\uc6a9 \uc5b4\uc2dc\uc2a4\ud134\ud2b8\uc785\ub2c8\ub2e4.\n\n"
        "\uc720\uc6a9\ud55c \uc9c8\ubb38 \uc608\uc2dc:\n"
        "- \ube0c\ub808\uc774\ud06c \uc2dc\uc2a4\ud15c\uc740 \uc5b4\ub5bb\uac8c \uc791\ub3d9\ud558\ub098\uc694?\n"
        "- \uad8c\uc7a5 \ud0c0\uc774\uc5b4 \uacf5\uae30\uc555\uc740 \uc5bc\ub9c8\uc778\uac00\uc694?\n"
        "- \uc5d4\uc9c4 \uacbd\uace0\ub4f1\uc740 \ubb34\uc5c7\uc744 \uc758\ubbf8\ud558\ub098\uc694?"
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
    "\uc790\ub3d9\ucc28", "\uc5d4\uc9c4", "\ube0c\ub808\uc774\ud06c", "\ud0c0\uc774\uc5b4",
    "\uc815\ube44", "\uacbd\uace0\ub4f1", "\ubc30\ud130\ub9ac", "\uc5f0\ub8cc", "\uc2dc\ub3d9",
]

NON_VEHICLE_KEYWORDS = [
    "recette", "cuisine", "gateau", "pizza", "soupe",
    "meteo", "pluie", "neige", "president", "election",
    "football", "basket", "film", "musique", "hopital",
    # Korean non-vehicle terms
    "\ub808\uc2dc\ud53c", "\uc694\ub9ac", "\ub0a0\uc528", "\ud1b5\ub839", "\uc120\uac70",
    "\ucd95\uad6c", "\ub18d\uad6c", "\uc601\ud654", "\uc74c\uc545", "\ubcd1\uc6d0",
]

LANG_QUESTION_PATTERNS = re.compile(
    r"(?:parle|parler|speak|talk|answer|respond|repondre|reponds)"
    r".*(?:anglais|english|francais|french|coreen|korean|langue|language|"
    r"\ud55c\uad6d\uc5b4|\uc601\uc5b4|\ud504\ub791\uc2a4\uc5b4|\uc5b8\uc5b4)"
    r"|(?:anglais|english|francais|french|coreen|korean|"
    r"\ud55c\uad6d\uc5b4|\uc601\uc5b4|\ud504\ub791\uc2a4\uc5b4|\uc5b8\uc5b4)"
    r".*(?:parle|speak|talk|answer|respond|repondre|reponds)"
    r"|(?:can you|peux.tu|tu peux|do you).*(?:anglais|english|francais|french|coreen|korean|langue|language|"
    r"\ud55c\uad6d\uc5b4|\uc601\uc5b4|\ud504\ub791\uc2a4\uc5b4|\uc5b8\uc5b4)"
    r"|(?:change|switch|changer).*(?:langue|language|\uc5b8\uc5b4)",
    re.IGNORECASE,
)

_KO_LANGUAGE_HINTS = (
    "\ud55c\uad6d\uc5b4", "\uc601\uc5b4", "\ud504\ub791\uc2a4\uc5b4", "\uc5b8\uc5b4",
)
_KO_LANGUAGE_ACTIONS = (
    "\ub9d0\ud574", "\ub9d0\ud558", "\ub9d0\ud560", "\ub300\ub2f5",
    "\uc751\ub2f5", "\ubc14\uafd4", "\ubcc0\uacbd",
)


def is_language_capability_question(question: str) -> bool:
    lower_question = (question or "").lower()
    if LANG_QUESTION_PATTERNS.search(lower_question):
        return True
    has_language_hint = any(token in question for token in _KO_LANGUAGE_HINTS)
    has_action_hint = any(token in question for token in _KO_LANGUAGE_ACTIONS)
    capability_hint = bool(re.search(r"\ud560\s*\uc218|\uac00\ub2a5", question))
    return has_language_hint and (has_action_hint or capability_hint)


LANG_QUESTION_RESPONSE = {
    "fr": (
        "Oui, je peux repondre en francais, anglais et coreen !\n"
        "Pour changer la langue, utilisez le bouton de selection de langue "
        "en haut a droite du chat."
    ),
    "en": (
        "Yes, I can respond in French, English and Korean!\n"
        "To change the language, use the language selector button "
        "in the top right corner of the chat."
    ),
    "ko": (
        "\ub124, \ud504\ub791\uc2a4\uc5b4, \uc601\uc5b4, \ud55c\uad6d\uc5b4\ub85c \ub2f5\ubcc0\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4!\n"
        "\uc5b8\uc5b4\ub97c \ubcc0\uacbd\ud558\ub824\uba74 \ucc44\ud305 \uc624\ub978\ucabd \uc0c1\ub2e8\uc758 \uc5b8\uc5b4 \uc120\ud0dd \ubc84\ud2bc\uc744 \uc0ac\uc6a9\ud558\uc138\uc694."
    ),
}

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

# Fetch YouTube for procedural, technical, and diagnostic questions
_YOUTUBE_ELIGIBLE_PATTERNS = re.compile(
    r"(?i)\b(comment|how|tutoriel|tutorial|etapes?|steps?|procedure|"
    r"remplacer|replace|changer|change|installer|install|reparer|repair|"
    r"fix|demonter|monter|regler|ajuster|vidanger|purger|nettoyer|"
    r"configurer|activer|desactiver|brancher|debrancher|"
    r"fonctionne|works?|marche|signifie|means?|voyant|warning|"
    r"pression|pressure|niveau|level|capacite|capacity|"
    r"entretien|maintenance|diagnostic|reset|reinitialiser|"
    r"connecter|connect|bluetooth|demarrer|start|ouvrir|open)\b"
)

YOUTUBE_MIN_RELEVANCE_SCORE = 4


def _extract_youtube_id(url: str) -> str:
    match = YOUTUBE_ID_REGEX.search(url or "")
    if not match:
        return ""
    return match.group(1).strip()


def _canonical_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _youtube_html_search(
    query: str, max_results: int = 8, timeout_seconds: float = 2.0
) -> List[Dict[str, str]]:
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
        with urlopen(req, timeout=max(1.0, float(timeout_seconds))) as response:
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
    """Strip only LLM-generated Sources blocks and URLs; preserve all formatting."""
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

        if re.match(r"(?i)^sources?\s*:", line):
            skip_sources_block = True
            continue
        if skip_sources_block:
            continue

        # Strip any URLs the LLM may have included (they are added separately)
        line = re.sub(r"https?://[^\s)]+", "", line).strip()
        if not line:
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


def web_search_results(
    query: str,
    max_results: int = WEB_MAX_RESULTS,
    time_budget_seconds: float = ENRICHMENT_TIME_BUDGET_SECONDS,
) -> List[Dict[str, str]]:
    """Fetch lightweight web snippets for enrichment only."""
    if not ENABLE_WEB_ENRICHMENT or DDGS is None:
        return []

    found: List[Dict[str, str]] = []
    seen_urls = set()
    seen_domains = set()
    started_at = time.perf_counter()

    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max(1, max_results * 3), region=WEB_SEARCH_REGION)
            for item in results:
                if (time.perf_counter() - started_at) > max(0.2, time_budget_seconds):
                    break
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
    except Exception as exc:
        log.warning("Web search failed for query '%s': %s", query, exc)
        return []

    return found


def youtube_video_suggestion(
    query: str, time_budget_seconds: float = ENRICHMENT_TIME_BUDGET_SECONDS
) -> Dict[str, str]:
    """Return one relevant YouTube video. No API key required."""
    if not ENABLE_WEB_ENRICHMENT:
        return {}

    candidates: List[Dict[str, str]] = []
    seen_urls = set()

    started_at = time.perf_counter()

    if DDGS is not None and ENABLE_DEEP_WEB_ENRICHMENT:
        try:
            search_queries = [
                f"site:youtube.com/watch {query}",
                f"{query} tutorial",
                f"{query} review",
            ]
            with DDGS() as ddgs:
                for search_query in search_queries:
                    if (time.perf_counter() - started_at) > max(0.2, time_budget_seconds):
                        break
                    results = ddgs.text(search_query, max_results=10, region=WEB_SEARCH_REGION)
                    for item in results:
                        if (time.perf_counter() - started_at) > max(0.2, time_budget_seconds):
                            break
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
        except Exception as exc:
            log.warning("YouTube DDG search failed: %s", exc)

    if not candidates:
        return {}

    candidates.sort(key=lambda item: int(item.get("score", "0")), reverse=True)
    best = candidates[0]
    if int(best.get("score", "0")) < YOUTUBE_MIN_RELEVANCE_SCORE:
        return {}
    return {
        "title": best.get("title", "YouTube"),
        "url": best.get("url", ""),
        "score": best.get("score", "0"),
    }


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
        return ""

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


_enrichment_executor = ThreadPoolExecutor(max_workers=4)


class GuideChatbot:
    """RAG chatbot attached to a pre-indexed guide with hybrid retrieval."""

    def __init__(self, guide: Guide):
        self.guide = guide
        self.vector_stores = self._load_vector_stores()
        self.bm25_indices = self._load_bm25_indices()
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_name = LLM_MODEL.replace("models/", "", 1)
        # Per-session conversation histories with bounded size
        self._session_histories: OrderedDict[str, List[dict]] = OrderedDict()
        self._max_sessions = 1000

    def _load_vector_stores(self) -> List[FAISS]:
        if importlib.util.find_spec("faiss") is None:
            return []

        stores: List[FAISS] = []
        embeddings = get_embeddings()
        for vs_dir in self.guide.vector_store_dirs:
            index_path = vs_dir / "index.faiss"
            if not index_path.exists():
                continue
            try:
                stores.append(
                    FAISS.load_local(
                        str(vs_dir), embeddings, allow_dangerous_deserialization=True
                    )
                )
            except Exception as exc:
                log.warning(
                    "Failed to load FAISS index for %s (%s): %s",
                    self.guide.slug,
                    vs_dir,
                    exc,
                )
        return stores

    def _load_bm25_indices(self) -> List[Tuple[object, List[Document]]]:
        indices: List[Tuple[object, List[Document]]] = []
        for vs_dir in self.guide.vector_store_dirs:
            bm25_path = vs_dir / "bm25_index.pkl"
            if not bm25_path.exists():
                continue
            try:
                with open(bm25_path, "rb") as f:
                    data = pickle.load(f)
                bm25_index = data.get("bm25")
                chunks = data.get("chunks") or []
                if bm25_index and chunks:
                    indices.append((bm25_index, chunks))
            except Exception as exc:
                log.warning(
                    "Failed to load BM25 index for %s (%s): %s",
                    self.guide.slug,
                    vs_dir,
                    exc,
                )
        return indices

    def _get_session_history(self, session_id: str) -> List[dict]:
        if session_id not in self._session_histories:
            # Evict oldest session if at capacity
            while len(self._session_histories) >= self._max_sessions:
                self._session_histories.popitem(last=False)
            self._session_histories[session_id] = []
        else:
            self._session_histories.move_to_end(session_id)
        return self._session_histories[session_id]

    def _trim_session_history(self, session_id: str):
        history = self._session_histories.get(session_id, [])
        if len(history) > MAX_CONVERSATION_HISTORY:
            self._session_histories[session_id] = history[-MAX_CONVERSATION_HISTORY:]

    def _hybrid_search(self, question: str, k: int = TOP_K_RESULTS) -> List[Document]:
        """Combine FAISS + BM25 with Reciprocal Rank Fusion (RRF)."""
        RRF_K = 60  # standard RRF constant

        # --- FAISS retrieval ---
        faiss_ranked: List[Document] = []
        for vector_store in self.vector_stores:
            try:
                faiss_docs = vector_store.similarity_search_with_score(question, k=k * 2)
                faiss_docs.sort(key=lambda x: x[1])  # lower L2 = better
                faiss_ranked.extend(doc for doc, _ in faiss_docs)
            except Exception as exc:
                log.warning("FAISS search failed: %s", exc)

        # --- BM25 retrieval ---
        bm25_ranked: List[Document] = []
        tokens = re.findall(r"[a-z\u00e0-\u00ff0-9\u3130-\u318f\uac00-\ud7af]{2,}", question.lower())
        if tokens:
            for bm25_index, bm25_chunks in self.bm25_indices:
                try:
                    scores = bm25_index.get_scores(tokens)
                except Exception as exc:
                    log.warning("BM25 scoring failed: %s", exc)
                    continue
                top_indices = sorted(
                    range(len(scores)),
                    key=lambda i: scores[i],
                    reverse=True,
                )[:k * 2]
                bm25_ranked.extend(
                    bm25_chunks[idx]
                    for idx in top_indices
                    if scores[idx] > 0
                )

        # --- Reciprocal Rank Fusion ---
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        for rank, doc in enumerate(faiss_ranked):
            key = hashlib.sha256(doc.page_content.encode()).hexdigest()
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(bm25_ranked):
            key = hashlib.sha256(doc.page_content.encode()).hexdigest()
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            doc_map[key] = doc

        # Sort by RRF score descending
        sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)

        # Apply relevance threshold (RRF score for rank 0 in one list = ~0.016)
        min_rrf = RELEVANCE_THRESHOLD * 0.1  # ~0.015 threshold
        filtered = [doc_map[k] for k in sorted_keys if rrf_scores[k] >= min_rrf]

        if not filtered and sorted_keys:
            filtered = [doc_map[sorted_keys[0]]]

        return filtered[:k]

    def _prepare_chat_payload(
        self,
        question: str,
        lang: Optional[str] = None,
        session_id: str = "default",
        skip_video: bool = False,
    ) -> Dict[str, Any]:
        """Build chat payload (prompt + retrieval context) shared by sync and stream paths."""
        if not lang:
            lang = detect_language(question)

        if is_language_capability_question(question):
            return {
                "early_answer": LANG_QUESTION_RESPONSE.get(
                    lang, LANG_QUESTION_RESPONSE["fr"]
                )
            }

        is_vehicle, confidence = is_vehicle_related(question)

        if not is_vehicle and confidence < 0.5:
            return {
                "early_answer": LANG_OFF_TOPIC.get(
                    lang, LANG_OFF_TOPIC["fr"]
                ).format(vehicle=self.guide.name)
            }

        # --- Hybrid retrieval with relevance threshold ---
        docs: List[Document] = []
        context = ""
        has_relevant_context = False
        if self.vector_stores or self.bm25_indices:
            docs = self._hybrid_search(question, k=TOP_K_RESULTS)
            if docs:
                has_relevant_context = True
                context = format_context(docs)

        # --- Web enrichment (parallel) ---
        web_results: List[Dict[str, str]] = []
        video: Dict[str, str] = {}
        web_context = ""

        if ENABLE_WEB_ENRICHMENT:
            enrichment_query = f"{self.guide.name} {question}".strip()
            budget = max(0.5, ENRICHMENT_TIME_BUDGET_SECONDS)

            def _fetch_web():
                return web_search_results(
                    enrichment_query,
                    max_results=WEB_MAX_RESULTS,
                    time_budget_seconds=budget,
                )

            web_future = _enrichment_executor.submit(_fetch_web)

            video_future = None
            if not skip_video:
                def _fetch_video():
                    if not _YOUTUBE_ELIGIBLE_PATTERNS.search(question):
                        return {}
                    return youtube_video_suggestion(
                        f"{self.guide.name} {question}",
                        time_budget_seconds=budget,
                    )
                video_future = _enrichment_executor.submit(_fetch_video)

            try:
                web_results = web_future.result(timeout=budget)
            except Exception:
                web_results = []
            if video_future is not None:
                try:
                    video = video_future.result(timeout=max(1.0, budget))
                except Exception:
                    video = {}

            web_context = format_web_context(web_results, lang=lang)

        sources_block = format_sources(docs, web_results=web_results)
        video_block = format_video_block(video, lang=lang)
        lang_instruction = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["fr"])

        # --- Build conversation context from session history ---
        history = self._get_session_history(session_id)
        history_block = ""
        if history:
            recent = history[-(min(len(history), 6)):]  # last 3 exchanges (6 messages)
            parts = []
            for msg in recent:
                role = "Utilisateur" if msg["role"] == "user" else "Assistant"
                parts.append(f"{role}: {msg['content'][:800]}")
            history_block = "\n".join(parts)

        # --- System instruction (separated from user content for Gemini) ---
        system_instruction = f"""Tu es un assistant technique expert et precis, specialise pour le vehicule {self.guide.name}.

REGLES STRICTES:
1) {lang_instruction}
2) Base-toi UNIQUEMENT sur le contexte fourni (manuel du vehicule et web).
3) JAMAIS d'invention: si une information (valeur technique, procedure, specification) n'est PAS dans le contexte fourni, dis-le clairement. Exemple: "Cette information n'est pas disponible dans le manuel fourni."
4) Ne JAMAIS inventer de valeurs chiffrees (couples de serrage, pressions, capacites, intervalles) qui ne sont pas explicitement dans le contexte.
5) Le contexte web est un complement. En cas de conflit avec le manuel, le manuel prime TOUJOURS.
6) Reponds de facon complete et detaillee. Pour les procedures en etapes, donne TOUTES les etapes. Ne tronque JAMAIS ta reponse.
7) Utilise un formatage clair et structure: listes numerotees pour les etapes, listes a puces pour les points cles, **gras** pour les termes importants. Pas de blocs de code (```).
8) N'ajoute PAS de section "Sources" (elle sera ajoutee automatiquement).
9) Orthographe, grammaire et ponctuation impeccables. Phrases claires et naturelles.
10) Personnalise chaque reponse pour le {self.guide.name}: mentionne le nom du vehicule quand c'est pertinent.
11) Ta reponse doit etre une explication textuelle complete et autonome. Ne mentionne AUCUN lien, URL, ou video dans ta reponse -- ils seront ajoutes automatiquement apres."""

        # --- User content ---
        user_parts = []
        if history_block:
            user_parts.append(f"Historique recent de la conversation:\n{history_block}")
        if context:
            user_parts.append(f"Contexte du manuel du vehicule:\n{context}")
        else:
            user_parts.append("Aucun passage pertinent trouve dans le manuel du vehicule pour cette question.")
        if web_context:
            user_parts.append(f"<web_enrichment>\n{web_context}\n</web_enrichment>")
        user_parts.append(f"Question de l'utilisateur: {question}")

        user_content = "\n\n---\n\n".join(user_parts)
        return {
            "history": history,
            "system_instruction": system_instruction,
            "user_content": user_content,
            "sources_block": sources_block,
            "video_block": video_block,
            "video_score": video.get("score", "0") if video else "0",
        }

    def _finalize_answer(
        self,
        raw_answer: str,
        sources_block: str = "",
        video_block: str = "",
        video_score: Any = 0,
    ) -> Tuple[str, str]:
        clean_answer = clean_model_output((raw_answer or "").strip())
        answer = trim_response(clean_answer)
        if not answer:
            answer = "Je n'ai pas trouve de reponse exploitable dans le manuel."

        try:
            parsed_video_score = int(video_score)
        except (TypeError, ValueError):
            parsed_video_score = 0

        blocks = [answer]
        if sources_block:
            blocks.append(sources_block)
        if video_block and parsed_video_score >= YOUTUBE_MIN_RELEVANCE_SCORE:
            blocks.append(video_block)
        final_answer = "\n\n".join(blocks)
        return answer, final_answer

    @staticmethod
    def _extract_stream_chunk_text(chunk: object) -> str:
        text = getattr(chunk, "text", "")
        if text:
            return text

        pieces: List[str] = []
        candidates = getattr(chunk, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", "")
                if part_text:
                    pieces.append(part_text)
        return "".join(pieces)

    def chat(self, question: str, lang: str = None, session_id: str = "default") -> str:
        """Generate a response. If lang is provided, use it; otherwise auto-detect."""
        payload = self._prepare_chat_payload(
            question=question,
            lang=lang,
            session_id=session_id,
        )
        early_answer = payload.get("early_answer")
        if isinstance(early_answer, str):
            return early_answer

        try:
            from google.genai import types as genai_types
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=str(payload.get("user_content", "")),
                config=genai_types.GenerateContentConfig(
                    system_instruction=str(payload.get("system_instruction", "")),
                    temperature=0.15,
                    max_output_tokens=4096,
                    http_options=genai_types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),
                ),
            )

            raw_answer = (getattr(response, "text", "") or "").strip()
            answer, final_answer = self._finalize_answer(
                raw_answer,
                sources_block=str(payload.get("sources_block", "")),
                video_block=str(payload.get("video_block", "")),
                video_score=payload.get("video_score", 0),
            )

            # Save to session history
            history = payload.get("history")
            if isinstance(history, list):
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})
                self._trim_session_history(session_id)

            return final_answer

        except Exception as exc:
            log.error("LLM generation failed for %s: %s", self.guide.slug, exc)
            return "Impossible de generer une reponse. Veuillez reessayer."

    def chat_stream(
        self,
        question: str,
        lang: str = None,
        session_id: str = "default",
    ) -> Iterator[Dict[str, Any]]:
        """Generate a streaming response, then search YouTube post-stream."""
        message_id = str(uuid.uuid4())

        payload = self._prepare_chat_payload(
            question=question,
            lang=lang,
            session_id=session_id,
            skip_video=True,
        )
        early_answer = payload.get("early_answer")
        if isinstance(early_answer, str):
            yield {"type": "chunk", "text": early_answer, "message_id": message_id}
            yield {"type": "end", "response": early_answer, "message_id": message_id}
            return

        try:
            from google.genai import types as genai_types

            stream = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=str(payload.get("user_content", "")),
                config=genai_types.GenerateContentConfig(
                    system_instruction=str(payload.get("system_instruction", "")),
                    temperature=0.15,
                    max_output_tokens=4096,
                    http_options=genai_types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),
                ),
            )

            raw_chunks: List[str] = []
            for chunk in stream:
                chunk_text = self._extract_stream_chunk_text(chunk)
                if not chunk_text:
                    continue
                raw_chunks.append(chunk_text)
                yield {"type": "chunk", "text": chunk_text, "message_id": message_id}

            raw_answer = "".join(raw_chunks).strip()
            if not raw_answer and not raw_chunks:
                yield {"type": "chunk", "text": "Je n'ai pas trouve de reponse exploitable dans le manuel.", "message_id": message_id}

            # Finalize with sources only (no video in text)
            answer, final_response = self._finalize_answer(
                raw_answer,
                sources_block=str(payload.get("sources_block", "")),
            )

            history = payload.get("history")
            if isinstance(history, list):
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})
                self._trim_session_history(session_id)

            yield {"type": "end", "response": final_response, "message_id": message_id}

        except Exception as exc:
            log.error("LLM streaming failed for %s: %s", self.guide.slug, exc)
            raise

        # --- Post-stream YouTube search (client already has full text) ---
        try:
            if ENABLE_WEB_ENRICHMENT and _YOUTUBE_ELIGIBLE_PATTERNS.search(question):
                video = youtube_video_suggestion(
                    f"{self.guide.name} {question}",
                    time_budget_seconds=max(0.5, ENRICHMENT_TIME_BUDGET_SECONDS),
                )
                if video and int(video.get("score", "0")) >= YOUTUBE_MIN_RELEVANCE_SCORE:
                    video_id = _extract_youtube_id(video.get("url", ""))
                    yield {
                        "type": "video_result",
                        "message_id": message_id,
                        "title": video.get("title", "YouTube"),
                        "url": video.get("url", ""),
                        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
                    }
                    return
            yield {"type": "video_none", "message_id": message_id}
        except Exception as exc:
            log.warning("Post-stream video search failed: %s", exc)
            yield {"type": "video_none", "message_id": message_id}

    def get_history(self, session_id: str = "default") -> list:
        return self._get_session_history(session_id)

    def clear_history(self, session_id: str = None):
        if session_id:
            self._session_histories.pop(session_id, None)
        else:
            self._session_histories.clear()


# LRU cache for chatbot instances (bounded by MAX_CACHED_GUIDES)
_guide_chatbot_cache: OrderedDict[str, GuideChatbot] = OrderedDict()
_cache_lock = threading.Lock()


def get_guide_chatbot(slug: str) -> GuideChatbot:
    """Get or create a chatbot for a vehicle slug with LRU eviction (thread-safe)."""
    with _cache_lock:
        if slug in _guide_chatbot_cache:
            _guide_chatbot_cache.move_to_end(slug)
            return _guide_chatbot_cache[slug]

    guide = guide_manager.get_guide(slug)
    if not guide:
        raise ValueError(f"Guide '{slug}' not found")
    if not guide.is_indexed:
        raise ValueError(f"Guide '{slug}' is not indexed yet")

    cache_key = guide.slug

    chatbot = GuideChatbot(guide)

    with _cache_lock:
        # Check again in case another thread created it
        if cache_key in _guide_chatbot_cache:
            _guide_chatbot_cache.move_to_end(cache_key)
            return _guide_chatbot_cache[cache_key]

        while len(_guide_chatbot_cache) >= MAX_CACHED_GUIDES:
            evicted_slug, _ = _guide_chatbot_cache.popitem(last=False)
            log.info("Evicted chatbot cache for guide: %s", evicted_slug)

        _guide_chatbot_cache[cache_key] = chatbot
        return chatbot


def clear_guide_chatbot_cache(slug: str = None):
    with _cache_lock:
        if slug:
            guide = guide_manager.get_guide(slug)
            cache_key = guide.slug if guide else slug
            _guide_chatbot_cache.pop(cache_key, None)
        else:
            _guide_chatbot_cache.clear()

