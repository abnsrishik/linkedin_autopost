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

        topics = TrendClient(query="AI students").fetch_topics()

        self.assertEqual(
            [
                "AI tutors are changing study habits",
                "Students use AI agents for project work",
                "New AI coding tools for beginners",
            ],
            topics,
        )


if __name__ == "__main__":
    unittest.main()
