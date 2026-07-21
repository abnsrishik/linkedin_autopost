import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from config import LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REDIRECT_URI
from bot.db import init_db, save_tokens

PORT = int(urllib.parse.urlparse(LINKEDIN_REDIRECT_URI).port or 8080)
CODE = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global CODE
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            CODE = params["code"][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Success!</h1><p>Authorization code caught. Return to your terminal.</p>")
        else:
            self.send_response(400)
            self.end_headers()

def run_local_server():
    server = HTTPServer(('localhost', PORT), CallbackHandler)
    print(f"Waiting on callback redirection on http://localhost:{PORT}...")
    server.handle_request() # Single-request exit

def get_linkedin_pages(access_token):
    url = "https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee&role=ADMINISTRATOR"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(url, headers=headers).json()
    
    pages = []
    for item in res.get("elements", []):
        org_urn = item.get("organizationalTarget")
        if org_urn:
            pages.append(org_urn)
    return pages

def main():
    init_db()
    
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
        print("Please configure Client credentials in .env first.")
        sys.exit(1)

    scopes = "w_organization_social r_organization_social rw_organization_admin openid profile email"
    encoded_scopes = urllib.parse.quote(scopes)
    
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(LINKEDIN_REDIRECT_URI)}"
        f"&scope={encoded_scopes}"
        f"&state=autoposter_init"
    )
    
    print("\n=== LinkedIn OAuth Setup ===")
    print("Open the following link in your browser to sign in & authorize:")
    print("-" * 60)
    print(auth_url)
    print("-" * 60)
    
    run_local_server()
    
    if not CODE:
        print("Error: Authorization failed or did not provide a code.")
        sys.exit(1)
        
    print("\nExchanging Authorization Code for access & refresh tokens...")
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": CODE,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    res = requests.post(token_url, data=payload, headers=headers).json()
    if "access_token" not in res:
        print(f"Token generation failed: {res}")
        sys.exit(1)
        
    access_token = res["access_token"]
    refresh_token = res["refresh_token"]
    
    print("Fetching managed LinkedIn Company Pages...")
    pages = get_linkedin_pages(access_token)
    if not pages:
        print("Warning: No administered Company Pages found. Make sure you are an administrator of the page.")
        org_urn = input("Please manually enter your target Organization URN (e.g. urn:li:organization:12345): ").strip()
    else:
        print("\nAdministered LinkedIn Pages found:")
        for idx, page in enumerate(pages):
            print(f"[{idx}] {page}")
        choice = int(input("\nSelect page index to post to: "))
        org_urn = pages[choice]
        
    save_tokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=res["expires_in"],
        refresh_token_expires_in=res["refresh_token_expires_in"],
        org_urn=org_urn
    )
    
    print(f"\nConfiguration Saved in DB! Target Page: {org_urn}")

if __name__ == "__main__":
    main()