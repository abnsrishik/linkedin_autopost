from bot.research.router import ResearchRouter

router = ResearchRouter()

bundle = router.research("OpenAI")

print()

print("Query:", bundle.query)

print("Articles:", bundle.total_articles)

print()

for article in bundle.articles[:5]:

    print("=" * 60)

    print(article.title)

    print(article.provider)

    print(article.domain)

    print(article.score)

    print(len(article.content))