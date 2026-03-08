"""
Configuration du projet Auris Chatbot
"""
import os
from pathlib import Path
from dotenv import load_dotenv

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
    raise ValueError(
        "GOOGLE_API_KEY non configuree. "
        "Creez un fichier .env avec votre cle API Google."
    )

# Configuration du modÃ¨le
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
)

# Configuration du chunking
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300

# Configuration du RAG
TOP_K_RESULTS = 5

