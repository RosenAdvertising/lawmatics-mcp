"""In-process Streamable HTTP checks for create_serve_app()."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest

from lawmatics_mcp import server

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
LOOPBACK_HOST = "127.0.0.1:8080"
ACCEPT = "application/json, text/event-stream"


def _request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    host: str = LOOPBACK_HOST,
    origin: str | None = None,
    session_id: str | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "lawmatics-http-test", "version": "0"},
    }
    headers = {
        "accept": ACCEPT,
        "content-type": "application/json",
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": method,
        "host": host,
    }
    if method in {"tools/call", "prompts/get"}:
        headers["mcp-name"] = str(request_params["name"])
    elif method == "resources/read":
        headers["mcp-name"] = str(request_params["uri"])
    if origin is not None:
        headers["origin"] = origin
    if session_id is not None:
        headers["mcp-session-id"] = session_id
    return headers, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": request_params,
    }


def _json_result(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


@asynccontextmanager
async def _http_client(app) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1",
        ) as client:
            yield client


async def _post(
    client: httpx.AsyncClient,
    method: str,
    params: dict[str, Any] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    headers, body = _request(method, params, **kwargs)
    return await client.post("/mcp", headers=headers, json=body)


def test_http_tools_list_matches_stdio_names_and_schemas() -> None:
    async def load() -> tuple[list[Any], httpx.Response]:
        stdio_tools = await server.mcp.list_tools()
        app = server.create_serve_app()
        async with _http_client(app) as client:
            response = await _post(client, "tools/list")
        return stdio_tools, response

    stdio_tools, response = asyncio.run(load())
    http_tools = {
        tool["name"]: tool["inputSchema"] for tool in _json_result(response)["tools"]
    }
    stdio = {
        tool.name: tool.model_dump(mode="json", by_alias=True)["inputSchema"]
        for tool in stdio_tools
    }
    assert http_tools == stdio


def test_read_tool_runs_over_http_against_vendor_mock(mock_requests) -> None:
    _calls, enqueue = mock_requests
    payload = {"data": [{"id": "status-1"}]}
    enqueue(json_data=payload)

    async def call() -> httpx.Response:
        app = server.create_serve_app()
        async with _http_client(app) as client:
            return await _post(
                client,
                "tools/call",
                {"name": "list_task_statuses", "arguments": {}},
            )

    result = _json_result(asyncio.run(call()))
    assert result["isError"] is False
    assert result["structuredContent"] == payload


def _record_exchange_isolation(
    connection, request, seen: list, violations: list
) -> None:
    """Note this exchange's connection and request state.

    A later exchange that sees the same objects, or a probe left on them,
    appends to ``violations`` instead of raising inside the SDK handler.
    """

    if "isolation_probe" in connection.state:
        violations.append("connection")
    else:
        connection.state["isolation_probe"] = id(connection)
    request_state = request.scope.get("state")
    if isinstance(request_state, dict) and "isolation_probe" in request_state:
        violations.append("request")
    else:
        request.state.isolation_probe = id(request)
    seen.append((id(connection), id(connection.state), id(request.scope["state"])))


def _assert_exchanges_isolated(seen: list, violations: list) -> None:
    assert violations == [], violations
    assert len(seen) == 2
    connections, connection_states, request_states = zip(*seen, strict=True)
    assert len(set(connections)) == 2
    assert len(set(connection_states)) == 2
    assert len(set(request_states)) == 2


def test_responses_carry_no_session_and_requests_share_none(monkeypatch) -> None:
    from mcp.server import _streamable_http_modern as modern

    seen: list[tuple[int, int, int]] = []
    violations: list[str] = []
    original = modern.serve_one

    async def tracking_serve_one(
        mcp_server, dctx, method, params, *, connection, lifespan_state
    ):
        _record_exchange_isolation(
            connection,
            dctx.message_metadata.request_context,
            seen,
            violations,
        )
        return await original(
            mcp_server,
            dctx,
            method,
            params,
            connection=connection,
            lifespan_state=lifespan_state,
        )

    monkeypatch.setattr(modern, "serve_one", tracking_serve_one)

    async def call() -> tuple[httpx.Response, httpx.Response]:
        app = server.create_serve_app()
        async with _http_client(app) as client:
            first = await _post(client, "tools/list")
            second = await _post(client, "tools/list", session_id="stale-session")
            return first, second

    first, second = asyncio.run(call())
    first_names = [tool["name"] for tool in _json_result(first)["tools"]]
    second_names = [tool["name"] for tool in _json_result(second)["tools"]]
    assert first_names == second_names
    assert first.headers.get("mcp-session-id") is None
    assert second.headers.get("mcp-session-id") is None
    _assert_exchanges_isolated(seen, violations)


def test_bogus_transport_exits_and_default_stays_stdio(monkeypatch) -> None:
    monkeypatch.setenv("LAWMATICS_MCP_TRANSPORT", "bogus")
    with pytest.raises(SystemExit, match="stdio") as caught:
        server.main()
    assert "streamable-http" in str(caught.value)

    monkeypatch.delenv("LAWMATICS_MCP_TRANSPORT", raising=False)
    ran: list[str] = []
    monkeypatch.setattr(server.mcp, "run", lambda *args, **kwargs: ran.append("stdio"))
    assert server._requested_transport() == "stdio"
    server.main()
    assert ran == ["stdio"]


def test_allowed_hosts_refuse_another_host_and_bad_origin_is_403(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LAWMATICS_MCP_HOST", "10.1.2.3")
    monkeypatch.setenv("LAWMATICS_MCP_ALLOWED_HOSTS", "mcp.example:8080")
    monkeypatch.setenv("LAWMATICS_MCP_ALLOWED_ORIGINS", "https://app.example")

    async def checks() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        app = server.create_serve_app()
        async with _http_client(app) as client:
            other_host = await _post(client, "tools/list", host="other.example")
            bad_origin = await _post(
                client,
                "tools/list",
                host="mcp.example:8080",
                origin="https://evil.example",
            )
            allowed = await _post(
                client,
                "tools/list",
                host="mcp.example:8080",
                origin="https://app.example",
            )
            return other_host, bad_origin, allowed

    other_host, bad_origin, allowed = asyncio.run(checks())
    assert other_host.status_code == 421
    assert bad_origin.status_code == 403
    assert allowed.status_code == 200


def test_non_loopback_host_without_allowed_hosts_exits(monkeypatch) -> None:
    monkeypatch.setenv("LAWMATICS_MCP_HOST", "10.1.2.3")
    monkeypatch.delenv("LAWMATICS_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SystemExit, match="LAWMATICS_MCP_ALLOWED_HOSTS"):
        server.create_serve_app()


def test_get_and_delete_return_405_and_discover_names_server_version() -> None:
    async def checks() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        app = server.create_serve_app()
        async with _http_client(app) as client:
            common = {
                "host": LOOPBACK_HOST,
                "accept": ACCEPT,
                "mcp-protocol-version": PROTOCOL_VERSION,
            }
            get_response = await client.get("/mcp", headers=common)
            delete_response = await client.delete("/mcp", headers=common)
            headers, body = _request("server/discover")
            discover = await client.post("/mcp", headers=headers, json=body)
            return get_response, delete_response, discover

    get_response, delete_response, discover = asyncio.run(checks())
    assert get_response.status_code == 405
    assert delete_response.status_code == 405
    result = _json_result(discover)
    assert PROTOCOL_VERSION in result["supportedVersions"]
    version = result["_meta"][SERVER_INFO_META_KEY]["version"]
    assert isinstance(version, str) and version


def test_stateless_lifespan_runs_once_for_two_requests(monkeypatch) -> None:
    """The session manager enters lifespan once for the app, then reuses it."""

    events: list[str] = []

    @asynccontextmanager
    async def counting(_app):
        events.append("enter")
        yield {}
        events.append("exit")

    monkeypatch.setattr(server.mcp._lowlevel_server, "lifespan", counting)

    async def two_requests() -> None:
        app = server.create_serve_app()
        async with _http_client(app) as client:
            first = await _post(client, "tools/list")
            second = await _post(client, "tools/list")
            assert first.status_code == 200
            assert second.status_code == 200

    asyncio.run(two_requests())
    assert events == ["enter", "exit"]


def test_empty_transport_selects_stdio(monkeypatch) -> None:
    """A set-but-empty or whitespace LAWMATICS_MCP_TRANSPORT means stdio (F3)."""
    ran: list[str] = []
    monkeypatch.setattr(server.mcp, "run", lambda *args, **kwargs: ran.append("stdio"))
    for value in ("", "   "):
        monkeypatch.setenv("LAWMATICS_MCP_TRANSPORT", value)
        assert server._requested_transport() == "stdio"
        server.main()
    assert ran == ["stdio", "stdio"]


def test_empty_host_yields_loopback_and_never_reaches_uvicorn(monkeypatch) -> None:
    """A set-but-empty or whitespace LAWMATICS_MCP_HOST means 127.0.0.1 (F4)."""
    monkeypatch.delenv("LAWMATICS_MCP_ALLOWED_HOSTS", raising=False)
    for value in ("", "   "):
        monkeypatch.setenv("LAWMATICS_MCP_HOST", value)
        assert server._host() == "127.0.0.1"
        assert server._transport_security() is None


def test_uppercase_localhost_host_is_not_loopback(monkeypatch) -> None:
    """_host() keeps spelling; LOCALHOST is non-loopback and fails closed (F7)."""
    monkeypatch.setenv("LAWMATICS_MCP_HOST", "LOCALHOST")
    monkeypatch.delenv("LAWMATICS_MCP_ALLOWED_HOSTS", raising=False)
    assert server._host() == "LOCALHOST"
    with pytest.raises(SystemExit, match="LAWMATICS_MCP_ALLOWED_HOSTS"):
        server.create_serve_app()


def test_import_succeeds_with_missing_distribution() -> None:
    """Import must survive when the lawmatics distribution is not installed (F8)."""
    repo_root = Path(__file__).resolve().parent.parent
    code = (
        "import importlib.metadata\n"
        "_real_version = importlib.metadata.version\n"
        "def _raise(name):\n"
        "    if name in ('lawmatics-mcp', 'lawmatics_mcp'):\n"
        "        raise importlib.metadata.PackageNotFoundError(name)\n"
        "    return _real_version(name)\n"
        "importlib.metadata.version = _raise\n"
        "import lawmatics_mcp.server\n"
        "print('server-imported')\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(repo_root),
        "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
    }
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "server-imported" in result.stdout
