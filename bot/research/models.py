from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ResearchArticle:
    """
    Represents a single article returned by a research provider.
    """

    title: str
    url: str
    provider: str
    summary: str = ""
    content: str = ""
    domain: str = ""
    published: str | datetime | None = None
    answer: str = ""
    score: float = 0.0
    language: str = "en"
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "provider": self.provider,
            "summary": self.summary,
            "content": self.content,
            "domain": self.domain,
            "published": self.published.isoformat()
            if isinstance(self.published, datetime)
            else self.published,
            "answer": self.answer,
            "score": self.score,
            "language": self.language,
            "fetched_at": self.fetched_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ResearchBundle:
    """
    Collection of articles for one research request.
    """

    query: str
    articles: list[ResearchArticle] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add(self, article: ResearchArticle):
        self.articles.append(article)

        if article.provider not in self.providers:
            self.providers.append(article.provider)

    def extend(self, articles: list[ResearchArticle]):
        for article in articles:
            self.add(article)

    @property
    def total_articles(self) -> int:
        return len(self.articles)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "articles": [article.to_dict() for article in self.articles],
            "providers": self.providers,
            "created_at": self.created_at.isoformat(),
            "total_articles": self.total_articles,
        }


@dataclass(slots=True)
class TrendingTopic:
    """
    Lightweight object used for trending feeds.
    """

    title: str
    url: str
    provider: str
    published: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "provider": self.provider,
            "published": self.published,
            "metadata": self.metadata,
        }
