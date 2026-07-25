import html
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from config import TREND_SEARCH_QUERY


class TrendClient:
    def __init__(self, query: str = TREND_SEARCH_QUERY):
        self.query = query

    def fetch_topics(self, limit: int = 3) -> list[str]:
        url = self._build_google_news_rss_url()
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            raise Exception(f"Trend search failed: {response.status_code} - {response.text}")

        root = ET.fromstring(response.content)
        topics = []
        seen = set()
        for item in root.findall(".//item"):
            title_node = item.find("title")
            if title_node is None or not title_node.text:
                continue

            topic = self._clean_title(title_node.text)
            key = topic.lower()
            if topic and key not in seen:
                topics.append(topic)
                seen.add(key)

            if len(topics) == limit:
                break

        if len(topics) < limit:
            raise Exception("Trend search did not return enough AI topics. Try again later.")
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
