import unittest
from unittest.mock import Mock, patch

from bot.trend_client import TrendClient


class TrendClientTest(unittest.TestCase):
    @patch("bot.trend_client.requests.get")
    def test_fetch_topics_reads_google_news_rss(self, get):
        response = Mock()
        response.status_code = 200
        response.content = b"""<?xml version="1.0"?>
<rss><channel>
<item><title>AI tutors are changing study habits - Example News</title></item>
<item><title>Students use AI agents for project work | Example News</title></item>
<item><title>New AI coding tools for beginners - Example News</title></item>
</channel></rss>"""
        get.return_value = response

        topics = TrendClient(query="AI students", tavily_api_key=None).fetch_topics()

        self.assertEqual(
            [
                "AI tutors are changing study habits",
                "Students use AI agents for project work",
                "New AI coding tools for beginners",
            ],
            topics,
        )

    @patch("bot.trend_client.requests.post")
    def test_fetch_topics_uses_tavily_when_api_key_is_present(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "results": [
                {"title": "AI note-taking tools help students manage classes"},
                {"title": "AI career coaches move into college job searches"},
                {"title": "Students use AI scheduling assistants in daily life"},
            ]
        }
        post.return_value = response

        topics = TrendClient(query="AI students", tavily_api_key="tvly-test").fetch_topics()

        self.assertEqual(
            [
                "AI note-taking tools help students manage classes",
                "AI career coaches move into college job searches",
                "Students use AI scheduling assistants in daily life",
            ],
            topics,
        )
        _, kwargs = post.call_args
        self.assertEqual("Bearer tvly-test", kwargs["headers"]["Authorization"])
        self.assertEqual("news", kwargs["json"]["topic"])
        self.assertEqual("day", kwargs["json"]["time_range"])

    @patch("bot.trend_client.requests.post")
    def test_fetch_topics_excludes_previous_topics_for_regeneration(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "results": [
                {"title": "Repeated AI topic"},
                {"title": "Fresh AI study topic"},
                {"title": "Fresh AI career topic"},
                {"title": "Fresh AI daily life topic"},
            ]
        }
        post.return_value = response

        topics = TrendClient(tavily_api_key="tvly-test").fetch_topics(
            exclude_topics=["Repeated AI topic"]
        )

        self.assertEqual(
            ["Fresh AI study topic", "Fresh AI career topic", "Fresh AI daily life topic"],
            topics,
        )

    @patch("bot.trend_client.requests.post")
    def test_fetch_topics_supplements_when_tavily_returns_too_few_unique_results(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "results": [
                {"title": "Repeated AI topic"},
                {"title": "Repeated AI topic"},
            ]
        }
        post.return_value = response

        topics = TrendClient(tavily_api_key="tvly-test").fetch_topics(
            exclude_topics=["Repeated AI topic"]
        )

        self.assertEqual(3, len(topics))
        self.assertIn("How students can use AI to plan daily study sessions without losing focus", topics)


if __name__ == "__main__":
    unittest.main()
