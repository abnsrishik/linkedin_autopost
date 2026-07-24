"""Web-search add-on for the LinkedIn autoposter.

Two providers are supported, selected at runtime by SEARCH_PROVIDER:

* ``tavily`` (https://tavily.com) — LLM-tuned search with a real
  ``/news`` endpoint that returns fresh articles with title, url, snippet,
  age, source, and an LLM-ready content blob. Best default for "top best
  news in the world" because results are already curated for AI grounding.

* ``serp`` (SerpAPI / Google SERP) — generic search results; we use the
  ``tbm=nws`` news tab for the news flow.

Both providers are pure HTTP via ``requests`` to avoid adding an SDK to the
project's dependency footprint. No new packages required.

The client exposes a single ``SearchClient`` interface:

* ``fetch_top_news(query=None, num=8, topic=None)`` -> list[NewsItem]
* ``fetch_trending_now(num=8)`` -> list[NewsItem]   (alias of news with a
  fresh-news query)

A ``NewsItem`` is a small dataclass-like dict with: ``title``, ``url``,
``snippet``, ``source``, ``age`` (e.g. ``"3 hours ago"``), ``content``
(Tavily ``raw_content`` when available for grounding), optional ``image``.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from config import (
    SEARCH_PROVIDER,
    SEARCH_DEFAULT_NUM,
    SERP_API_KEY,
    TAVILY_API_KEY,
)


REQUEST_TIMEOUT_SECONDS = 30

# Provider-neutral result shape.
_default_newsitem_keys = (
    "title",
    "url",
    "snippet",
    "source",
    "age",
    "content",
    "image",
)


class SearchClient:
    """Provider-aware facade. Construct via ``get_search_client()``."""

    def __init__(self):
        self.provider = SEARCH_PROVIDER
        self.tavily_key = TAVILY_API_KEY
        self.serp_key = SERP_API_KEY

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        if self.provider == "tavily":
            return bool(self.tavily_key)
        if self.provider == "serp":
            return bool(self.serp_key)
        return False

    def fetch_top_news(
        self,
        query: str | None = None,
        num: int | None = None,
        topic: str | None = None,
        days: int | None = 1,
    ) -> list[dict]:
        """Return ``num`` trending news items.

        Args:
            query: optional search query (e.g. "AI regulation"). When
                ``None``, the provider returns their general top news.
            num: max results; falls back to ``SEARCH_DEFAULT_NUM``.
            topic: Tavily-specific category hint like ``"technology"``,
                ``"business"``, ``"sports"``, ``"entertainment"``,
                ``"health"``, ``"science"``, ``"world"``, ``"politics"``.
                Ignored by Serp.
            days: only return articles newer than this many days.
                Tavily supports ``days`` natively; Serp has no equivalent
                so this is ignored.
        """
        n = num or SEARCH_DEFAULT_NUM
        q = (query or "").strip()

        if not self.is_available():
            raise RuntimeError(
                f"Search provider '{self.provider}' has no API key. "
                "Set TAVILY_API_KEY or SERP_API_KEY in .env to match SEARCH_PROVIDER."
            )

        if self.provider == "tavily":
            return _tavily_news(self.tavily_key, query=q, num=n, topic=topic, days=days)
        if self.provider == "serp":
            return _serp_news(self.serp_key, query=q, num=n)
        raise RuntimeError(f"Unknown SEARCH_PROVIDER: {self.provider}")

    def fetch_trending_now(self, num: int | None = None, topic: str | None = None) -> list[dict]:
        """Convenience wrapper for /trending — fresh news, no specific query."""
        return self.fetch_top_news(query=None, num=num, topic=topic, days=1)

    def fetch_topic_news(
        self,
        topic_text: str,
        num: int | None = None,
    ) -> list[dict]:
        """Search news for a specific topic phrase (used when the user types
        a topic alongside ``/news topic:``)."""
        return self.fetch_top_news(query=topic_text, num=num)


# ----------------------------------------------------------------------
# Tavily provider
# ----------------------------------------------------------------------
TAVILY_NEWS_URL = "https://api.tavily.com/news"


def _tavily_news(api_key: str, query: str, num: int, topic: str | None, days: int | None) -> list[dict]:
    payload: dict[str, Any] = {"api_key": api_key, "max_results": num}
    if query:
        payload["query"] = query
    if topic:
        payload["topic"] = topic
    if days is not None:
        payload["days"] = days

    response = requests.post(TAVILY_NEWS_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise RuntimeError(f"Tavily news error: {response.status_code} - {response.text}")

    data = response.json() or {}
    results = data.get("results", []) or []
    # Tavily returns dicts with at least: title, url, raw_content, content
    # and sometimes: published_date, image_url, source.
    items = []
    for r in results[:num]:
        items.append(
            {
                "title": r.get("title", "").strip(),
                "url": r.get("url", "").strip(),
                "snippet": (r.get("content") or r.get("raw_content") or "")[:500].strip(),
                "source": _extract_domain(r.get("url", "")),
                "age": r.get("published_date") or "",
                "content": (r.get("raw_content") or r.get("content") or "")[:4000],
                "image": r.get("image_url"),
                "score": r.get("score"),
            }
        )
    return items


# ----------------------------------------------------------------------
# SerpAPI (Google SERP with tbm=nws) provider
# ----------------------------------------------------------------------
SERP_NEWS_URL = "https://serpapi.com/search.json"


def _serp_news(api_key: str, query: str, num: int) -> list[dict]:
    params = {
        "api_key": api_key,
        "engine": "google",
        "tbm": "nws",
        "num": num,
    }
    if query:
        params["q"] = query
    response = requests.get(SERP_NEWS_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise RuntimeError(f"SerpAPI error: {response.status_code} - {response.text}")

    data = response.json() or {}
    results = data.get("news_results", []) or []
    items = []
    for r in results[:num]:
        items.append(
            {
                "title": r.get("title", "").strip(),
                "url": r.get("link", "").strip(),
                "snippet": r.get("snippet", "").strip(),
                "source": r.get("source", "").strip(),
                "age": r.get("date", "").strip(),
                "content": "",  # Serp doesn't return full article text
                "image": r.get("thumbnail"),
                "score": None,
            }
        )
    return items


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def summarize_news_for_prompt(items: list[dict], max_items: int = 6) -> str:
    """Render a list of news items as a compact block for LLM grounding.

    Used by the Groq prompt so the generated LinkedIn post can quote real
    facts without hallucinating.
    """
    lines = []
    for idx, item in enumerate(items[:max_items], start=1):
        title = (item.get("title") or "").strip()
        source = (item.get("source") or "").strip()
        age = (item.get("age") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        url = (item.get("url") or "").strip()
        line = f"{idx}. {title}"
        meta_bits = [b for b in (source, age) if b]
        if meta_bits:
            line += f"  [{' • '.join(meta_bits)}]"
        if snippet:
            line += f"\n   {snippet}"
        if url:
            line += f"\n   {url}"
        lines.append(line)
    return "\n".join(lines)


def news_items_to_json(items: list[dict]) -> str:
    """Serialize news items to a JSON string suitable for storing in SQLite."""
    return json.dumps(items, ensure_ascii=False)


def news_items_from_json(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
        return items if isinstance(items, list) else []
    except Exception:
        return []


# ----------------------------------------------------------------------
# Factory + cache helpers
# ----------------------------------------------------------------------
_cached_client: SearchClient | None = None


def get_search_client() -> SearchClient:
    """Module-level singleton. The handler uses this once at startup."""
    global _cached_client
    if _cached_client is None:
        _cached_client = SearchClient()
    return _cached_client


def cache_is_fresh(saved_at: float, ttl_seconds: int) -> bool:
    return (time.time() - saved_at) < ttl_seconds
