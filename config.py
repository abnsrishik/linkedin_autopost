"""Process-level configuration.

Loads ``.env`` defensively: strips surrounding whitespace and any stray
matching quotes a user may have left in the file, so accidental
``TELEGRAM_BOT_TOKEN="***"`` (double-quoted) and
``TELEGRAM_BOT_TOKEN='701:abc'`` work the same as no-quotes.

Numeric env vars are parsed with ``int(...)`` defaults that fall back
gracefully on garbage values.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "data" / "state.db"
LOG_PATH = BASE_DIR / "logs" / "autoposter.log"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _env(key: str, default: str | None = None) -> str | None:
    """Read an env var and normalize it.

    * Strip surrounding whitespace.
    * Strip a single matching pair of surrounding quotes.
    * Treat empty string as missing.
    """
    value = os.getenv(key, default)
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    return value if value else None


def _env_int(key: str, default: int) -> int:
    raw = _env(key, "")
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
_telegram_user_id_raw = _env("TELEGRAM_USER_ID", "0") or "0"
try:
    TELEGRAM_USER_ID = int(_telegram_user_id_raw)
except ValueError:
    TELEGRAM_USER_ID = 0

GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL") or "openai/gpt-oss-120b"

LINKEDIN_CLIENT_ID = _env("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = _env("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = _env("LINKEDIN_REDIRECT_URI") or "http://localhost:8080/callback"
LINKEDIN_VERSION = _env("LINKEDIN_VERSION") or "202604"

# ---- Web Search (optional add-on) ----
# Provider is selected via SEARCH_PROVIDER=tavily|serp. Both providers are
# optional — bot runs fine without them, but /trending and /news commands
# will refuse until a valid key is configured.
SEARCH_PROVIDER = (_env("SEARCH_PROVIDER") or "tavily").lower()
TAVILY_API_KEY = _env("TAVILY_API_KEY")
SERP_API_KEY = _env("SERP_API_KEY")
# How long cached trending/news articles stay fresh before we re-query.
SEARCH_CACHE_TTL_SECONDS = _env_int("SEARCH_CACHE_TTL_SECONDS", 1800)  # 30 min
# Default number of items returned by /trending and /news.
SEARCH_DEFAULT_NUM = _env_int("SEARCH_DEFAULT_NUM", 8)


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

    if SEARCH_PROVIDER not in ("tavily", "serp"):
        raise RuntimeError(
            f"SEARCH_PROVIDER must be 'tavily' or 'serp' (got {SEARCH_PROVIDER!r})"
        )


def search_provider_configured():
    """True when the configured search provider has an API key set."""
    if SEARCH_PROVIDER == "tavily":
        return bool(TAVILY_API_KEY)
    if SEARCH_PROVIDER == "serp":
        return bool(SERP_API_KEY)
    return False
