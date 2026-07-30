from bot.research.models import (
    ResearchArticle,
    ResearchBundle,
)

from bot.research.ranker import ResearchRanker


bundle = ResearchBundle(query="OpenAI")

bundle.add(
    ResearchArticle(
        title="GPT-5.5 Released",
        url="https://openai.com/gpt55",
        provider="tavily",
        content="Full article",
        summary="Summary",
        answer="Answer",
        domain="openai.com",
    )
)

bundle.add(
    ResearchArticle(
        title="GPT-5.5 Released",
        url="https://openai.com/gpt55",
        provider="serpapi",
        summary="Duplicate",
        domain="openai.com",
    )
)

bundle.add(
    ResearchArticle(
        title="Claude 4 Released",
        url="https://anthropic.com/news",
        provider="tavily",
        summary="Claude",
        domain="anthropic.com",
    )
)

ranker = ResearchRanker()

result = ranker.rank(bundle)

print()

print("Total:", result.total_articles)

print()

for article in result.articles:
    print(article.score, article.title)