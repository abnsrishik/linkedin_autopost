from bot.research.cache import ResearchCache
from bot.research.models import ResearchArticle

cache = ResearchCache(ttl_minutes=30)

article = ResearchArticle(
    title="GPT-5.5",
    url="https://openai.com/index/introducing-gpt-5-5/",
    provider="tavily",
    content="Hello World",
)

print()

print(cache.get(article.url))

cache.set(article)

print()

cached = cache.get(article.url)

print(cached.title)

print(cached.content)

print()

print(cache.size())

cache.clear()

print()

print(cache.size())