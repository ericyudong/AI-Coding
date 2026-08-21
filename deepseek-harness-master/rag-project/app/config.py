"""Application configuration."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
CHROMA_DIR = BASE_DIR / "data" / "chroma_db"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Chunking parameters
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80

# Embedding model (runs locally, no API key needed)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# LLM configuration — uses OpenAI-compatible API
# Set OPENAI_API_KEY and optionally OPENAI_BASE_URL in environment
LLM_MODEL = "deepseek-chat"
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 1024

# Retrieval
TOP_K = 5

# Allowed upload extensions
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".md", ".docx"}
