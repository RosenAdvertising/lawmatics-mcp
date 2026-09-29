#!/usr/bin/env python3
"""Verify Lawmatics credentials by calling GET /v1/users/me."""

from __future__ import annotations

import sys

from lawmatics_mcp.client import LawmaticsClient


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
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
