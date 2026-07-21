import sys
import time

from config import validate_config
from bot.db import get_tokens, init_db


def main():
    failures = []

    try:
        validate_config()
        print("OK config")
    except Exception as e:
        failures.append(str(e))
        print(f"FAIL config: {e}")

    try:
        init_db()
        print("OK database schema")
    except Exception as e:
        failures.append(f"Database schema error: {e}")
        print(f"FAIL database schema: {e}")

    try:
        token_data = get_tokens()
        if not token_data:
            failures.append("LinkedIn OAuth tokens missing. Run setup_linkedin_oauth.py.")
            print("FAIL LinkedIn OAuth tokens missing")
        elif not token_data.get("author_urn"):
            failures.append("LinkedIn member author URN missing. Run setup_linkedin_oauth.py.")
            print("FAIL LinkedIn member author URN missing")
        elif not token_data["author_urn"].startswith("urn:li:person:"):
            failures.append("LinkedIn author URN must be a person URN for personal profile posting.")
            print("FAIL LinkedIn author URN is not a person URN")
        elif time.time() >= token_data["refresh_expires_at"]:
            failures.append("LinkedIn refresh token expired. Run setup_linkedin_oauth.py again.")
            print("FAIL LinkedIn refresh token expired")
        elif time.time() >= token_data["expires_at"]:
            print("OK LinkedIn OAuth token row and member author URN; access token will refresh on publish")
        else:
            print("OK LinkedIn OAuth token row and member author URN")
    except Exception as e:
        failures.append(f"LinkedIn token check error: {e}")
        print(f"FAIL LinkedIn token check: {e}")

    if failures:
        print("\nHealthcheck failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nHealthcheck passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
