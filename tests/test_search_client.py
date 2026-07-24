"""Unit tests for bot.search_client.

These tests patch `requests.post` / `requests.get` so we don't need
real API keys. We verify:
  * SearchClient selects Tavily vs Serp via SEARCH_PROVIDER
  * Tavily parsing maps the API JSON to our NewsItem shape
  * SerpAPI parsing does the same
  * is_available() correctly returns True/False based on configured keys
  * summarize_news_for_prompt renders multi-line grounding blocks
  * cache_is_fresh uses time.time()
"""
import time
import unittest
from unittest.mock import Mock, patch

import bot.search_client as sc
import config


def setUpModule():
    # Make sure the module-level config sees a stable key/mode for these tests.
    pass


class TavilyProviderTest(unittest.TestCase):
    def test_parses_news_results_into_normalized_items(self):
        fake_response = Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "results": [
                {
                    "title": "AI startup raises $1B",
                    "url": "https://reuters.com/tech/abc",
                    "content": "Reuters summary text...",
                    "raw_content": "Full article body here ...",
                    "published_date": "3 hours ago",
                    "image_url": "https://example.com/img.jpg",
                    "score": 0.95,
                },
                {
                    "title": "OpenAI ships new model",
                    "url": "https://techcrunch.com/abc",
                    "content": "Short",
                    "raw_content": "",
                    "published_date": "yesterday",
                },
            ]
        }

        with patch("bot.search_client.requests.post", return_value=fake_response) as post:
            items = sc._tavily_news("fake-key", query="AI", num=5, topic=None, days=1)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "AI startup raises $1B")
        self.assertEqual(items[0]["source"], "reuters.com")
        self.assertEqual(items[0]["age"], "3 hours ago")
        self.assertEqual(items[1]["source"], "techcrunch.com")
        # First item raw_content preferred, second falls back to content
        self.assertIn("Full article body", items[0]["content"])
        self.assertEqual(items[1]["content"], "Short")

        # Confirm payload sent correctly to Tavily.
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["api_key"], "fake-key")
        self.assertEqual(kwargs["json"]["query"], "AI")
        self.assertEqual(kwargs["json"]["max_results"], 5)


class SerpProviderTest(unittest.TestCase):
    def test_parses_news_results(self):
        fake_response = Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "news_results": [
                {
                    "title": "Markets rally on jobs data",
                    "link": "https://bloomberg.com/markets",
                    "snippet": "Markets rallied...",
                    "source": "Bloomberg",
                    "date": "5 hours ago",
                    "thumbnail": "https://img",
                }
            ]
        }

        with patch("bot.search_client.requests.get", return_value=fake_response) as get:
            items = sc._serp_news("fake-serp-key", query="markets", num=3)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Markets rally on jobs data")
        self.assertEqual(items[0]["source"], "Bloomberg")
        self.assertEqual(items[0]["url"], "https://bloomberg.com/markets")
        self.assertEqual(items[0]["image"], "https://img")
        # Serp has no full article content.
        self.assertEqual(items[0]["content"], "")

        params = get.call_args.kwargs["params"]
        self.assertEqual(params["tbm"], "nws")
        self.assertEqual(params["q"], "markets")


class SearchClientFacadesTest(unittest.TestCase):
    def test_is_available_tavily_needs_tavily_key(self):
        with patch.object(sc, "TAVILY_API_KEY", "tk"), patch.object(sc, "SEARCH_PROVIDER", "tavily"), \
             patch.object(sc, "SERP_API_KEY", ""), patch.object(config, "search_provider_configured", lambda: True):
            client = sc.SearchClient()
            self.assertTrue(client.is_available())

        with patch.object(sc, "TAVILY_API_KEY", ""), patch.object(sc, "SEARCH_PROVIDER", "tavily"), \
             patch.object(sc, "SERP_API_KEY", "sk"), patch.object(config, "search_provider_configured", lambda: False):
            client = sc.SearchClient()
            self.assertFalse(client.is_available())

    def test_fetch_top_news_dispatches_to_provider(self):
        fake_items = [{"title": "X", "url": "https://e/x", "snippet": "s", "source": "e",
                       "age": "1h", "content": "", "image": None, "score": None}]
        with patch.object(sc, "SEARCH_PROVIDER", "tavily"), \
             patch.object(sc, "TAVILY_API_KEY", "tk"), \
             patch.object(sc, "_tavily_news", return_value=fake_items) as tav:
            client = sc.SearchClient()
            items = client.fetch_top_news(query="AI", num=4, topic="technology")
        self.assertEqual(items, fake_items)
        self.assertEqual(tav.call_args.args[0], "tk")
        self.assertEqual(tav.call_args.kwargs["query"], "AI")

    def test_fetch_top_news_raises_when_unconfigured(self):
        with patch.object(sc, "SEARCH_PROVIDER", "serp"), \
             patch.object(sc, "SERP_API_KEY", ""):
            client = sc.SearchClient()
            with self.assertRaises(RuntimeError):
                client.fetch_top_news()


class HelperTests(unittest.TestCase):
    def test_summarize_news_for_prompt_includes_index_and_meta(self):
        items = [{"title": "T1", "source": "Reuters", "age": "1h",
                  "snippet": "snip A", "url": "https://r/1"},
                 {"title": "T2", "source": "TC", "age": "",
                  "snippet": "", "url": ""}]
        block = sc.summarize_news_for_prompt(items, max_items=2)
        self.assertIn("1. T1  [Reuters • 1h]", block)
        self.assertIn("https://r/1", block)
        self.assertIn("2. T2  [TC]", block)

    def test_summarize_respects_max_items(self):
        items = [{"title": f"t{i}", "source": "s", "age": "",
                  "snippet": "", "url": ""} for i in range(10)]
        block = sc.summarize_news_for_prompt(items, max_items=3)
        self.assertIn("1.", block)
        self.assertIn("3.", block)
        self.assertNotIn("4.", block)

    def test_news_items_json_roundtrip(self):
        items = [{"title": "T", "url": "u", "snippet": "s", "source": "src",
                  "age": "now", "content": "body", "image": None, "score": None}]
        encoded = sc.news_items_to_json(items)
        decoded = sc.news_items_from_json(encoded)
        self.assertEqual(decoded, items)
        # Bad JSON returns empty list.
        self.assertEqual(sc.news_items_from_json("not json"), [])
        self.assertEqual(sc.news_items_from_json(None), [])

    def test_cache_is_fresh_uses_time(self):
        with patch("bot.search_client.time.time", return_value=1000):
            self.assertTrue(sc.cache_is_fresh(900, ttl_seconds=200))  # 100 < 200
            self.assertFalse(sc.cache_is_fresh(700, ttl_seconds=200))  # 300 > 200
            self.assertFalse(sc.cache_is_fresh(800, ttl_seconds=0))   # ttl=0 always stale


if __name__ == "__main__":
    unittest.main()
