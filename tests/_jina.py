from bot.research.jina import JinaProvider
from bot.research.models import ResearchArticle

article = ResearchArticle(
    title="GPT-5.5",
    url="https://openai.com/index/introducing-gpt-5-5/",
    provider="serpapi",
)

provider = JinaProvider()

article = provider.scrape(article)

print()

print(article.title)

print(article.url)

print()

print("Characters:", len(article.content))

print()

print(article.content[:500])