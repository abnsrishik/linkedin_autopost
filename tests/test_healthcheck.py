import unittest
from unittest.mock import patch

import healthcheck


class HealthcheckTest(unittest.TestCase):
    @patch("healthcheck.time.time")
    @patch("healthcheck.get_tokens")
    @patch("healthcheck.init_db")
    @patch("healthcheck.validate_config")
    def test_healthcheck_fails_for_expired_refresh_token(self, validate_config, init_db, get_tokens, time_now):
        time_now.return_value = 2_000
        get_tokens.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 1_000,
            "refresh_expires_at": 1_500,
            "author_urn": "urn:li:person:abc123",
        }

        self.assertEqual(1, healthcheck.main())

    @patch("healthcheck.time.time")
    @patch("healthcheck.get_tokens")
    @patch("healthcheck.init_db")
    @patch("healthcheck.validate_config")
    def test_healthcheck_passes_when_access_expired_but_refresh_valid(
        self, validate_config, init_db, get_tokens, time_now
    ):
        time_now.return_value = 2_000
        get_tokens.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 1_000,
            "refresh_expires_at": 3_000,
            "author_urn": "urn:li:person:abc123",
        }

        self.assertEqual(0, healthcheck.main())


if __name__ == "__main__":
    unittest.main()
