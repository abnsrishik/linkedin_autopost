import unittest
from unittest.mock import Mock, patch

import setup_linkedin_oauth as oauth


class SetupLinkedInOAuthTest(unittest.TestCase):
    def test_authorization_url_contains_redirect_scope_and_state(self):
        url = oauth.build_authorization_url("state-token")

        self.assertIn("response_type=code", url)
        self.assertIn("state=state-token", url)
        self.assertIn("redirect_uri=", url)
        self.assertIn("w_member_social", url)
        self.assertIn("openid", url)
        self.assertIn("profile", url)

    @patch("setup_linkedin_oauth.requests.post")
    def test_exchange_code_allows_missing_refresh_token(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"access_token": "access", "expires_in": 3600}
        post.return_value = response

        data = oauth.exchange_code_for_tokens("auth-code")

        self.assertEqual("access", data["access_token"])
        self.assertEqual(3600, data["expires_in"])

    @patch("setup_linkedin_oauth.requests.get")
    def test_get_linkedin_member_urn_uses_userinfo_subject(self, get):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "sub": "abc123",
            "name": "Test User",
        }
        get.return_value = response

        author_urn = oauth.get_linkedin_member_urn("access-token")

        self.assertEqual("urn:li:person:abc123", author_urn)

    @patch("setup_linkedin_oauth.save_tokens")
    def test_save_oauth_result_defaults_refresh_expiry(self, save_tokens):
        oauth.save_oauth_result(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
            "urn:li:person:abc123",
        )

        save_tokens.assert_called_once_with(
            access_token="access",
            refresh_token="refresh",
            expires_in=3600,
            refresh_token_expires_in=3600,
            author_urn="urn:li:person:abc123",
            author_type="member",
        )


if __name__ == "__main__":
    unittest.main()
