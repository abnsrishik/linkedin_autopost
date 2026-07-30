from __future__ import annotations

from typing import List


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

    def __init__(
        self,
        tavily=None,
        serpapi=None,
        firecrawl=None,
        jina=None,
    ):
        self.tavily = tavily
        self.serpapi = serpapi
        self.firecrawl = firecrawl
        self.jina = jina

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

                provider_results = provider.search(topic)

                if provider_results:
                    results.extend(provider_results)

            except Exception as e:

                print(
                    f"[Router] Provider "
                    f"{provider.__class__.__name__} failed: {e}"
                )

        return results

    # -----------------------------------------------------

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