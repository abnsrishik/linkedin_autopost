import unittest
from unittest.mock import Mock, call, patch

from bot.groq_client import GroqClient, MAX_COMPLETION_TOKENS
from bot.research.models import ResearchArticle, ResearchBundle


class GroqClientTest(unittest.TestCase):
    def make_response(self, status_code, payload=None, text=None, headers=None):
        response = Mock()
        response.status_code = status_code
        response.headers = headers or {}
        response.text = text if text is not None else ""
        response.json.return_value = payload if payload is not None else {}
        return response

    @patch("bot.groq_client.time.sleep")
    @patch("bot.groq_client.requests.post")
    def test_429_retries_with_parsed_retry_duration_and_backoff(self, post, sleep):
        rate_limited = self.make_response(
            429,
            payload={"error": {"message": "Rate limit reached. Please try again in 1.5s."}},
            text='{"error":{"message":"Rate limit reached. Please try again in 1.5s."}}',
        )
        success = self.make_response(
            200,
            payload={
                "choices": [{"message": {"content": "Generated draft"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
            text='{"choices":[{"message":{"content":"Generated draft"}}]}',
        )
        post.side_effect = [rate_limited, rate_limited, success]

        draft = GroqClient().generate_post("AI automation")

        self.assertEqual("Generated draft", draft)
        self.assertEqual(3, post.call_count)
        self.assertEqual([call(2.5), call(5.0)], sleep.call_args_list)

    @patch("bot.groq_client.time.sleep")
    @patch("bot.groq_client.requests.post")
    def test_429_exhaustion_raises_graceful_runtime_error(self, post, sleep):
        post.return_value = self.make_response(
            429,
            payload={"error": {"message": "Rate limit reached. Please try again in 2s."}},
            text='{"error":{"message":"Rate limit reached. Please try again in 2s."}}',
        )

        with self.assertRaisesRegex(RuntimeError, "rate limit"):
            GroqClient().generate_post("AI automation")

        self.assertEqual(4, post.call_count)
        self.assertEqual(3, sleep.call_count)

    @patch("bot.groq_client.requests.post")
    def test_payload_reduces_completion_tokens(self, post):
        post.return_value = self.make_response(
            200,
            payload={
                "choices": [{"message": {"content": "Generated draft"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

        GroqClient().generate_post("AI automation")

        payload = post.call_args.kwargs["json"]
        self.assertEqual(MAX_COMPLETION_TOKENS, payload["max_completion_tokens"])
        self.assertEqual("low", payload["reasoning_effort"])
        self.assertFalse(payload["include_reasoning"])

    def test_research_bundle_prompt_uses_top_three_and_truncates_summary(self):
        bundle = ResearchBundle(query="AI agents")
        for index in range(5):
            bundle.add(
                ResearchArticle(
                    title=f"Article {index}",
                    url=f"https://example.com/{index}",
                    provider="test",
                    summary="s" * 400,
                    content="c" * 2000,
                    domain="example.com",
                    metadata={"unused": "metadata"},
                )
            )

        formatted = GroqClient()._format_research_bundle(bundle)

        self.assertIn("ARTICLE 1", formatted)
        self.assertIn("ARTICLE 3", formatted)
        self.assertNotIn("ARTICLE 4", formatted)
        self.assertNotIn("unused", formatted)
        self.assertLessEqual(len(formatted), 5400)


if __name__ == "__main__":
    unittest.main()
