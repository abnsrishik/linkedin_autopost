import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

from config import TAVILY_API_KEY, TAVILY_TIME_RANGE, TREND_SEARCH_QUERY

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
    "microsoft.com",
    "blogs.nvidia.com",
    "meta.com",
}

class TrendClient:
    def __init__(
        self,
        query: str = TREND_SEARCH_QUERY,
        tavily_api_key: str | None = TAVILY_API_KEY,
        time_range: str = TAVILY_TIME_RANGE,
    ):
        self.query = query
        self.tavily_api_key = tavily_api_key
        self.time_range = time_range

    def fetch_topics(self, limit: int = 3, exclude_topics: list[str] | None = None) -> list[str]:
        excluded = {topic.lower() for topic in (exclude_topics or [])}
        if self.tavily_api_key:
            topics = self._fetch_tavily_topics(limit, excluded)
            if len(topics) < limit:
                topics = self._supplement_topics(topics, limit, excluded)
            return topics[:limit]

        topics = self._fetch_google_news_topics(limit, excluded)
        if len(topics) < limit:
            topics = self._supplement_topics(topics, limit, excluded)
        return topics[:limit]

    def _fetch_tavily_topics(self, limit: int, excluded: set[str]) -> list[str]:
        payload = {
            "query": self.query,
            "topic": "news",
            "time_range": self.time_range,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": True,
            "max_results": 20,
        }
        headers = {
            "Authorization": f"Bearer {self.tavily_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post("https://api.tavily.com/search", headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Tavily trend search failed: {response.status_code} - {response.text}")

        results = response.json().get("results", [])

        research = []

        seen = set()

        for result in results:

            title = self._clean_title(result.get("title", ""))

            if not title:
                continue

            if title.lower() in seen:
                continue

            if title.lower() in excluded:
                continue

            seen.add(title.lower())

            content = (
                result.get("raw_content")
                or result.get("content")
                or ""
            )

            url = result.get("url", "")

            published = (
                result.get("published_date")
                or result.get("published")
                or ""
            )

            research.append(
                {
                    "title": title,
                    "content": content,
                    "url": url,
                    "published": published,
                }
            )

            if len(research) == limit:
                break

            return research

    def _fetch_google_news_topics(self, limit: int, excluded: set[str]) -> list[str]:
        url = self._build_google_news_rss_url()
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            raise Exception(f"Trend search failed: {response.status_code} - {response.text}")

        root = ET.fromstring(response.content)
        topics = self._unique_clean_titles(
            (
                item.find("title").text
                for item in root.findall(".//item")
                if item.find("title") is not None and item.find("title").text
            ),
            limit,
            excluded,
        )
        return topics

    def _supplement_topics(self, topics: list[str], limit: int, excluded: set[str]) -> list[str]:
        used = excluded | {topic.lower() for topic in topics}
        candidates = self._daily_life_ai_topics()
        for topic in candidates:
            key = topic.lower()
            if key not in used:
                topics.append(topic)
                used.add(key)
            if len(topics) == limit:
                break

        if len(topics) < limit:
            raise Exception("Trend search did not return enough AI topics. Try again later.")
        return topics

    def _unique_clean_titles(self, titles, limit: int, excluded: set[str]) -> list[str]:
        topics = []
        seen = set()
        for title in titles:
            topic = self._clean_title(title)
            key = topic.lower()
            if topic and key not in seen and key not in excluded:
                topics.append(topic)
                seen.add(key)

            if len(topics) == limit:
                break
        return topics

    def _build_google_news_rss_url(self) -> str:
        params = urllib.parse.urlencode(
            {
                "q": self.query,
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en",
            }
        )
        return f"https://news.google.com/rss/search?{params}"

    def _clean_title(self, title: str) -> str:
        title = html.unescape(title)
        title = re.sub(r"\s+[-|]\s+[^-|]+$", "", title).strip()
        title = re.sub(r"\s+", " ", title)
        return title

    def _daily_life_ai_topics(self) -> list[str]:
        return [
            "How students can use AI to plan daily study sessions without losing focus",
            "AI note-taking workflows that help students revise faster before exams",
            "Using AI career tools to prepare resumes, projects, and interview practice",
            "How AI assistants can help students manage assignments, deadlines, and habits",
            "Practical AI tools students can use for research, coding, and presentations",
        ]
    def _expand_queries(self, topic: str) -> list[str]:
        return [
            topic,
            f"Latest {topic} news",
            f"{topic} announcements",
            f"{topic} tutorial",
            f"{topic} GitHub",
        ]
    
    def fetch_topic_research(self, topic: str) -> str:

        if not self.tavily_api_key:
            return topic
        


        all_results = []
        for query in self._expand_queries(topic):

            payload = {
                "query": query,
                "topic": "general",
                "search_depth": "advanced",
                "include_answer": True,
                "include_raw_content": True,
                "max_results": 5,
            }

            response = requests.post(
                "https://api.tavily.com/search",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                all_results.extend(response.json().get("results", []))
        headers = {
            "Authorization": f"Bearer {self.tavily_api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.tavily.com/search",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            return topic

        data = response.json()

        research = []

        if data.get("answer"):
            research.append(data["answer"])

        for result in data.get("results", []):

            title = result.get("title", "")
            content = (
                result.get("raw_content")
                or result.get("content")
                or ""
            )

            url = result.get("url", "")

            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            if not any(domain.endswith(d) for d in TRUSTED_DOMAINS):
                continue
            
            seen_titles = set()
            normalized = title.lower().strip()
            if normalized in seen_titles:
                continue
            seen_titles.add(normalized)

            research.append(
    f"""
========== ARTICLE ==========

Title:
{title}

Summary:
{content}

Source:
{url}

Published:
{result.get("published_date", "")}

=============================
"""
)
