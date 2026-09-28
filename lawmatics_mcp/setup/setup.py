#!/usr/bin/env python3
"""Interactive OAuth setup for lawmatics-mcp."""

from __future__ import annotations

import os
import sys
from getpass import getpass
from urllib.parse import urlencode

import requests

from lawmatics_mcp import credentials
from lawmatics_mcp.client import AUTHORIZE_URL, DEFAULT_REDIRECT_URI, TOKEN_URL


def main() -> None:
    print("Lawmatics MCP OAuth Setup")
    print("=" * 40)
    print("Developer Settings must be enabled by support@lawmatics.com.")
    print("Create an app in Lawmatics, then enter its OAuth credentials here.")
    print()

    client_id = input("Lawmatics Client ID: ").strip()
    client_secret = getpass("Lawmatics Client Secret: ").strip()
    redirect_uri = input(
        f"Redirect URI [{DEFAULT_REDIRECT_URI}]: "
    ).strip() or DEFAULT_REDIRECT_URI

    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required.", file=sys.stderr)
        sys.exit(1)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(auth_params)}"
    print()
    print("Open this URL, approve the app, then paste the returned code:")
    print(auth_url)
    print()

    code = input("Authorization code: ").strip()
    if not code:
        print("Error: authorization code is required.", file=sys.stderr)
        sys.exit(1)

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    if resp.status_code != 200:
        print(f"Token exchange failed ({resp.status_code}).", file=sys.stderr)
        sys.exit(1)

    token_data = resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        print("Token exchange response did not contain access_token.", file=sys.stderr)
        sys.exit(1)

    credentials.set_many(
        {
            "LAWMATICS_CLIENT_ID": client_id,
            "LAWMATICS_CLIENT_SECRET": client_secret,
            "LAWMATICS_REDIRECT_URI": redirect_uri,
            "LAWMATICS_ACCESS_TOKEN": access_token,
        }
    )

    os.environ["LAWMATICS_ACCESS_TOKEN"] = access_token
    print()
    print(f"Credentials saved to {credentials.storage_location()} (0600).")
    print()

    try:
        from lawmatics_mcp.setup.verify import run_verify

        run_verify()
    except Exception as exc:  # noqa: BLE001
        print(f"Verification failed: {exc}", file=sys.stderr)
        print("Check your app settings and token, then try lawmatics-mcp-verify.")
        sys.exit(1)


if __name__ == "__main__":
    main()
