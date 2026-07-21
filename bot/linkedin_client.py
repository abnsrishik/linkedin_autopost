import time
import requests
from config import LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET
from bot.db import get_tokens, save_tokens

class LinkedInClient:
    def __init__(self):
        self.client_id = LINKEDIN_CLIENT_ID
        self.client_secret = LINKEDIN_CLIENT_SECRET

    def refresh_access_token_if_needed(self):
        token_data = get_tokens()
        if not token_data:
            raise Exception("No OAuth tokens found. Please run setup_linkedin_oauth.py first.")

        # Refresh if token is within 5 minutes of expiring
        if time.time() < (token_data["expires_at"] - 300):
            return token_data["access_token"]

        print("Refreshing LinkedIn access token...")
        url = "https://www.linkedin.com/oauth/v2/accessToken"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token_data["refresh_token"],
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to refresh access token: {response.status_code} - {response.text}")

        data = response.json()
        # Save refreshed token with standard durations
        save_tokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", token_data["refresh_token"]),
            expires_in=data["expires_in"],
            refresh_token_expires_in=data.get("refresh_token_expires_in", 31536000), # Default 1 yr if omitted
            org_urn=token_data["org_urn"]
        )
        return data["access_token"]

    def publish_post(self, commentary: str) -> str:
        access_token = self.refresh_access_token_if_needed()
        token_data = get_tokens()
        org_urn = token_data.get("org_urn")
        
        if not org_urn:
            raise Exception("No Organization URN linked in database.")

        url = "https://api.linkedin.com/rest/posts"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": "202506", # API Version
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        payload = {
            "author": org_urn,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": []
            },
            "lifecycleState": "PUBLISHED"
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 201:
            raise Exception(f"LinkedIn publication failed: {response.status_code} - {response.text}")

        # The post URN is returned in the x-restli-id header
        post_urn = response.headers.get("x-restli-id")
        return post_urn