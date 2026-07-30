from bot.research.models import (
    ResearchArticle,
    ResearchBundle,
)

from bot.research.analyzer import ResearchAnalyzer


bundle = ResearchBundle(query="OpenAI")

bundle.add(
    ResearchArticle(
        title="GPT-5.5 Released",
        url="https://openai.com",
        provider="tavily",
        summary="Skip to main content GPT-5.5 is now available. Read more.",
        content="Skip to main content\n\n"
        + ("GPT-5.5 improves reasoning. " * 200),
        published="Thu, 30 Jul 2026 08:00:00 GMT",
        domain="openai.com",
    )
)

bundle.add(
    ResearchArticle(
        title="Bad Article",
        url="https://example.com",
        provider="serpapi",
        summary="",
        content="short",
    )
)

analyzer = ResearchAnalyzer()

result = analyzer.analyze(bundle)

print()

print("Total:", result.total_articles)

print()

for article in result.articles:

    print(article.title)

    print(article.published)

    print(len(article.content))

    print(article.summary)