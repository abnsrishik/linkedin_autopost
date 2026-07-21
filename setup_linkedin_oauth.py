import argparse
import secrets
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from config import LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REDIRECT_URI
from bot.db import init_db, save_tokens


SCOPES = "openid profile w_member_social"
REQUEST_TIMEOUT_SECONDS = 30


class OAuthCallbackServer:
    def __init__(self, host: str, port: int, expected_state: str):
        self.code = None
        self.error = None
        self.state = None
        self.expected_state = expected_state

        outer = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                outer.code = params.get("code", [None])[0]
                outer.error = params.get("error_description", params.get("error", [None]))[0]
                outer.state = params.get("state", [None])[0]

                if outer.code and outer.state == outer.expected_state:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<h1>Success</h1><p>Authorization complete. Return to terminal.</p>")
                else:
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    message = outer.error or "Authorization response did not include a valid code/state."
                    body = (
                        "<h1>Authorization failed</h1>"
                        f"<p>{message}</p>"
                        "<p>Return to terminal.</p>"
                    )
                    self.wfile.write(body.encode("utf-8"))

        self.server = HTTPServer((host, port), CallbackHandler)
        self.server.timeout = 300

    def wait_for_code(self):
        self.server.handle_request()
        self.server.server_close()

        if self.state and self.state != self.expected_state:
            raise RuntimeError("OAuth state mismatch. Authorization response rejected.")
        if self.error:
            raise RuntimeError(f"LinkedIn authorization failed: {self.error}")
        if not self.code:
            raise RuntimeError("Authorization timed out or no code was returned.")
        return self.code


def parse_redirect_port():
    return int(urllib.parse.urlparse(LINKEDIN_REDIRECT_URI).port or 8080)


def build_authorization_url(state: str):
    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    return "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(code: str):
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(token_url, data=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise RuntimeError(f"Token generation failed: {response.status_code} - {response.text}")

    data = response.json()
    if "access_token" not in data:
        raise RuntimeError(f"Token generation failed: {data}")
    if "refresh_token" not in data:
        print("Note: LinkedIn did not return a refresh_token. Access token will need manual re-auth when it expires.")
    return data


def get_linkedin_member_urn(access_token):
    url = "https://api.linkedin.com/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch LinkedIn member profile: {response.status_code} - {response.text}")

    member_id = response.json().get("sub")
    if not member_id:
        raise RuntimeError("LinkedIn userinfo response did not include member subject identifier.")
    return f"urn:li:person:{member_id}"


def save_oauth_result(token_data, author_urn):
    has_refresh = "refresh_token" in token_data
    save_tokens(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        expires_in=token_data["expires_in"],
        refresh_token_expires_in=token_data.get(
            "refresh_token_expires_in", token_data["expires_in"]
        ),
        author_urn=author_urn,
        author_type="member",
    )
    if not has_refresh:
        print("Access token saved without refresh token. Use /reauth in Telegram when it expires.")


def perform_reauth(code: str):
    token_data = exchange_code_for_tokens(code)
    author_urn = get_linkedin_member_urn(token_data["access_token"])
    save_oauth_result(token_data, author_urn)
    return author_urn


def main():
    parser = argparse.ArgumentParser(description="Set up LinkedIn OAuth tokens for autoposter.")
    parser.add_argument(
        "--manual-code",
        help="Authorization code copied from the redirect URL. Use when the callback server cannot receive the redirect.",
    )
    args = parser.parse_args()

    init_db()

    if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
        print("Configure LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.")
        return 1

    state = secrets.token_urlsafe(24)
    auth_url = build_authorization_url(state)

    print("\n=== LinkedIn OAuth Setup ===")
    print("Open this URL in your browser:")
    print("-" * 60)
    print(auth_url)
    print("-" * 60)

    if args.manual_code:
        code = args.manual_code.strip()
    else:
        port = parse_redirect_port()
        print(f"Waiting up to 5 minutes on {LINKEDIN_REDIRECT_URI} ...")
        print("On a remote server, use an SSH tunnel or rerun with --manual-code.")
        server = OAuthCallbackServer("localhost", port, state)
        code = server.wait_for_code()

    print("\nExchanging authorization code for tokens...")
    token_data = exchange_code_for_tokens(code)

    print("Fetching authenticated LinkedIn member profile...")
    author_urn = get_linkedin_member_urn(token_data["access_token"])
    save_oauth_result(token_data, author_urn)

    print(f"\nConfiguration saved. Target Author: {author_urn}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOAuth setup cancelled.")
        sys.exit(130)
    except Exception as e:
        print(f"\nOAuth setup failed: {e}")
        sys.exit(1)
