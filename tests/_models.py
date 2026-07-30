from bot.research.models import (
    ResearchArticle,
    ResearchBundle,
    TrendingTopic,
)

# -------------------------------
# Test ResearchArticle
# -------------------------------

article = ResearchArticle(
    title="GPT-5.5 Released",
    url="https://openai.com",
    provider="tavily",
    summary="OpenAI released GPT-5.5.",
    content="This is the article content.",
    domain="openai.com",
)

print("===== ARTICLE =====")
print(article)

# -------------------------------
# Test ResearchBundle
# -------------------------------

bundle = ResearchBundle(query="OpenAI")

bundle.add(article)

print("\n===== BUNDLE =====")
print(bundle)

print("\nTotal Articles:", bundle.total_articles)
print("Providers:", bundle.providers)

# -------------------------------
# Test TrendingTopic
# -------------------------------

topic = TrendingTopic(
    title="OpenAI launches GPT-5.5",
    url="https://openai.com",
    provider="serpapi",
)

print("\n===== TRENDING TOPIC =====")
print(topic)

article2 = ResearchArticle(
    title="Claude 4 Released",
    url="https://anthropic.com",
    provider="serpapi",
)

bundle.add(article2)

print("\n===== AFTER SECOND ARTICLE =====")
print("Total:", bundle.total_articles)
print("Providers:", bundle.providers)