#!/usr/bin/env python3
"""File-backed credential storage for lawmatics-mcp.

Lawmatics OAuth returns a non-expiring access token and no refresh token. This
package stores the OAuth client details and access token in
``~/.lawmatics-mcp/.env`` with restrictive permissions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

SERVICE_NAME = "lawmatics-mcp"
CONFIG_DIR_ENV = "LAWMATICS_MCP_CONFIG_DIR"


def config_dir() -> Path:
    """Return the Lawmatics MCP config directory.

    ``LAWMATICS_MCP_CONFIG_DIR`` is primarily for tests and managed runtimes that
    need to redirect credential storage away from the user's home directory.
    """

    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".lawmatics-mcp"


def env_file() -> Path:
    """Return the path to the Lawmatics MCP .env file."""

    return config_dir() / ".env"


def _parse_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file."""

    path = path or env_file()
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_file(values: dict[str, str], path: Path | None = None) -> None:
    """Write the .env file with 0600 permissions inside a 0700 directory."""

    path = path or env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_into_environ(keys: Iterable[str]) -> None:
    """Populate unset environment variables from ``~/.lawmatics-mcp/.env``."""

    load_dotenv(env_file(), override=False)
    values = _parse_env_file()
    for key in keys:
        if os.environ.get(key):
            continue
        value = values.get(key)
        if value:
            os.environ[key] = value


def get_secret(key: str, default: str = "") -> str:
    """Return an environment/config value by key."""

    load_into_environ([key])
    return os.environ.get(key, default)


def set_secret(key: str, value: str) -> None:
    """Persist one secret to the .env file."""

    values = _parse_env_file()
    values[key] = value
    _write_env_file(values)


def set_many(values: dict[str, str]) -> None:
    """Persist multiple secrets to the .env file."""

    existing = _parse_env_file()
    existing.update(values)
    _write_env_file(existing)


def storage_location() -> str:
    """Return a user-facing description of where credentials are stored."""

    return str(env_file())

