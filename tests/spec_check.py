#!/usr/bin/env python3
"""Offline guard for the MCP protocol revision targeted by lawmatics-mcp."""

from __future__ import annotations

import argparse

from mcp.types import LATEST_PROTOCOL_VERSION

EXPECTED_MCP_PROTOCOL_VERSION = "2026-07-28"


def check_mcp_revision() -> list[str]:
    """Return an actionable error when the SDK target drifts."""

    if LATEST_PROTOCOL_VERSION == EXPECTED_MCP_PROTOCOL_VERSION:
        return []
    return [
        "installed MCP SDK targets the wrong revision: "
        f"expected {EXPECTED_MCP_PROTOCOL_VERSION!r}, "
        f"got {LATEST_PROTOCOL_VERSION!r}"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="check the installed MCP protocol revision",
    )
    parser.parse_args()

    errors = check_mcp_revision()
    print(f"Spec check: {'FAIL' if errors else 'PASS'}")
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
