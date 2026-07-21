import unittest
from unittest.mock import Mock, patch

from bot.linkedin_client import LinkedInClient


class LinkedInClientTest(unittest.TestCase):
    @patch("bot.linkedin_client.LINKEDIN_VERSION", "202604")
    @patch("bot.linkedin_client.requests.post")
    @patch("bot.linkedin_client.get_tokens")
    def test_publish_post_uses_versioned_posts_api_payload(self, get_tokens, post):
        get_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_at": 4_000_000_000,
            "refresh_expires_at": 4_100_000_000,
            "author_urn": "urn:li:person:abc123",
            "author_type": "member",
        }
        response = Mock()
        response.status_code = 201
        response.headers = {"x-restli-id": "urn:li:share:12345"}
        post.return_value = response

        client = LinkedInClient()
        post_urn = client.publish_post("Approved draft")

        self.assertEqual("urn:li:share:12345", post_urn)
        post.assert_called_once()
        _, kwargs = post.call_args
        self.assertEqual("https://api.linkedin.com/rest/posts", post.call_args.args[0])
        self.assertEqual("2.0.0", kwargs["headers"]["X-Restli-Protocol-Version"])
        self.assertEqual("202604", kwargs["headers"]["Linkedin-Version"])
        self.assertEqual("urn:li:person:abc123", kwargs["json"]["author"])
        self.assertEqual("Approved draft", kwargs["json"]["commentary"])
        self.assertEqual("PUBLIC", kwargs["json"]["visibility"])
        self.assertEqual("PUBLISHED", kwargs["json"]["lifecycleState"])
        self.assertEqual("MAIN_FEED", kwargs["json"]["distribution"]["feedDistribution"])
        self.assertFalse(kwargs["json"]["isReshareDisabledByAuthor"])

    @patch("bot.linkedin_client.time.time")
    @patch("bot.linkedin_client.get_tokens")
    def test_refresh_access_token_fails_when_refresh_token_expired(self, get_tokens, time_now):
        time_now.return_value = 2_000
        get_tokens.return_value = {
            "access_token": "expired-access-token",
            "refresh_token": "expired-refresh-token",
            "expires_at": 1_000,
            "refresh_expires_at": 1_500,
            "author_urn": "urn:li:person:abc123",
        }

        client = LinkedInClient()

        with self.assertRaisesRegex(Exception, "refresh token expired"):
            client.refresh_access_token_if_needed()


if __name__ == "__main__":
    unittest.main()
