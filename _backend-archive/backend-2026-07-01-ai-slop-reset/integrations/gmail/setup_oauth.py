"""
One-time Gmail API OAuth setup — opens a local server for automatic redirect.
Run, click Allow in browser, done.
"""
import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

DIR = Path(__file__).parent
CLIENT_SECRET_FILE = DIR / "client_secret.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
ENV_VARS = {
    "INTEGRATION_GMAIL_CLIENT_ID": "",
    "INTEGRATION_GMAIL_CLIENT_SECRET": "",
    "INTEGRATION_GMAIL_REFRESH_TOKEN": "",
}


def main():
    if not CLIENT_SECRET_FILE.exists():
        print(f"ERROR: Save the downloaded JSON as {CLIENT_SECRET_FILE}")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    print("\n=== ADD THESE TO RAILWAY ===")
    print(f"railway variables set INTEGRATION_GMAIL_CLIENT_ID={creds.client_id} \\")
    print(f"  INTEGRATION_GMAIL_CLIENT_SECRET={creds.client_secret} \\")
    print(f"  INTEGRATION_GMAIL_REFRESH_TOKEN={creds.refresh_token} \\")
    print("  --service owlbell-api")
    print()


if __name__ == "__main__":
    main()
