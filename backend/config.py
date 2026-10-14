import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
KNOWLEDGE_DIR = DATA_DIR / "clause_library"
POLICY_DIR = DATA_DIR / "policy_references"


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except Exception:
        pass


_load_env()


def get_bool(name, default=False):
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    APP_NAME = "TATA AI Legal Document Intelligence System"
    APP_VERSION = "1.0.0"

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    AI_MODE = os.getenv("AI_MODE", "auto")

    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "legal_intelligence.db"))
    SECRET_KEY = os.getenv("SECRET_KEY", "tata-legal-demo-secret-change-me")
    TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "24"))

    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
    ALLOWED_EXTENSIONS = {ext.strip() for ext in os.getenv(
        "ALLOWED_EXTENSIONS",
        ".pdf,.docx,.doc,.txt,.md,.html,.htm,.xml,.csv,.json,.png,.jpg,.jpeg,.bmp,.tiff,.tif,.gif,.webp",
    ).split(",") if ext.strip()}

    OCR_ENGINE = os.getenv("OCR_ENGINE", "auto")
    EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "tfidf")
    TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "5"))

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@tata.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "tata123")

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()

for d in (UPLOAD_DIR, KNOWLEDGE_DIR, POLICY_DIR):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
