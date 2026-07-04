from __future__ import annotations

import asyncio

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

