from bot.research.tavily import TavilyProvider

provider = TavilyProvider()

print(provider.trending_topics())

print(provider.research("OpenAI"))