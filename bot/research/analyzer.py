from __future__ import annotations

import re
from datetime import datetime

from bot.research.models import (
    ResearchArticle,
    ResearchBundle,
)


class ResearchAnalyzer:
    """
    Cleans and normalizes ranked research before
    it is sent to the LLM.
    """

    MAX_CONTENT_LENGTH = 4000

    MIN_CONTENT_LENGTH = 150

    def analyze(
        self,
        bundle: ResearchBundle,
    ) -> ResearchBundle:

        cleaned_articles = []

        for article in bundle.articles:

            article.summary = self._clean(article.summary)

            article.content = self._clean(article.content)

            article.content = article.content[
                : self.MAX_CONTENT_LENGTH
            ]

            article.published = self._normalize_date(
                article.published
            )

            if not self._is_valid(article):
                continue

            cleaned_articles.append(article)

        return ResearchBundle(
            query=bundle.query,
            articles=cleaned_articles,
            providers=bundle.providers,
        )

    def _clean(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        text = re.sub(r"\s+", " ", text)

        boilerplate = [
            "Skip to main content",
            "Privacy Policy",
            "Terms of Use",
            "Help Center",
            "Read more",
            "Cookie Policy",
            "All rights reserved",
        ]

        for item in boilerplate:
            text = text.replace(item, "")

        return text.strip()

    def _normalize_date(
        self,
        date: str,
    ) -> str:

        if not date:
            return ""

        formats = [
            "%a, %d %b %Y %H:%M:%S GMT",
            "%m/%d/%Y, %I:%M %p, %z UTC",
            "%Y-%m-%d",
        ]

        for fmt in formats:

            try:
                dt = datetime.strptime(date, fmt)
                return dt.isoformat()
            except ValueError:
                pass

        return date

    def _is_valid(
        self,
        article: ResearchArticle,
    ) -> bool:

        if not article.title:
            return False

        if not article.url:
            return False

        return True
