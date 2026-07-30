from __future__ import annotations

from difflib import SequenceMatcher

from bot.research.models import (
    ResearchArticle,
    ResearchBundle,
)


class ResearchRanker:
    """
    Removes duplicates and ranks articles.
    """

    def rank(
        self,
        bundle: ResearchBundle,
    ) -> ResearchBundle:

        unique = self._remove_duplicates(bundle.articles)

        for article in unique:
            article.score = self._score(article)

        unique.sort(
            key=lambda x: x.score,
            reverse=True,
        )

        return ResearchBundle(
            query=bundle.query,
            articles=unique,
            providers=bundle.providers,
        )

    def _score(
        self,
        article: ResearchArticle,
    ) -> float:

        score = 0

        if article.content:
            score += 40

        if article.summary:
            score += 20

        if article.answer:
            score += 10

        trusted = {
            "openai.com",
            "anthropic.com",
            "huggingface.co",
            "techcrunch.com",
            "venturebeat.com",
            "wired.com",
            "reuters.com",
            "theverge.com",
            "deepmind.google",
            "nvidia.com",
            "microsoft.com",
        }

        if article.domain in trusted:
            score += 30

        return score

    def _remove_duplicates(
        self,
        articles: list[ResearchArticle],
    ) -> list[ResearchArticle]:

        result = []

        seen_urls = set()

        for article in articles:

            if article.url:

                if article.url in seen_urls:
                    continue

                seen_urls.add(article.url)

            duplicate = False

            for existing in result:

                similarity = SequenceMatcher(
                    None,
                    article.title.lower(),
                    existing.title.lower(),
                ).ratio()

                if similarity > 0.90:
                    duplicate = True
                    break

            if not duplicate:
                result.append(article)

        return result