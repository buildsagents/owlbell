"""
One-time OAuth 2.0 setup for Gmail API.

Usage:
    python backend/integrations/gmail/setup_oauth.py

Prerequisites:
    1. Go to https://console.cloud.google.com/apis/credentials
    2. Create a project (or use existing)
    3. Enable Gmail API (https://console.cloud.google.com/apis/library/gmail.googleapis.com)
    4. Create OAuth 2.0 Client ID → "Desktop application"
    5. Download the JSON → save as client_secret.json in this directory
"""

import json
import os
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

DIR = Path(__file__).parent
CLIENT_SECRET_FILE = DIR / "client_secret.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"


def main():
    if not CLIENT_SECRET_FILE.exists():
        print(f"ERROR: {CLIENT_SECRET_FILE} not found.")
        print()
        print("Steps:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID → 'Desktop application'")
        print(f"  3. Download JSON → save as {CLIENT_SECRET_FILE}")
        return

    with open(CLIENT_SECRET_FILE) as f:
        creds = json.load(f)["installed"]

    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{AUTH_URL}?{urlencode(params)}"
    print(f"Opening browser for authorization...\n{url}")
    webbrowser.open(url)
    code = input("\nPaste the authorization code here: ").strip()

    import httpx

    resp = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    tokens = resp.json()
    if "refresh_token" not in tokens:
        print(f"ERROR: No refresh_token in response: {json.dumps(tokens, indent=2)}")
        print("Make sure you granted consent and used the correct client_id.")
        return

    print("\n=== ADD THESE TO RAILWAY ===")
    print(f"INTEGRATION_GMAIL_CLIENT_ID={client_id}")
    print(f"INTEGRATION_GMAIL_CLIENT_SECRET={client_secret}")
    print(f"INTEGRATION_GMAIL_REFRESH_TOKEN={tokens['refresh_token']}")
    print()
    print("Run:")
    print(f"  railway variables set INTEGRATION_GMAIL_CLIENT_ID={client_id} \\")
    print(f"    INTEGRATION_GMAIL_CLIENT_SECRET={client_secret} \\")
    print(f"    INTEGRATION_GMAIL_REFRESH_TOKEN={tokens['refresh_token']} \\")
    print("    --service owlbell-api")


if __name__ == "__main__":
    main()
