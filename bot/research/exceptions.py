class ResearchError(Exception):
    """
    Base exception for the research pipeline.
    """

    pass


class ProviderError(ResearchError):
    """
    Generic provider failure.
    """

    pass


class FirecrawlError(ProviderError):
    """
    Firecrawl provider failed.
    """

    pass


class JinaError(ProviderError):
    """
    Jina provider failed.
    """

    pass


class TavilyError(ProviderError):
    """
    Tavily provider failed.
    """

    pass


class SerpAPIError(ProviderError):
    """
    SerpAPI provider failed.
    """

    pass