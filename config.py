import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "data" / "state.db"
LOG_PATH = BASE_DIR / "logs" / "autoposter.log"

# Ensure runtime directories exist
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
try:
    TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
except ValueError:
    TELEGRAM_USER_ID = 0

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8080/callback")
LINKEDIN_VERSION = os.getenv("LINKEDIN_VERSION", "202604")

TREND_SEARCH_QUERY = os.getenv(
    "TREND_SEARCH_QUERY",
    "AI OR artificial intelligence student learning tools careers technology",
)


def validate_config():
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_USER_ID:
        missing.append("TELEGRAM_USER_ID")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not LINKEDIN_CLIENT_ID:
        missing.append("LINKEDIN_CLIENT_ID")
    if not LINKEDIN_CLIENT_SECRET:
        missing.append("LINKEDIN_CLIENT_SECRET")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
