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
from lawmatics_mcp.oauth_callback import LoopbackCallback, new_state, validate_redirect


def _run_setup() -> None:
    print("Lawmatics MCP OAuth Setup")
    print("=" * 40)
    print("Developer Settings must be enabled by support@lawmatics.com.")
    print("Create an app in Lawmatics, then enter its OAuth credentials here.")
    print()

    try:
        client_id = input("Lawmatics Client ID: ").strip()
        client_secret = getpass("Lawmatics Client Secret: ").strip()
        redirect_uri = (
            input(f"Redirect URI [{DEFAULT_REDIRECT_URI}]: ").strip()
            or DEFAULT_REDIRECT_URI
        )
    except (EOFError, KeyboardInterrupt):
        print(
            "Error: setup input ended before OAuth credentials were provided.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required.", file=sys.stderr)
        sys.exit(1)

    try:
        validate_redirect(redirect_uri)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    state = new_state()
    try:
        with LoopbackCallback(redirect_uri, state) as callback:
            auth_params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "state": state,
            }
            auth_url = f"{AUTHORIZE_URL}?{urlencode(auth_params)}"
            print("Register this exact redirect URI with the vendor:", redirect_uri)
            print("Open this URL and approve the app:")
            print(auth_url)
            code = callback.receive()
    except (OSError, ValueError):
        print(
            "Error: could not receive a valid OAuth callback. Check the registered redirect and restart setup.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=30,
            allow_redirects=False,
        )
    except (requests.Timeout, requests.ConnectionError):
        print(
            "Error: Lawmatics token exchange timed out or lost its connection; the outcome is unknown. Check whether authorization completed before retrying setup.",
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.RequestException:
        print(
            "Error: Lawmatics token exchange failed. Check the OAuth configuration and try setup again.",
            file=sys.stderr,
        )
        sys.exit(1)
    if resp.status_code == 403:
        print(
            "Error: Lawmatics access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawmatics-mcp-setup if so).",
            file=sys.stderr,
        )
        sys.exit(1)
    if resp.status_code != 200:
        print(
            f"Token exchange failed ({resp.status_code}). Check the client credentials and authorization code, then run lawmatics-mcp-setup again.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        token_data = resp.json()
        if not isinstance(token_data, dict):
            raise ValueError
    except (ValueError, requests.RequestException):
        print(
            "Error: Lawmatics token exchange returned an invalid response.",
            file=sys.stderr,
        )
        sys.exit(1)
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
    except Exception:  # noqa: BLE001
        print(
            "Verification failed. Check credentials and connectivity, then try lawmatics-mcp-verify.",
            file=sys.stderr,
        )
        print("Check your app settings and token, then try lawmatics-mcp-verify.")
        sys.exit(1)


def main() -> None:
    try:
        _run_setup()
    except Exception:
        print(
            "Error: Lawmatics setup failed. Check the OAuth configuration and credential storage, then run lawmatics-mcp-setup again.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
