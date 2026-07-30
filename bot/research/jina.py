from __future__ import annotations

import requests
import logging

from bot.research.exceptions import JinaError
from bot.research.models import ResearchArticle

logger = logging.getLogger(__name__)


class JinaProvider:
    """
    Uses Jina Reader to extract clean article
    content from a webpage.
    """

    BASE_URL = "https://r.jina.ai/http://"

    def scrape(
        self,
        article: ResearchArticle,
    ) -> ResearchArticle:

        if not article.url:
            return article

        url = article.url

        if url.startswith("https://"):
            url = url.replace("https://", "", 1)

        elif url.startswith("http://"):
            url = url.replace("http://", "", 1)

        endpoint = self.BASE_URL + url

        try:

            response = requests.get(
                endpoint,
                timeout=60,
            )
            logger.info("stage=provider.jina status=response status_code=%s", response.status_code)

            response.raise_for_status()

        except requests.RequestException as exc:

            raise JinaError(
                f"Jina request failed: {exc}"
            ) from exc

        article.content = response.text.strip()

        return article
