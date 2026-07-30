from bot.research.models import ResearchArticle
from bot.research.firecrawl import FirecrawlProvider

article = ResearchArticle(
    title="GPT-5.5",
    url="https://openai.com/index/introducing-gpt-5-5/",
    provider="serpapi",
)

provider = FirecrawlProvider()

article = provider.scrape(article)

print()

print(article.title)

print(article.url)

print(len(article.content))

print(article.content[:500])