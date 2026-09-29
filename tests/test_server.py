from __future__ import annotations

import asyncio
import json
import re
from typing import Any, cast
from unittest.mock import Mock

import pytest
import requests
from mcp_types import CallToolRequestParams

from lawmatics_mcp import server


def test_server_imports_and_registers_all_36_tools():
    tools = asyncio.run(server.mcp.list_tools())
    tool_names = {tool.name for tool in tools}

    assert len(tool_names) == 36
    assert tool_names == {
        "get_current_user",
        "list_users",
        "get_user",
        "list_matters",
        "get_matter",
        "create_matter",
        "update_matter",
        "find_matter",
        "list_contacts",
        "get_contact",
        "create_contact",
        "update_contact",
        "list_tasks",
        "get_task",
        "create_task",
        "update_task",
        "complete_task",
        "list_task_statuses",
        "list_notes",
        "get_note",
        "create_note",
        "update_note",
        "list_events",
        "get_event",
        "create_event",
        "update_event",
        "list_custom_fields",
        "get_custom_field",
        "list_interactions",
        "create_interaction",
        "list_custom_emails",
        "get_custom_email",
        "list_forms",
        "get_form",
        "list_form_entries",
        "submit_form",
    }


def test_server_registers_exactly_three_resources_and_prompts():
    resources = asyncio.run(server.mcp.list_resources())
    prompts = asyncio.run(server.mcp.list_prompts())

    assert {(str(resource.uri), resource.mime_type) for resource in resources} == {
        ("lawmatics://users", "application/json"),
        ("lawmatics://custom-fields", "application/json"),
        ("lawmatics://security-notes", "text/markdown"),
    }
    assert {prompt.name for prompt in prompts} == {
        "triage_new_leads",
        "review_pipeline_health",
        "sweep_stale_follow_ups",
    }


def _call_tool(name: str, arguments: dict | None = None):
    return asyncio.run(
        server.mcp._handle_call_tool(
            cast(Any, None), CallToolRequestParams(name=name, arguments=arguments or {})
        )
    )


@pytest.mark.parametrize(
    ("status", "headers", "payload", "expected"),
    [
        (
            401,
            {},
            {},
            "Lawmatics authentication was rejected or expired. Reauthorize with lawmatics-mcp-setup.",
        ),
        (
            403,
            {},
            {},
            "Lawmatics authentication was rejected or expired. Reauthorize with lawmatics-mcp-setup.",
        ),
        (
            429,
            {"Retry-After": "60"},
            {},
            "Lawmatics rate limit reached. Retry after 60 seconds; this client does not auto-retry.",
        ),
        (
            429,
            {"Retry-After": "999999"},
            {},
            "Lawmatics rate limit reached. Retry after 3600 seconds; this client does not auto-retry.",
        ),
        (
            429,
            {"Retry-After": "1; https://attacker.invalid/token"},
            {},
            "Lawmatics rate limit reached. Retry later; this client does not auto-retry.",
        ),
        (
            404,
            {},
            {"error": "not_found"},
            "The requested Lawmatics record was not found (HTTP 404). Check the record ID.",
        ),
        (
            422,
            {},
            {"error": "customer person@example.test Bearer secret-token"},
            "Lawmatics API request failed (HTTP 422): request could not be processed.",
        ),
    ],
)
def test_http_failures_are_sanitized_in_actual_tool_result(
    status, headers, payload, expected, mock_requests
):
    _calls, enqueue = mock_requests
    enqueue(status_code=status, headers=headers, json_data=payload)

    result = _call_tool("get_current_user")

    text = result.content[0].text
    assert result.is_error is True
    assert text == expected
    assert "person@example.test" not in text
    assert "secret-token" not in text
    assert "attacker.invalid" not in text
    assert "Retry-After:" not in text


def test_missing_credentials_returns_setup_guidance(monkeypatch):
    monkeypatch.delenv("LAWMATICS_ACCESS_TOKEN", raising=False)

    result = _call_tool("get_current_user")

    assert result.is_error is True
    assert result.content[0].text == (
        "Lawmatics credentials are missing. Run lawmatics-mcp-setup or set LAWMATICS_ACCESS_TOKEN."
    )
    assert "private detail" not in result.content[0].text


def test_client_validation_is_actionable_and_argument_values_are_hidden(mock_requests):
    _calls, _enqueue = mock_requests
    result = _call_tool("list_users", {"sort_order": "person@example.test"})

    assert result.is_error is True
    assert (
        result.content[0].text
        == "Invalid arguments: sort_order must be 'asc' or 'desc'."
    )
    assert "person@example.test" not in result.content[0].text


def test_pydantic_validation_does_not_echo_input_or_unknown_argument_names():
    sentinel = "PII-SENTINEL-person@example.test"
    result = _call_tool("list_users", {"page": sentinel, "attacker-key": sentinel})
    text = result.content[0].text

    assert result.is_error is True
    assert text == "Invalid arguments: 'page' must be integer >= 1."
    assert sentinel not in text
    assert "attacker-key" not in text


def test_unknown_exception_result_and_logs_are_masked(monkeypatch, caplog):
    sentinel = "UNKNOWN-EXCEPTION-secret-token-person@example.test"

    def crash():
        raise RuntimeError(sentinel)

    monkeypatch.setattr(server, "_client", crash)
    result = _call_tool("get_current_user")

    assert result.is_error is True
    assert result.content[0].text == "Error executing tool get_current_user"
    assert sentinel not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    ("resource", "client_method", "expected_call", "payload"),
    [
        (
            server.users_resource,
            "list_users",
            {"page": 1, "fields": "all"},
            {"data": [{"id": "user-1", "name": "Intake Owner"}]},
        ),
        (
            server.custom_fields_resource,
            "list_custom_fields",
            {"fields": "all", "page": 1},
            {"data": [{"id": "field-1", "name": "Practice Area"}]},
        ),
    ],
)
def test_json_resources_call_the_client_and_return_valid_json(
    monkeypatch, resource, client_method, expected_call, payload
):
    client = Mock()
    getattr(client, client_method).return_value = payload
    monkeypatch.setattr(server, "_client", Mock(return_value=client))

    assert json.loads(resource()) == payload
    getattr(client, client_method).assert_called_once_with(**expected_call)


@pytest.mark.parametrize(
    ("prompt", "kwargs"),
    [
        (server.triage_new_leads, {}),
        (server.review_pipeline_health, {"days_stale": 21}),
        (server.sweep_stale_follow_ups, {"days_stale": 10}),
    ],
)
def test_prompts_are_non_empty_and_reference_only_registered_tools(prompt, kwargs):
    text = prompt(**kwargs)
    registered_tools = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    referenced_tools = set(re.findall(r"`([a-z][a-z0-9_]*)`", text))

    assert text.strip()
    assert referenced_tools
    assert referenced_tools <= registered_tools


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            {"code": "validation_error", "message": "private@example.test"},
            "Lawmatics API request failed (HTTP 422): request parameters were invalid.",
        ),
        (
            {"error": {"code": "conflict"}},
            "Lawmatics API request failed (HTTP 422): the request conflicts with the current record.",
        ),
        (
            {"code": ["private@example.test"], "error": {"code": {"secret": "value"}}},
            "Lawmatics API request failed (HTTP 422): request could not be processed.",
        ),
    ],
)
def test_http_reason_allowlist_and_malformed_codes(mock_requests, body, expected):
    _calls, enqueue = mock_requests
    enqueue(status_code=422, json_data=body)
    result = _call_tool("get_current_user")
    assert result.is_error is True
    assert result.content[0].text == expected


@pytest.mark.parametrize(
    ("error_type", "expected"),
    [
        (requests.Timeout, "Lawmatics request timed out. Retry shortly."),
        (
            requests.ConnectionError,
            "Could not connect to Lawmatics. Check connectivity and retry.",
        ),
        (ValueError, "Error executing tool get_current_user"),
    ],
)
def test_transport_failure_and_unknown_valueerror(
    monkeypatch, caplog, error_type, expected
):
    def fail(*_args, **_kwargs):
        raise error_type("private@example.test token=private")

    monkeypatch.setattr(requests.Session, "request", fail)
    result = _call_tool("get_current_user")
    assert result.is_error is True
    assert result.content[0].text == expected
    assert "private@example.test" not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (
            {"estimated_value_cents": "private@example.test"},
            "Invalid arguments: 'estimated_value_cents' must be integer or null.",
        ),
        (
            {"extra_fields": "private@example.test"},
            "Invalid arguments: 'extra_fields' must be object or null.",
        ),
    ],
)
def test_optional_argument_shapes(arguments, expected):
    result = _call_tool("create_matter", arguments)
    assert result.is_error is True
    assert result.content[0].text == expected
