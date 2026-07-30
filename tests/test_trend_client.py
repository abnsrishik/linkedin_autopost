import unittest

from bot.research.models import ResearchBundle, TrendingTopic
from bot.trend_client import TrendClient


class FakeRouter:
    def __init__(self):
        self.trending_calls = []
        self.research_calls = []

    def trending_topics(self, limit=3, exclude_topics=None):
        self.trending_calls.append((limit, exclude_topics))
        return [
            TrendingTopic(
                title="AI tutors are changing study habits",
                url="https://example.com/1",
                provider="test",
            ),
            {"title": "Students use AI agents for project work"},
            "New AI coding tools for beginners",
        ][:limit]

    def research(self, topic):
        self.research_calls.append(topic)
        return ResearchBundle(query=topic)


class TrendClientTest(unittest.TestCase):
    def test_fetch_topics_delegates_to_router_and_returns_legacy_titles(self):
        router = FakeRouter()
        topics = TrendClient(router=router).fetch_topics(
            limit=3,
            exclude_topics=["Old topic"],
        )

        self.assertEqual(
            [
                "AI tutors are changing study habits",
                "Students use AI agents for project work",
                "New AI coding tools for beginners",
            ],
            topics,
        )
        self.assertEqual([(3, ["Old topic"])], router.trending_calls)

    def test_fetch_topic_research_delegates_to_router(self):
        router = FakeRouter()
        bundle = TrendClient(router=router).fetch_topic_research("AI automation")

        self.assertEqual("AI automation", bundle.query)
        self.assertEqual(["AI automation"], router.research_calls)

    def test_legacy_constructor_kwargs_do_not_restore_http_logic(self):
        router = FakeRouter()
        topics = TrendClient(
            router=router,
            query="AI students",
            tavily_api_key="tvly-test",
        ).fetch_topics()

        self.assertEqual(3, len(topics))
        self.assertEqual([(3, None)], router.trending_calls)


if __name__ == "__main__":
    unittest.main()
