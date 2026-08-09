from __future__ import annotations

import asyncio
import json
import re
from unittest.mock import Mock

import pytest

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
    registered_tools = {
        tool.name for tool in asyncio.run(server.mcp.list_tools())
    }
    referenced_tools = set(re.findall(r"`([a-z][a-z0-9_]*)`", text))

    assert text.strip()
    assert referenced_tools
    assert referenced_tools <= registered_tools
