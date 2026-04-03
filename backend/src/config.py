"""
Configuration du projet Auris Chatbot
"""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

log = logging.getLogger("auris")

# Charger les variables d'environnement
load_dotenv()

# Chemins du projet
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"

# Creer les repertoires s'ils n'existent pas
PDF_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

# Configuration API Google
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    log.warning(
        "GOOGLE_API_KEY non configuree. "
        "Le chatbot ne fonctionnera pas sans cle API Google."
    )

# Configuration du modèle
def _normalize_model_name(raw_value, default_value, aliases=None):
    value = (raw_value or default_value).strip()
    if aliases and value in aliases:
        value = aliases[value]
    elif not value.startswith("models/"):
        value = f"models/{value}"
    return value


EMBEDDING_MODEL = _normalize_model_name(
    raw_value=os.getenv("EMBEDDING_MODEL"),
    default_value="models/gemini-embedding-001",
    aliases={
        "embedding-001": "models/gemini-embedding-001",
        "models/embedding-001": "models/gemini-embedding-001",
        "gemini-embedding-001": "models/gemini-embedding-001",
    },
)

LLM_MODEL = _normalize_model_name(
    raw_value=os.getenv("LLM_MODEL"),
    default_value="models/gemini-2.5-flash",
    aliases={
        "gemini-2.0-flash": "models/gemini-2.5-flash",
        "models/gemini-2.0-flash": "models/gemini-2.5-flash",
    },
)

# Configuration du chunking
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

# Configuration du RAG
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "5"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "45"))


def _as_bool(raw_value: str, default: bool = True) -> bool:
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


# Web enrichment (supplemental only, manual remains primary source)
ENABLE_WEB_ENRICHMENT = _as_bool(os.getenv("ENABLE_WEB_ENRICHMENT"), default=True)
ENABLE_DEEP_WEB_ENRICHMENT = _as_bool(
    os.getenv("ENABLE_DEEP_WEB_ENRICHMENT"), default=True
)
ENRICHMENT_TIME_BUDGET_SECONDS = float(
    os.getenv("ENRICHMENT_TIME_BUDGET_SECONDS", "3")
)
WEB_MAX_RESULTS = int(os.getenv("WEB_MAX_RESULTS", "3"))
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "wt-wt")

# Rate limiting & validation
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "3000"))
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))
MAX_CACHED_GUIDES = int(os.getenv("MAX_CACHED_GUIDES", "5"))

# RAG quality
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.15"))

# CORS
_DEFAULT_ORIGINS = [
    "https://carchat.online",
    "https://www.carchat.online",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://localhost:5002",
    "http://127.0.0.1:5002",
]

_raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", ",".join(_DEFAULT_ORIGINS))
if _raw_allowed_origins.strip() == "*":
    ALLOWED_ORIGINS = "*"
else:
    ALLOWED_ORIGINS = []
    for origin in _raw_allowed_origins.split(","):
        clean = origin.strip()
        if clean and clean not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(clean)

