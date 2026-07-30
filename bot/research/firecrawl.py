from __future__ import annotations

import requests
import logging
from bot.research.exceptions import FirecrawlError

from config import FIRECRAWL_API_KEY

from bot.research.models import ResearchArticle

logger = logging.getLogger(__name__)


class FirecrawlProvider:
    """
    Enriches an existing ResearchArticle by
    scraping the article body from its URL.
    """

    BASE_URL = "https://api.firecrawl.dev/v1/scrape"

    def __init__(self):

        self.headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        }

    def scrape(
        self,
        article: ResearchArticle,
    ) -> ResearchArticle:

        if not article.url:
            return article

        if not FIRECRAWL_API_KEY:
            raise FirecrawlError("Firecrawl API key is not configured")

        payload = {
            "url": article.url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }

        try:

            response = requests.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=60,
            )
            logger.info("stage=provider.firecrawl status=response status_code=%s", response.status_code)

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as exc:

            raise FirecrawlError(
                f"Firecrawl request failed: {exc}"
            ) from exc

        markdown = (
            data.get("data", {})
            .get("markdown", "")
            .strip()
        )

        if markdown:
            article.content = markdown

        return article
