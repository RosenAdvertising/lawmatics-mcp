"""Offline reproductions of PUBLIC6 findings through real MCP/setup boundaries."""

import asyncio
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from mcp import ClientSession
from mcp.client._memory import InMemoryTransport

from lawmatics_mcp import client as client_module
from lawmatics_mcp import credentials, oauth_callback, private_storage, server
from lawmatics_mcp.setup import setup as setup_flow


@pytest.fixture
def boundary(monkeypatch):
    client = object.__new__(client_module.LawmaticsClient)
    calls = Mock(return_value={"id": "123"})
    for name in ("get", "put", "patch", "post", "_detail", "_send", "_request"):
        monkeypatch.setattr(client, name, calls, raising=False)
    monkeypatch.setattr(server, "LawmaticsClient", lambda: client)
    for name in ("_c", "_client", "get_client"):
        if hasattr(server, name):
            monkeypatch.setattr(server, name, lambda: client)

    async def invoke(name, arguments):
        async with InMemoryTransport(server.mcp) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(name, arguments)

    return lambda name, arguments: asyncio.run(invoke(name, arguments)), calls


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("create_matter", {}),
        ("update_matter", {"matter_id": "123", "matter_data": {}}),
        ("update_contact", {"contact_id": "123", "contact_data": {}}),
        ("update_task", {"task_id": "123", "task_data": {}}),
        ("update_note", {"note_id": "123", "note_data": {}}),
        ("update_event", {"event_id": "123", "event_data": {}}),
    ],
)
def test_empty_write_rejected_at_mcp_boundary(boundary, name, arguments):
    call, requests = boundary
    result = call(name, arguments)
    assert result.is_error, result
    assert any(
        "field" in item.text or "non-empty" in item.text for item in result.content
    )
    requests.assert_not_called()


@pytest.mark.parametrize("failure", ["directory_chmod", "fchmod", "replace", None])
@pytest.mark.parametrize("existing", [False, True])
def test_fallback_private_from_creation_and_fail_closed(
    monkeypatch, tmp_path, failure, existing
):
    target = tmp_path / "config" / ".env"
    if existing:
        target.parent.mkdir()
        target.write_text("old value")
    if "lawmatics" == "lawmatics":
        monkeypatch.setattr(credentials, "env_file", lambda: target)
    else:
        monkeypatch.setattr(credentials, "ENV_FILE", target)
        monkeypatch.setattr(credentials, "CONFIG_DIR", target.parent)
    observed = []
    real_open = os.open

    def opened(path, flags, mode=0o777):
        fd = real_open(path, flags, mode)
        observed.append((mode, os.fstat(fd).st_mode & 0o777))
        return fd

    monkeypatch.setattr(private_storage.os, "open", opened)

    def denied(*args, **kwargs):
        raise OSError("simulated permissions failure")

    if failure == "directory_chmod":
        monkeypatch.setattr(Path, "chmod", denied)
    elif failure:
        monkeypatch.setattr(private_storage.os, failure, denied)
    old_umask = os.umask(0o022)
    try:
        if failure:
            with pytest.raises(OSError):
                credentials._write_env_file({"TEST_VALUE": "dummy"})
            assert (
                target.read_text() == "old value" if existing else not target.exists()
            )
        else:
            credentials._write_env_file({"TEST_VALUE": "dummy"})
            assert target.stat().st_mode & 0o777 == 0o600
            assert target.parent.stat().st_mode & 0o777 == 0o700
    finally:
        os.umask(old_umask)
    assert all(mode == actual == 0o600 for mode, actual in observed)
    assert not list(target.parent.glob("..env.*")) if target.parent.exists() else True


@pytest.mark.parametrize(
    "suffix",
    [
        "?code=dummy",
        "?code=dummy&state=wrong",
        "?code=dummy&state=expected&state=expected",
        "?code=dummy&code=other&state=expected",
        "?state=expected",
        "?code=dummy&state=expected&error=denied",
        "?code=dummy&state=expected#fragment",
    ],
)
def test_missing_wrong_duplicate_state_or_code_rejected(suffix):
    with pytest.raises(ValueError):
        oauth_callback.redirect_code(
            "http://127.0.0.1:8124/callback" + suffix,
            "http://127.0.0.1:8124/callback",
            "expected",
        )


def test_state_randomness_and_valid_redirect():
    states = {oauth_callback.new_state() for _ in range(100)}
    assert len(states) == 100
    assert all(len(x) >= 43 for x in states)
    assert (
        oauth_callback.redirect_code(
            "http://127.0.0.1:8124/callback?code=dummy&state=expected",
            "http://127.0.0.1:8124/callback",
            "expected",
        )
        == "dummy"
    )
    with pytest.raises(ValueError):
        oauth_callback.redirect_code(
            "https://attacker.example/callback?code=dummy&state=expected",
            "http://127.0.0.1:8124/callback",
            "expected",
        )


@pytest.mark.parametrize("returned_state", [None, "wrong", "expected"])
def test_real_setup_checks_state_before_exchange(monkeypatch, returned_state, capsys):
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setattr(setup_flow, "new_state", lambda: "expected")
    monkeypatch.setattr(setup_flow.sys, "argv", ["setup"])
    events = []
    exchange = Mock(return_value={"access_token": "dummy"})
    code_query = "?code=dummy" + ("&state=" + returned_state if returned_state else "")

    class FakeHTTPServer:
        def __init__(self, address, handler):
            events.append(("bound", address))
            self.handler = handler

        def handle_request(self):
            import io

            handler = object.__new__(self.handler)
            handler.path = "/callback" + code_query
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            handler.wfile = io.BytesIO()
            handler.do_GET()
            if returned_state != "expected":
                raise ValueError("invalid callback")

        def server_close(self):
            events.append(("closed",))

    monkeypatch.setattr(oauth_callback, "HTTPServer", FakeHTTPServer)
    from types import SimpleNamespace

    prompts = iter(["dummy-id", ""])
    monkeypatch.setattr("builtins.input", lambda *a: next(prompts))
    monkeypatch.setattr(setup_flow, "getpass", lambda *a: "dummy")
    exchange.return_value = SimpleNamespace(
        status_code=200, json=lambda: {"access_token": "dummy"}
    )
    monkeypatch.setattr(setup_flow.requests, "post", exchange)
    monkeypatch.setattr(setup_flow.credentials, "set_many", lambda *a: None)
    monkeypatch.setattr("lawmatics_mcp.setup.verify.run_verify", lambda: None)
    if returned_state == "expected":
        setup_flow.main()
        exchange.assert_called_once()
    else:
        with pytest.raises(SystemExit) as exc:
            setup_flow.main()
        assert exc.value.code == 1
        exchange.assert_not_called()
    output = capsys.readouterr().out
    authorization = next(
        line.strip() for line in output.splitlines() if "response_type=code" in line
    )
    assert parse_qs(urlsplit(authorization).query)["state"] == ["expected"]
    assert events[0][0] == "bound"
    assert events[-1] == ("closed",)


@pytest.mark.parametrize(
    "redirect",
    [
        "https://example.com/oauth/callback",
        "http://attacker.example/callback",
        "http://127.0.0.1:8124/callback?x=1",
        "http://user@localhost:8124/callback",
    ],
)
def test_callback_rejects_unowned_destination(redirect):
    with pytest.raises(ValueError):
        oauth_callback.LoopbackCallback(redirect, "dummy")


def test_owned_loopback_listener_rejects_wrong_state_then_captures_code(monkeypatch):
    import concurrent.futures

    import requests

    real_server = oauth_callback.HTTPServer

    def ephemeral(address, handler):
        assert address == ("127.0.0.1", 8124)
        return real_server((address[0], 0), handler)

    monkeypatch.setattr(oauth_callback, "HTTPServer", ephemeral)
    with oauth_callback.LoopbackCallback(
        "http://127.0.0.1:8124/callback", "expected"
    ) as callback:
        port = callback.server.server_port
        callback.redirect_uri = f"http://127.0.0.1:{port}/callback"
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(callback.receive, 5)
            with requests.Session() as browser:
                browser.trust_env = False
                rejected = browser.get(
                    callback.redirect_uri + "?code=wrong&state=wrong", timeout=2
                )
                assert rejected.status_code == 400
                assert callback.code is None
                accepted = browser.get(
                    callback.redirect_uri + "?code=dummy&state=expected", timeout=2
                )
                assert accepted.status_code == 200
                assert future.result(timeout=3) == "dummy"
    assert callback.server.fileno() == -1
