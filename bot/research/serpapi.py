from __future__ import annotations

from urllib.parse import urlparse
import logging

import requests

from config import SERP_API_KEY

from bot.research.models import (
    ResearchArticle,
    TrendingTopic,
)

logger = logging.getLogger(__name__)


class SerpAPIProvider:
    """
    Google Search / Google News provider using SerpAPI.
    """

    BASE_URL = "https://serpapi.com/search.json"

    TRUSTED_DOMAINS = {
        "openai.com",
        "anthropic.com",
        "deepmind.google",
        "huggingface.co",
        "techcrunch.com",
        "venturebeat.com",
        "theverge.com",
        "wired.com",
        "arstechnica.com",
        "mit.edu",
        "reuters.com",
        "nvidia.com",
        "microsoft.com",
        "meta.com",
    }

    def __init__(self):
        self.api_key = SERP_API_KEY

    # ----------------------------------------------------

    def research(self, topic: str) -> list[ResearchArticle]:
        if not self.api_key:
            return []

        params = {
            "engine": "google_news",
            "q": topic,
            "api_key": self.api_key,
        }

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=30,
        )
        logger.info("stage=provider.serpapi.research status=response status_code=%s", response.status_code)

        if response.status_code != 200:
            raise Exception(
                f"SerpAPI Error {response.status_code}\n"
                f"{response.text}"
            )

        data = response.json()

        articles: list[ResearchArticle] = []

        seen = set()

        for item in data.get("news_results", []):

            title = item.get("title", "").strip()

            if not title:
                continue

            key = title.lower()

            if key in seen:
                continue

            seen.add(key)

            url = item.get("link", "")

            domain = urlparse(url).netloc.lower()

            if domain.startswith("www."):
                domain = domain[4:]

            if domain and domain not in self.TRUSTED_DOMAINS:
                continue

            articles.append(
                ResearchArticle(
                    title=title,
                    url=url,
                    provider="serpapi",
                    summary=item.get("snippet", ""),
                    content="",
                    domain=domain,
                    published=item.get("date", ""),
                )
            )

        return articles[:10]

    # ----------------------------------------------------

    def trending_topics(self, limit: int = 3) -> list[TrendingTopic]:
        if not self.api_key:
            return []

        params = {
            "engine": "google_news",
            "q": "Artificial Intelligence",
            "api_key": self.api_key,
        }

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=30,
        )
        logger.info("stage=provider.serpapi.trending status=response status_code=%s", response.status_code)

        if response.status_code != 200:
            raise Exception(
                f"SerpAPI Error {response.status_code}\n"
                f"{response.text}"
            )

        data = response.json()

        topics = []

        seen = set()

        for item in data.get("news_results", []):

            title = item.get("title", "").strip()

            if not title:
                continue

            key = title.lower()

            if key in seen:
                continue

            seen.add(key)

            topics.append(
                TrendingTopic(
                    title=title,
                    url=item.get("link", ""),
                    provider="serpapi",
                    published=item.get("date", ""),
                )
            )

            if len(topics) >= limit:
                break

        return topics
