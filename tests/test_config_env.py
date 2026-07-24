"""Make sure config.py tolerates the common forms a user might paste
into .env: with/without quotes, with extra whitespace, etc.

We do this by writing temporary .env files and re-importing the
config module with the temp dir's env vars overriding the real ones.
"""
import importlib
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class _ConfigReload:
    """Context manager that pins os.environ + reloads config from scratch."""

    def __init__(self, env_text: str, extra_env: dict | None = None):
        self.env_text = env_text
        self.extra_env = extra_env or {}
        self._previous = {}

    def __enter__(self):
        # Snapshot current env vars we'll touch.
        for key in [
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_USER_ID", "GROQ_API_KEY",
            "GROQ_MODEL", "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET",
            "LINKEDIN_REDIRECT_URI", "LINKEDIN_VERSION",
            "SEARCH_PROVIDER", "TAVILY_API_KEY", "SERP_API_KEY",
            "SEARCH_CACHE_TTL_SECONDS", "SEARCH_DEFAULT_NUM",
        ]:
            self._previous[key] = os.environ.get(key)
            os.environ.pop(key, None)
        # Apply extra_env
        for k, v in self.extra_env.items():
            os.environ[k] = v
        # Write .env
        tmp = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        tmp.write(self.env_text)
        tmp.close()
        self._path = tmp.name

        # Patch load_dotenv to read from our file.
        import dotenv as _dotenv
        self._orig_load_dotenv = _dotenv.load_dotenv

        def _loader(*args, **kwargs):
            kwargs.setdefault("dotenv_path", self._path)
            kwargs.setdefault("override", True)
            return self._orig_load_dotenv(**kwargs)

        _dotenv.load_dotenv = _loader
        # Reload config from scratch.
        sys.modules.pop("config", None)
        self.config = importlib.import_module("config")
        # Restore load_dotenv immediately; reload keeps behavior.
        _dotenv.load_dotenv = self._orig_load_dotenv
        return self.config

    def __exit__(self, *exc):
        for key, val in self._previous.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        try:
            Path(self._path).unlink()
        except Exception:
            pass


class EnvQuotingTolerantTest(unittest.TestCase):
    def _required_env(self):
        return "\n".join([
            "TELEGRAM_BOT_TOKEN=bt123",
            "TELEGRAM_USER_ID=9999",
            "GROQ_API_KEY=gr123",
            "LINKEDIN_CLIENT_ID=cli",
            "LINKEDIN_CLIENT_SECRET=sec",
        ])

    def test_no_quotes_string_var(self):
        env = self._required_env() + "\nTAVILY_API_KEY=tk_raw\n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.TAVILY_API_KEY, "tk_raw")
            self.assertEqual(c.TELEGRAM_USER_ID, 9999)

    def test_double_quoted_string_var(self):
        env = self._required_env() + "\nTAVILY_API_KEY=\"tk_double\"\n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.TAVILY_API_KEY, "tk_double")

    def test_single_quoted_string_var(self):
        env = self._required_env() + "\nTAVILY_API_KEY='tk_single'\n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.TAVILY_API_KEY, "tk_single")

    def test_extra_whitespace_is_stripped(self):
        env = self._required_env() + "\nTAVILY_API_KEY=    tk_space   \n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.TAVILY_API_KEY, "tk_space")

    def test_quotes_with_whitespace_stripped(self):
        env = self._required_env() + "\nTAVILY_API_KEY=   \"tk_combo\"  \n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.TAVILY_API_KEY, "tk_combo")

    def test_integer_raw_and_quoted(self):
        for env in [
            self._required_env() + "\nTELEGRAM_USER_ID=424242\n",
            self._required_env() + "\nTELEGRAM_USER_ID=\"424242\"\n",
            self._required_env() + "\nTELEGRAM_USER_ID='424242'\n",
        ]:
            with _ConfigReload(env) as c:
                self.assertEqual(c.TELEGRAM_USER_ID, 424242)

    def test_garbage_integer_falls_back_to_zero(self):
        env = self._required_env() + "\nTELEGRAM_USER_ID=not_a_number\n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.TELEGRAM_USER_ID, 0)

    def test_search_default_num_accepts_int_string(self):
        env = self._required_env() + "\nSEARCH_DEFAULT_NUM=12\n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.SEARCH_DEFAULT_NUM, 12)

    def test_search_default_num_garbage_falls_back_to_default(self):
        env = self._required_env() + "\nSEARCH_DEFAULT_NUM=many\n"
        with _ConfigReload(env) as c:
            self.assertEqual(c.SEARCH_DEFAULT_NUM, 8)  # default

    def test_empty_value_treated_as_missing(self):
        env = self._required_env() + "\nTAVILY_API_KEY=\n"
        with _ConfigReload(env) as c:
            self.assertFalse(bool(c.TAVILY_API_KEY))
            self.assertFalse(c.search_provider_configured())

    def test_search_provider_is_lowercased(self):
        env = self._required_env() + '\nTAVILY_API_KEY=tk\nSEARCH_PROVIDER="Tavily"\n'
        with _ConfigReload(env) as c:
            self.assertEqual(c.SEARCH_PROVIDER, "tavily")
            self.assertTrue(c.search_provider_configured())


if __name__ == "__main__":
    unittest.main()
