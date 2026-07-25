import html
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from config import TAVILY_API_KEY, TAVILY_TIME_RANGE, TREND_SEARCH_QUERY


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
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": 20,
        }
        headers = {
            "Authorization": f"Bearer {self.tavily_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post("https://api.tavily.com/search", headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Tavily trend search failed: {response.status_code} - {response.text}")

        topics = self._unique_clean_titles(
            (result.get("title") for result in response.json().get("results", [])),
            limit,
            excluded,
        )
        return topics

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
