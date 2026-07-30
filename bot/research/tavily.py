from __future__ import annotations

from urllib.parse import urlparse
import logging

from bot.research.models import (
    ResearchArticle,
    TrendingTopic,
)

import requests

from config import (
    TAVILY_API_KEY,
    TAVILY_TIME_RANGE,
    TREND_SEARCH_QUERY,
)

logger = logging.getLogger(__name__)

TRUSTED_DOMAINS = {
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "ai.google",
    "huggingface.co",
    "techcrunch.com",
    "venturebeat.com",
    "theverge.com",
    "technologyreview.com",
    "blogs.nvidia.com",
    "microsoft.com",
    "meta.com",
}



class TavilyProvider:

    def __init__(self):

        self.api_key = TAVILY_API_KEY
        self.time_range = TAVILY_TIME_RANGE
        self.trending_query = TREND_SEARCH_QUERY

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ----------------------------------------------------

    def research(self, topic: str) -> list[ResearchArticle]:
        if not self.api_key:
            return []

        query = f"{topic} latest developments AI"

        payload = {
            "query" : query,
            "topic": "general",
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": True,
            "max_results": 8,
        }

        response = requests.post(
            "https://api.tavily.com/search",
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        logger.info("stage=provider.tavily.research status=response status_code=%s", response.status_code)

        response.raise_for_status()

        data = response.json()

        articles: list[ResearchArticle] = []

        answer = data.get("answer", "")

        seen = set()

        for result in data.get("results", []):

            title = result.get("title", "").strip()

            if not title:
                continue

            key = title.lower()

            if key in seen:
                continue

            seen.add(key)

            url = result.get("url", "")

            domain = urlparse(url).netloc.lower()

            if domain.startswith("www."):
                domain = domain[4:]

            if not any(domain.endswith(d) for d in TRUSTED_DOMAINS):
                continue

            articles.append(
                ResearchArticle(
                    title=title,
                    url=result.get("url", ""),
                    provider="tavily",
                    summary=result.get("content", ""),
                    content=result.get("raw_content")
                    or result.get("content")
                    or "",
                    domain=domain,
                    published=result.get("published_date", ""),
                    answer=answer,
                )
            )

        return articles[:10]

    # ----------------------------------------------------

    def trending_topics(self, limit: int = 3) -> list[TrendingTopic]:
        if not self.api_key:
            return []

        payload = {
            "query": self.trending_query,
            "topic": "news",
            "time_range": self.time_range,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": 20,
        }

        response = requests.post(
            "https://api.tavily.com/search",
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        logger.info("stage=provider.tavily.trending status=response status_code=%s", response.status_code)

        response.raise_for_status()

        results = response.json().get("results", [])

        topics = []

        seen = set()

        for result in results:

            title = result.get("title", "").strip()

            if not title:
                continue

            key = title.lower()

            if key in seen:
                continue

            seen.add(key)

            topics.append(
                TrendingTopic(
                    title=title,
                    url=result.get("url", ""),
                    provider="tavily",
                    published=result.get("published_date", ""),
                )
            )

            if len(topics) >= limit:
                break

        return topics
