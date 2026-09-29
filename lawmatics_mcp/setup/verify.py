#!/usr/bin/env python3
"""Verify Lawmatics credentials by calling GET /v1/users/me."""

from __future__ import annotations

import sys

import requests

from lawmatics_mcp.client import (
    LawmaticsAuthError,
    LawmaticsClient,
    LawmaticsMissingCredentialsError,
)


def run_verify() -> dict:
    client = LawmaticsClient()
    result = client.get_current_user()
    data = result.get("data", result) if isinstance(result, dict) else {}
    attrs = data.get("attributes", {}) if isinstance(data, dict) else {}
    name = attrs.get("name") or "unknown"
    role = attrs.get("role") or "unknown"
    print("Connection successful.")
    print(f"User: {name}")
    print(f"Role: {role}")
    return result


def main() -> None:
    try:
        run_verify()
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, LawmaticsMissingCredentialsError | LawmaticsAuthError):
            message = str(exc)
        elif isinstance(exc, requests.Timeout):
            message = "Lawmatics verification timed out. Check connectivity and try lawmatics-mcp-verify again."
        elif isinstance(exc, requests.ConnectionError):
            message = "Could not connect to Lawmatics. Check connectivity and try lawmatics-mcp-verify again."
        else:
            message = "Lawmatics verification failed. Check credentials and connectivity, then try again."
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
