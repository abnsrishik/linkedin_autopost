from bot.research.serpapi import SerpAPIProvider

provider = SerpAPIProvider()

print(provider.trending_topics())

print(provider.research("OpenAI"))