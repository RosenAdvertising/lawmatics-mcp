from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

from lawmatics_mcp.setup import setup, verify


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
    monkeypatch.setattr(
        setup.credentials, "storage_location", lambda: "test credentials"
    )
    monkeypatch.setattr("lawmatics_mcp.setup.verify.run_verify", lambda: None)

    setup.main()

    assert request["timeout"] == 30
    assert saved_credentials["LAWMATICS_ACCESS_TOKEN"] == "token"


def test_verify_entrypoint_no_credentials_exits_actionably(monkeypatch, capsys):
    monkeypatch.delenv("LAWMATICS_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(
        "lawmatics_mcp.client.credentials.load_into_environ", lambda _keys: None
    )
    try:
        verify.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("verify should fail without credentials")
    captured = capsys.readouterr()
    assert "Lawmatics access token not found. Run: lawmatics-mcp-setup" in captured.err
    assert "Traceback" not in captured.err


def test_verify_entrypoint_fake_bad_key_exits_without_vendor_text(monkeypatch, capsys):
    import requests

    def rejected(_self, *_args, **_kwargs):
        response = requests.Response()
        response.status_code = 401
        response._content = b"BAD-KEY vendor body https://evil.test"
        return response

    monkeypatch.setattr(requests.Session, "request", rejected)
    try:
        verify.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("verify should fail for rejected credentials")
    captured = capsys.readouterr()
    assert (
        "Lawmatics authentication was rejected or expired. Reauthorize with lawmatics-mcp-setup."
        in captured.err
    )
    assert "BAD-KEY" not in captured.err
    assert "Traceback" not in captured.err


def test_setup_entrypoint_empty_eof_fails_clearly(monkeypatch, capsys):
    monkeypatch.setattr(
        "builtins.input", lambda *_args: (_ for _ in ()).throw(EOFError())
    )
    try:
        setup.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("setup should fail on EOF")
    captured = capsys.readouterr()
    assert "setup input ended before OAuth credentials were provided" in captured.err
    assert "Traceback" not in captured.err


def test_setup_entrypoint_empty_values_fail_without_network(monkeypatch, capsys):
    prompts = iter(["", ""])
    monkeypatch.setattr("builtins.input", lambda *_args: next(prompts))
    monkeypatch.setattr(setup, "getpass", lambda *_args: "")
    try:
        setup.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("setup should fail when required inputs are empty")
    captured = capsys.readouterr()
    assert "Client ID and Client Secret are required" in captured.err
    assert "Traceback" not in captured.err


def test_setup_entrypoint_fake_oauth_rejection_is_masked(monkeypatch, capsys):
    prompts = iter(["fake-client-id", "", "fake-code"])
    request = {}
    monkeypatch.setattr("builtins.input", lambda *_args: next(prompts))
    monkeypatch.setattr(setup, "getpass", lambda *_args: "fake-client-secret")

    def rejected(url, *, data, timeout):
        request.update(url=url, data=data, timeout=timeout)
        return SimpleNamespace(status_code=401, text="VENDOR-SECRET https://evil.test")

    monkeypatch.setattr(setup.requests, "post", rejected)
    try:
        setup.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("setup should fail for a rejected fake OAuth code")
    captured = capsys.readouterr()
    assert request["timeout"] == 30
    assert captured.err == (
        "Token exchange failed (401). Check the client credentials and authorization code, "
        "then run lawmatics-mcp-setup again.\n"
    )
    assert "VENDOR-SECRET" not in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError])
def test_setup_transport_failure_warns_unknown_outcome(monkeypatch, capsys, failure):
    prompts = iter(["fake-id", "", "fake-code"])
    monkeypatch.setattr("builtins.input", lambda _: next(prompts))
    monkeypatch.setattr(setup, "getpass", lambda _: "fake-secret")
    monkeypatch.setattr(
        setup.requests,
        "post",
        lambda *a, **kw: (_ for _ in ()).throw(failure("PRIVATE")),
    )
    with pytest.raises(SystemExit) as error:
        setup.main()
    assert error.value.code == 1
    assert (
        capsys.readouterr().err
        == "Error: Lawmatics token exchange timed out or lost its connection; the outcome is unknown. Check whether authorization completed before retrying setup.\n"
    )


@pytest.mark.parametrize(
    "status, body, expected",
    [
        (
            403,
            {},
            "Error: Lawmatics access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawmatics-mcp-setup if so).",
        ),
        (
            200,
            ["PRIVATE"],
            "Error: Lawmatics token exchange returned an invalid response.",
        ),
    ],
)
def test_setup_permission_and_malformed_response_are_safe(
    monkeypatch, capsys, status, body, expected
):
    prompts = iter(["fake-id", "", "fake-code"])
    monkeypatch.setattr("builtins.input", lambda _: next(prompts))
    monkeypatch.setattr(setup, "getpass", lambda _: "fake-secret")
    monkeypatch.setattr(
        setup.requests,
        "post",
        lambda *a, **kw: SimpleNamespace(status_code=status, json=lambda: body),
    )
    with pytest.raises(SystemExit) as error:
        setup.main()
    assert error.value.code == 1
    assert capsys.readouterr().err == expected + "\n"
