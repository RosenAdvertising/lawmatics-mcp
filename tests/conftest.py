from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
import requests


@dataclass
class MockResponse:
    status_code: int = 200
    json_data: Any = field(default_factory=lambda: {"data": {"id": "ok"}})
    headers: dict[str, str] = field(default_factory=dict)
    text: str = "{}"

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self) -> Any:
        return self.json_data


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("LAWMATICS_MCP_CONFIG_DIR", str(tmp_path / ".lawmatics-mcp"))
    monkeypatch.setenv("LAWMATICS_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("LAWMATICS_CLIENT_ID", "client-id")
    monkeypatch.setenv("LAWMATICS_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("LAWMATICS_REDIRECT_URI", "http://localhost:8124/callback")


@pytest.fixture
def mock_requests(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []
    responses: list[MockResponse] = []

    def enqueue(
        status_code: int = 200,
        json_data: Any | None = None,
        headers: dict[str, str] | None = None,
        text: str = "{}",
    ) -> None:
        responses.append(
            MockResponse(
                status_code=status_code,
                json_data={"data": {"id": "ok"}} if json_data is None else json_data,
                headers=headers or {},
                text=text,
            )
        )

    def fake_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> MockResponse:
        calls.append(
            {
                "method": method,
                "url": url,
                "params": params or {},
                "json": json,
                "headers": headers or {},
                "kwargs": kwargs,
            }
        )
        if responses:
            return responses.pop(0)
        return MockResponse()

    monkeypatch.setattr(requests.sessions.Session, "request", fake_request)
    return calls, enqueue
