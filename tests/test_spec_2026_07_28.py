"""Offline conformance regressions for the MCP 2026-07-28 migration."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx2 as httpx
from mcp import Client
from mcp.types import LATEST_PROTOCOL_VERSION
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from lawmatics_mcp import server

PROTOCOL_VERSION = "2026-07-28"
LEGACY_PROTOCOL_VERSION = "2025-11-25"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _modern_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    request_id: int = 1,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: protocol_version,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "lawmatics-spec-test", "version": "0"},
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "mcp-protocol-version": protocol_version,
        "mcp-method": method,
    }
    if method == "tools/call":
        headers["mcp-name"] = str(request_params["name"])
    elif method == "prompts/get":
        headers["mcp-name"] = str(request_params["name"])
    elif method == "resources/read":
        headers["mcp-name"] = str(request_params["uri"])
    return headers, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


async def _post_modern(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    header_overrides: dict[str, str] | None = None,
    omit_headers: set[str] | None = None,
) -> httpx.Response:
    app = server.mcp.streamable_http_app(
        host="0.0.0.0",
        stateless_http=True,
        json_response=True,
    )
    headers, body = _modern_request(
        method,
        params,
        protocol_version=protocol_version,
    )
    if header_overrides:
        headers.update(header_overrides)
    for header in omit_headers or set():
        headers.pop(header, None)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://spec-test",
        ) as client:
            return await client.post("/mcp", headers=headers, json=body)


def _result(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


def test_spec_check_pins_the_2026_revision() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "spec_check.py"), "--mcp-only"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Spec check: PASS" in result.stdout
    assert LATEST_PROTOCOL_VERSION == PROTOCOL_VERSION
    assert MODERN_PROTOCOL_VERSIONS == (PROTOCOL_VERSION,)


def test_modern_discovery_is_sessionless_and_declares_used_capabilities() -> None:
    response = asyncio.run(_post_modern("server/discover"))
    result = _result(response)

    assert "mcp-session-id" not in response.headers
    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert result["capabilities"] == {
        "prompts": {"listChanged": True},
        "resources": {"listChanged": True, "subscribe": True},
        "tools": {"listChanged": True},
    }
    assert "extensions" not in result["capabilities"]
    assert result["_meta"][SERVER_INFO_META_KEY]["name"] == "lawmatics"


def test_client_defaults_modern_and_keeps_legacy_negotiation() -> None:
    async def negotiate() -> tuple[str, str]:
        async with Client(server.mcp, cache=None) as modern:
            modern_version = modern.protocol_version
        async with Client(server.mcp, mode="legacy", cache=None) as legacy:
            legacy_version = legacy.protocol_version
        return modern_version, legacy_version

    modern_version, legacy_version = asyncio.run(negotiate())
    assert modern_version == PROTOCOL_VERSION
    assert legacy_version == LEGACY_PROTOCOL_VERSION


def test_cacheable_results_are_complete_private_and_deterministic() -> None:
    async def list_results() -> list[dict[str, Any]]:
        methods = (
            "tools/list",
            "tools/list",
            "prompts/list",
            "resources/list",
            "resources/templates/list",
        )
        return [_result(await _post_modern(method)) for method in methods]

    first_tools, second_tools, prompts, resources, templates = asyncio.run(
        list_results()
    )
    for result in (first_tools, second_tools, prompts, resources, templates):
        assert result["resultType"] == "complete"
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "private"

    first_names = [tool["name"] for tool in first_tools["tools"]]
    second_names = [tool["name"] for tool in second_tools["tools"]]
    assert first_names == second_names
    assert len(first_names) == 36
    assert all(tool["inputSchema"]["type"] == "object" for tool in first_tools["tools"])
    assert len(prompts["prompts"]) == 3
    assert [item["uri"] for item in resources["resources"]] == [
        "lawmatics://users",
        "lawmatics://custom-fields",
        "lawmatics://security-notes",
    ]
    assert templates["resourceTemplates"] == []


def test_list_tool_schemas_enforce_pages_and_expose_supported_sorting() -> None:
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    paginated = {
        "list_users",
        "list_matters",
        "list_contacts",
        "list_tasks",
        "list_notes",
        "list_events",
        "list_custom_fields",
        "list_interactions",
        "list_custom_emails",
        "list_forms",
        "list_form_entries",
    }
    sortable = {
        "list_users",
        "list_matters",
        "list_contacts",
        "list_tasks",
        "list_notes",
        "list_events",
        "list_interactions",
    }

    for name in paginated:
        assert tools[name].input_schema["properties"]["page"]["minimum"] == 1
    for name in sortable:
        properties = tools[name].input_schema["properties"]
        assert {"sort_by", "sort_order"} <= properties.keys()


def test_resource_read_and_tool_result_have_modern_result_fields(monkeypatch) -> None:
    class StubLawmaticsClient:
        def list_users(self, page: int = 1, fields: str = "") -> dict[str, Any]:
            return {"data": [{"id": "user-1"}], "page": page, "fields": fields}

        def list_task_statuses(self) -> dict[str, Any]:
            return {"data": [{"id": "open"}]}

    monkeypatch.setattr(server, "_client", StubLawmaticsClient)

    resource = asyncio.run(
        _post_modern("resources/read", {"uri": "lawmatics://users"})
    )
    resource_result = _result(resource)
    assert resource_result["resultType"] == "complete"
    assert resource_result["ttlMs"] == 0
    assert resource_result["cacheScope"] == "private"
    assert "user-1" in resource_result["contents"][0]["text"]

    tool = asyncio.run(
        _post_modern(
            "tools/call",
            {"name": "list_task_statuses", "arguments": {}},
        )
    )
    tool_result = _result(tool)
    assert tool_result["resultType"] == "complete"
    assert tool_result["isError"] is False
    assert tool_result["structuredContent"] == {"data": [{"id": "open"}]}


def test_resource_not_found_uses_invalid_params() -> None:
    missing = asyncio.run(
        _post_modern("resources/read", {"uri": "lawmatics://does-not-exist"})
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == -32602


def test_modern_http_requires_routing_and_protocol_headers() -> None:
    missing_method = asyncio.run(
        _post_modern("tools/list", omit_headers={"mcp-method"})
    )
    assert missing_method.status_code == 400
    assert missing_method.json()["error"]["code"] == -32020

    missing_name = asyncio.run(
        _post_modern(
            "tools/call",
            {"name": "list_task_statuses", "arguments": {}},
            omit_headers={"mcp-name"},
        )
    )
    assert missing_name.status_code == 400
    assert missing_name.json()["error"]["code"] == -32020

    missing_version = asyncio.run(
        _post_modern(
            "server/discover",
            omit_headers={"mcp-protocol-version"},
        )
    )
    assert missing_version.status_code == 200
    assert missing_version.json()["error"]["code"] == -32601


def test_modern_http_uses_renumbered_and_standard_method_errors() -> None:
    mismatch = asyncio.run(
        _post_modern(
            "tools/list",
            header_overrides={"mcp-method": "resources/list"},
        )
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == -32020

    unsupported = asyncio.run(
        _post_modern("tools/list", protocol_version="2099-01-01")
    )
    assert unsupported.status_code == 400
    assert unsupported.json()["error"] == {
        "code": -32022,
        "message": "Unsupported protocol version",
        "data": {
            "supported": [PROTOCOL_VERSION],
            "requested": "2099-01-01",
        },
    }

    unknown = asyncio.run(_post_modern("example/unknown"))
    assert unknown.status_code == 404
    assert unknown.json()["error"] == {
        "code": -32601,
        "message": "Method not found",
        "data": "example/unknown",
    }
