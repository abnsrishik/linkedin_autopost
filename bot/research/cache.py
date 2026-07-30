from __future__ import annotations

from datetime import datetime, timedelta

from bot.research.models import ResearchArticle
from copy import deepcopy


class ResearchCache:
    """
    Simple in-memory TTL cache.
    """

    def __init__(
        self,
        ttl_minutes: int = 30,
    ):

        self.ttl = timedelta(minutes=ttl_minutes)

        self._cache: dict[
            str,
            tuple[datetime, ResearchArticle]
        ] = {}

    def get(
        self,
        url: str,
    ) -> ResearchArticle | None:

        if url not in self._cache:
            return None

        timestamp, article = self._cache[url]

        if datetime.utcnow() - timestamp > self.ttl:

            del self._cache[url]

            return None

        return deepcopy(article)

    def set(
        self,
        article: ResearchArticle,
    ) -> None:

        if not article.url:
            return

        self._cache[article.url] = (
            datetime.utcnow(),
            deepcopy(article),
        )

    def clear(self) -> None:

        self._cache.clear()

    def size(self) -> int:

        return len(self._cache)