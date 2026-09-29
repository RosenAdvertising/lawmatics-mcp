from __future__ import annotations

from types import SimpleNamespace

from lawmatics_mcp.setup import setup


def test_oauth_token_exchange_uses_a_finite_timeout(monkeypatch) -> None:
    prompts = iter(["client-id", "", "authorization-code"])
    saved_credentials: dict[str, str] = {}
    request: dict[str, object] = {}

    monkeypatch.setattr("builtins.input", lambda _prompt="": next(prompts))
    monkeypatch.setattr(setup, "getpass", lambda _prompt="": "client-secret")

    def post(url: str, *, data: dict[str, str], timeout: int):
        request.update(url=url, data=data, timeout=timeout)
        return SimpleNamespace(status_code=200, json=lambda: {"access_token": "token"})

    monkeypatch.setattr(setup.requests, "post", post)
    monkeypatch.setattr(setup.credentials, "set_many", saved_credentials.update)
    monkeypatch.setattr(setup.credentials, "storage_location", lambda: "test credentials")
    monkeypatch.setattr("lawmatics_mcp.setup.verify.run_verify", lambda: None)

    setup.main()

    assert request["timeout"] == 30
    assert saved_credentials["LAWMATICS_ACCESS_TOKEN"] == "token"
