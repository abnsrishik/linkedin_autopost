from __future__ import annotations
import logging
from typing import List
from bot.research.analyzer import ResearchAnalyzer
from bot.research.cache import ResearchCache
from bot.research.exceptions import FirecrawlError
from bot.research.firecrawl import FirecrawlProvider
from bot.research.jina import JinaProvider
from bot.research.models import ResearchBundle, TrendingTopic
from bot.research.ranker import ResearchRanker
from bot.research.tavily import TavilyProvider
from bot.research.serpapi import SerpAPIProvider    

logger = logging.getLogger(__name__)


class ResearchRouter:
    """
    Routes a research request to one or more providers.

    The router itself contains NO scraping logic.

    Each provider exposes:

        search(topic: str) -> list[dict]

    and returns a list of Research Articles.

    The router merges every provider's output into one list.

    Later stages:
        -> Ranker
        -> Analyzer
        -> Writer
    """

    def __init__(self, tavily=None, serpapi=None):

        self.tavily = tavily or TavilyProvider()

        self.serpapi = serpapi or SerpAPIProvider()

        self.providers = [
            self.tavily,
            self.serpapi,
        ]

        self.ranker = ResearchRanker()

        self.analyzer = ResearchAnalyzer()

        self.cache = ResearchCache()

        self.firecrawl = FirecrawlProvider()

        self.jina = JinaProvider()

    # -----------------------------------------------------

    def search(self, topic: str) -> List[dict]:
        """
        Main entry point.

        Example:

            router.search("OpenAI GPT-6")

        Returns:

            [
                {...},
                {...},
                {...}
            ]
        """

        results = []

        providers = self._select_providers(topic)

        for provider in providers:

            try:
                logger.info("stage=research.search provider=%s status=started", provider.__class__.__name__)

                provider_results = provider.research(topic)

                if provider_results:
                    results.extend(provider_results)
                logger.info(
                    "stage=research.search provider=%s status=completed count=%s",
                    provider.__class__.__name__,
                    len(provider_results or []),
                )

            except Exception as e:

                logger.exception(
                    "stage=research.search provider=%s status=failed reason=%s",
                    provider.__class__.__name__,
                    e,
                )
                

        return results

    # -----------------------------------------------------

    def trending_topics(
        self,
        limit: int = 3,
        exclude_topics: list[str] | None = None,
    ):
        topics = []

        for provider in self.providers:
            try:
                logger.info("stage=research.trending provider=%s status=started", provider.__class__.__name__)
                topics.extend(provider.trending_topics(limit))
                logger.info("stage=research.trending provider=%s status=completed", provider.__class__.__name__)
            except Exception as e:
                logger.exception(
                    "stage=research.trending provider=%s status=failed reason=%s",
                    provider.__class__.__name__,
                    e,
                )

        excluded = {
            self._topic_title(topic).lower()
            for topic in (exclude_topics or [])
        }

        filtered = []

        for topic in topics:
            title = self._topic_title(topic).lower()

            if title in excluded:
                continue

            filtered.append(topic)

        if len(filtered) < limit:
            filtered.extend(self._fallback_topics(excluded, limit - len(filtered)))

        return filtered[:limit]

    def _topic_title(self, topic) -> str:
        if isinstance(topic, str):
            return topic
        if isinstance(topic, dict):
            return topic.get("title", "")
        return getattr(topic, "title", str(topic))

    def _fallback_topics(self, excluded: set[str], count: int) -> list[TrendingTopic]:
        fallback_titles = [
            "How students can use AI to plan daily study sessions without losing focus",
            "What early-career developers should learn about AI agents this week",
            "How builders can evaluate new AI tools without chasing every launch",
        ]
        topics = []
        for title in fallback_titles:
            if title.lower() in excluded:
                continue
            topics.append(TrendingTopic(title=title, url="", provider="fallback"))
            if len(topics) >= count:
                break
        return topics

    def _select_providers(self, topic: str):

        """
        Decide which providers should be used.

        Currently:

        Everything uses Tavily.

        Future:

        AI News
            Tavily
            SerpAPI

        Programming
            Tavily
            GitHub

        Research
            Tavily
            arXiv

        etc.
        """

        providers = []

        if self.tavily:
            providers.append(self.tavily)

        #
        # Future routing rules
        #

        lowered = topic.lower()

        ai_keywords = [
            "ai",
            "gpt",
            "llm",
            "openai",
            "anthropic",
            "claude",
            "gemini",
            "deepmind",
        ]

        if any(word in lowered for word in ai_keywords):

            if self.serpapi:
                providers.append(self.serpapi)

        return providers
    
    def research(self, topic: str) -> ResearchBundle:
        logger.info("stage=research.pipeline status=started topic=%s", topic)

        results = []

        #
        # Collect research
        #

        providers = self._select_providers(topic)

        for provider in providers:

            try:
                logger.info("stage=research.provider provider=%s status=started", provider.__class__.__name__)

                provider_results = provider.research(topic)

                if provider_results:
                    results.extend(provider_results)
                logger.info(
                    "stage=research.provider provider=%s status=completed count=%s",
                    provider.__class__.__name__,
                    len(provider_results or []),
                )

            except Exception as e:

                logger.exception(
                    "stage=research.provider provider=%s status=failed reason=%s",
                    provider.__class__.__name__,
                    e,
                )

        bundle = ResearchBundle(
            query=topic,
            articles=results,
            providers=self._provider_names(results),
        )
        logger.info("stage=research.collect status=completed articles=%s", bundle.total_articles)

        #
        # Rank
        #

        bundle = self.ranker.rank(bundle)
        logger.info("stage=research.rank status=completed articles=%s", bundle.total_articles)

        #
        # Analyze
        #

        bundle = self.analyzer.analyze(bundle)
        logger.info("stage=research.analyze status=completed articles=%s", bundle.total_articles)

        #
        # Enrich articles
        #

        for article in bundle.articles:

            cached = self.cache.get(article.url)

            if cached:

                article.content = cached.content
                logger.info("stage=research.cache status=hit url=%s", article.url)

                continue

            try:
                logger.info("stage=research.firecrawl status=started url=%s", article.url)

                article = self.firecrawl.scrape(article)
                logger.info("stage=research.firecrawl status=completed url=%s", article.url)

            except FirecrawlError:

                try:
                    logger.info("stage=research.jina status=started url=%s", article.url)

                    article = self.jina.scrape(article)
                    logger.info("stage=research.jina status=completed url=%s", article.url)

                except Exception as e:

                    logger.exception("stage=research.jina status=failed url=%s reason=%s", article.url, e)
            self.cache.set(article)

        logger.info("stage=research.pipeline status=completed articles=%s", bundle.total_articles)
        return bundle

    def _provider_names(self, articles) -> list[str]:
        providers = []
        for article in articles:
            if article.provider not in providers:
                providers.append(article.provider)
        return providers
