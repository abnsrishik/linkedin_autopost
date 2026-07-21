import time

import requests

from config import LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_VERSION
from bot.db import get_tokens, save_tokens


class LinkedInClient:
    def __init__(self):
        self.client_id = LINKEDIN_CLIENT_ID
        self.client_secret = LINKEDIN_CLIENT_SECRET

    def refresh_access_token_if_needed(self):
        token_data = get_tokens()
        if not token_data:
            raise Exception("No OAuth tokens found. Send /reauth or run setup_linkedin_oauth.py.")

        if time.time() < (token_data["expires_at"] - 300):
            return token_data["access_token"]

        if not token_data.get("refresh_token"):
            raise Exception("No refresh token available. Send /reauth to re-authorize.")

        if time.time() >= token_data["refresh_expires_at"]:
            raise Exception("LinkedIn refresh token expired. Send /reauth or run setup_linkedin_oauth.py again.")

        print("Refreshing LinkedIn access token...")
        url = "https://www.linkedin.com/oauth/v2/accessToken"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token_data["refresh_token"],
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Failed to refresh access token: {response.status_code} - {response.text}")

        data = response.json()
        save_tokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", token_data["refresh_token"]),
            expires_in=data["expires_in"],
            refresh_token_expires_in=data.get(
                "refresh_token_expires_in",
                max(0, token_data["refresh_expires_at"] - time.time()),
            ),
            author_urn=token_data["author_urn"],
            author_type="member",
        )
        return data["access_token"]

    def publish_post(self, commentary: str) -> str:
        access_token = self.refresh_access_token_if_needed()
        token_data = get_tokens()
        author_urn = token_data.get("author_urn")

        if not author_urn:
            raise Exception("No LinkedIn member author URN found. Please run setup_linkedin_oauth.py first.")
        if not author_urn.startswith("urn:li:person:"):
            raise Exception("LinkedIn author URN must be a person URN for personal profile posting.")

        url = "https://api.linkedin.com/rest/posts"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": LINKEDIN_VERSION,
        }
        payload = {
            "author": author_urn,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 201:
            raise Exception(f"LinkedIn publication failed: {response.status_code} - {response.text}")

        post_urn = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
        if not post_urn:
            raise Exception("LinkedIn publication succeeded but did not return X-RestLi-Id header.")
        return post_urn
