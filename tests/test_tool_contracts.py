from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import pytest

from lawmatics_mcp import server
from lawmatics_mcp.client import build_list_params


@dataclass(frozen=True)
class ToolContract:
    name: str
    method: str
    path: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] | None = None
    body: Any = None
    auth: bool = True


def _path(url: str) -> str:
    return urlparse(url).path


def _assert_request(
    call: dict[str, Any],
    *,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: Any = None,
    auth: bool = True,
) -> None:
    assert call["method"] == method
    assert _path(call["url"]) == path
    assert call["params"] == ({} if params is None else params)
    assert call["json"] == body
    if auth:
        assert call["headers"]["Authorization"] == "Bearer test-token"
    else:
        assert "Authorization" not in call["headers"]


TOOL_CONTRACTS = [
    ToolContract("get_current_user", "GET", "/v1/users/me"),
    ToolContract("list_users", "GET", "/v1/users", params={"page": 1}),
    ToolContract("get_user", "GET", "/v1/users/user-123", args=("user-123",)),
    ToolContract("list_matters", "GET", "/v1/prospects", params={"page": 1}),
    ToolContract("get_matter", "GET", "/v1/prospects/matter-123", args=("matter-123",)),
    ToolContract(
        "create_matter",
        "POST",
        "/v1/prospects",
        kwargs={
            "case_title": "Estate intake",
            "contact_id": "contact-123",
            "estimated_value_cents": 12345,
            "tags": ["vip", "probate"],
            "extra_fields": {
                "actual_value_cents": 67890,
                "lead_cost_cents": 2500,
            },
        },
        body={
            "case_title": "Estate intake",
            "contact_id": "contact-123",
            "estimated_value_cents": 12345,
            "tags": ["vip", "probate"],
            "actual_value_cents": 67890,
            "lead_cost_cents": 2500,
        },
    ),
    ToolContract(
        "update_matter",
        "PUT",
        "/v1/prospects/matter-123",
        args=("matter-123", {"case_title": "Updated", "actual_value_cents": 5000}),
        body={"case_title": "Updated", "actual_value_cents": 5000},
    ),
    ToolContract(
        "find_matter",
        "GET",
        "/v1/prospects/find_by_email/ada%2Blaw%40example.com",
        kwargs={"email": "ada+law@example.com"},
    ),
    ToolContract("list_contacts", "GET", "/v1/contacts", params={"page": 1}),
    ToolContract("get_contact", "GET", "/v1/contacts/contact-123", args=("contact-123",)),
    ToolContract(
        "create_contact",
        "POST",
        "/v1/contacts",
        args=(
            "Ada",
            "Lovelace",
            "ada@example.com",
            "+1 555 0100",
            [{"name": "Intake", "body": "Called after hours"}],
        ),
        body={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "phone": "+1 555 0100",
            "notes": [{"name": "Intake", "body": "Called after hours"}],
        },
    ),
    ToolContract(
        "update_contact",
        "PUT",
        "/v1/contacts/contact-123",
        args=("contact-123", {"email": "new@example.com"}),
        body={"email": "new@example.com"},
    ),
    ToolContract(
        "list_tasks",
        "GET",
        "/v1/tasks",
        kwargs={
            "matter_id": "matter-123",
            "contact_id": "contact-123",
            "company_id": "company-123",
            "user_id": "user-123",
        },
        params={
            "page": 1,
            "matter_id": "matter-123",
            "contact_id": "contact-123",
            "company_id": "company-123",
            "user_id": "user-123",
        },
    ),
    ToolContract("get_task", "GET", "/v1/tasks/task-123", args=("task-123",)),
    ToolContract(
        "create_task",
        "POST",
        "/v1/tasks",
        kwargs={
            "name": "Review intake",
            "description": "Confirm facts",
            "due_date": "2026-07-04",
            "user_ids": ["user-123"],
            "priority": "high",
            "taskable_type": "Prospect",
            "taskable_id": "matter-123",
            "tag_ids": ["tag-123"],
        },
        body={
            "name": "Review intake",
            "description": "Confirm facts",
            "due_date": "2026-07-04",
            "user_ids": ["user-123"],
            "priority": "high",
            "taskable_type": "Prospect",
            "taskable_id": "matter-123",
            "tag_ids": ["tag-123"],
        },
    ),
    ToolContract(
        "update_task",
        "PUT",
        "/v1/tasks/task-123",
        args=("task-123", {"priority": "low", "done": False}),
        body={"priority": "low", "done": False},
    ),
    ToolContract(
        "complete_task",
        "PUT",
        "/v1/tasks/task-123",
        args=("task-123",),
        body={"done": True},
    ),
    ToolContract("list_task_statuses", "GET", "/v1/task_statuses"),
    ToolContract("list_notes", "GET", "/v1/notes", params={"page": 1}),
    ToolContract("get_note", "GET", "/v1/notes/note-123", args=("note-123",)),
    ToolContract(
        "create_note",
        "POST",
        "/v1/notes",
        args=("Call summary", "Client called back.", "Prospect", "matter-123"),
        body={
            "name": "Call summary",
            "body": "Client called back.",
            "notable_type": "Prospect",
            "notable_id": "matter-123",
        },
    ),
    ToolContract(
        "update_note",
        "PUT",
        "/v1/notes/note-123",
        args=("note-123", {"name": "Renamed", "body": "Updated body"}),
        body={"name": "Renamed", "body": "Updated body"},
    ),
    ToolContract("list_events", "GET", "/v1/events", params={"page": 1}),
    ToolContract("get_event", "GET", "/v1/events/event-123", args=("event-123",)),
    ToolContract(
        "create_event",
        "POST",
        "/v1/events",
        kwargs={
            "name": "Strategy meeting",
            "start_date": "2026-07-04T09:00:00Z",
            "end_date": "2026-07-04T10:00:00Z",
            "eventable_type": "Prospect",
            "eventable_id": "matter-123",
            "user_ids": ["user-123"],
            "all_day": True,
            "time_zone": "America/New_York",
            "reminder_type": "minutes",
            "reminder_delay_length": 15,
            "send_invites": False,
            "event_type_id": "event-type-123",
        },
        body={
            "name": "Strategy meeting",
            "start_date": "2026-07-04T09:00:00Z",
            "end_date": "2026-07-04T10:00:00Z",
            "eventable_type": "Prospect",
            "eventable_id": "matter-123",
            "user_ids": ["user-123"],
            "all_day": True,
            "time_zone": "America/New_York",
            "reminder_type": "minutes",
            "reminder_delay_length": 15,
            "send_invites": False,
            "event_type_id": "event-type-123",
        },
    ),
    ToolContract(
        "update_event",
        "PUT",
        "/v1/events/event-123",
        args=("event-123", {"name": "Updated event", "send_invites": False}),
        body={"name": "Updated event", "send_invites": False},
    ),
    ToolContract(
        "list_custom_fields",
        "GET",
        "/v1/custom_fields",
        kwargs={"fields": "all", "page": 2},
        params={"fields": "all", "page": 2},
    ),
    ToolContract(
        "get_custom_field",
        "GET",
        "/v1/custom_fields/custom-field-123",
        args=("custom-field-123",),
    ),
    ToolContract("list_interactions", "GET", "/v1/interactions", params={"page": 1}),
    ToolContract(
        "create_interaction",
        "POST",
        "/v1/interactions",
        kwargs={
            "interaction_type": "Call",
            "body": "Discussed intake",
            "happened_at": "2026-07-04T12:00:00Z",
            "interactable_type": "Prospect",
            "interactable_id": "matter-123",
            "created_by_id": "user-123",
        },
        body={
            "interaction_type": "Call",
            "body": "Discussed intake",
            "happened_at": "2026-07-04T12:00:00Z",
            "interactable_type": "Prospect",
            "interactable_id": "matter-123",
            "created_by_id": "user-123",
        },
    ),
    ToolContract(
        "list_custom_emails",
        "GET",
        "/v1/custom_emails",
        kwargs={"page": 2},
        params={"page": 2},
    ),
    ToolContract(
        "get_custom_email",
        "GET",
        "/v1/custom_emails/custom-email-123",
        args=("custom-email-123",),
    ),
    ToolContract("list_forms", "GET", "/v1/forms", kwargs={"page": 2}, params={"page": 2}),
    ToolContract(
        "get_form",
        "GET",
        "/v1/forms/form-uuid-123",
        args=("form-uuid-123",),
        params={"fields": "all"},
    ),
    ToolContract(
        "list_form_entries",
        "GET",
        "/v1/forms/form-uuid-123/entries",
        kwargs={"form_uuid": "form-uuid-123", "page": 2},
        params={"page": 2},
    ),
    ToolContract(
        "submit_form",
        "POST",
        "/v1/forms/form-uuid-123/submit",
        kwargs={
            "form_uuid": "form-uuid-123",
            "fields": {"first_name": "Ada", "custom_field_2263": "yes"},
            "utm_source": "google",
            "utm_campaign": "summer",
            "referring_url": "https://example.com/intake",
        },
        body={
            "first_name": "Ada",
            "custom_field_2263": "yes",
            "utm_source": "google",
            "utm_campaign": "summer",
            "referring_url": "https://example.com/intake",
        },
        auth=False,
    ),
]


@pytest.mark.parametrize("case", TOOL_CONTRACTS, ids=lambda case: case.name)
def test_each_registered_tool_http_contract_and_response_passthrough(
    case: ToolContract, mock_requests
) -> None:
    calls, enqueue = mock_requests
    envelope = {"data": {"id": case.name}, "meta": {"contract": "unchanged"}}
    enqueue(json_data=envelope)

    result = getattr(server, case.name)(*case.args, **case.kwargs)

    assert result is envelope
    assert len(calls) == 1
    _assert_request(
        calls[0],
        method=case.method,
        path=case.path,
        params=case.params,
        body=case.body,
        auth=case.auth,
    )


STANDARD_LIST_TOOL_CASES = [
    ("list_users", {}, "/v1/users", {}),
    ("list_matters", {}, "/v1/prospects", {}),
    ("list_contacts", {}, "/v1/contacts", {}),
    (
        "list_tasks",
        {
            "matter_id": "matter-123",
            "contact_id": "contact-123",
            "company_id": "company-123",
            "user_id": "user-123",
        },
        "/v1/tasks",
        {
            "matter_id": "matter-123",
            "contact_id": "contact-123",
            "company_id": "company-123",
            "user_id": "user-123",
        },
    ),
    ("list_notes", {}, "/v1/notes", {}),
    ("list_events", {}, "/v1/events", {}),
    ("list_interactions", {}, "/v1/interactions", {}),
]


@pytest.mark.parametrize(
    ("tool_name", "extra_kwargs", "path", "extra_params"),
    STANDARD_LIST_TOOL_CASES,
    ids=[case[0] for case in STANDARD_LIST_TOOL_CASES],
)
def test_standard_list_tools_send_full_shared_list_param_surface(
    tool_name: str,
    extra_kwargs: dict[str, Any],
    path: str,
    extra_params: dict[str, Any],
    mock_requests,
) -> None:
    calls, enqueue = mock_requests
    enqueue()

    getattr(server, tool_name)(
        page=3,
        fields="first_name,actual_value_cents",
        sort_by="actual_value_cents",
        sort_order="asc",
        filter_by="actual_value_cents",
        filter_on="10000",
        filter_with="<=",
        **extra_kwargs,
    )

    expected = {
        "page": 3,
        "fields": "first_name,actual_value_cents",
        "sort_by": "actual_value_cents",
        "sort_order": "asc",
        "filter_by": "actual_value_cents",
        "filter_on": "10000",
        "filter_with": "<=",
        **extra_params,
    }
    _assert_request(calls[0], method="GET", path=path, params=expected)


@pytest.mark.parametrize(
    ("tool_name", "path"),
    [
        ("list_users", "/v1/users"),
        ("list_matters", "/v1/prospects"),
        ("list_contacts", "/v1/contacts"),
        ("list_tasks", "/v1/tasks"),
        ("list_notes", "/v1/notes"),
        ("list_events", "/v1/events"),
        ("list_interactions", "/v1/interactions"),
    ],
)
def test_standard_list_tools_omit_unsupplied_optional_params(
    tool_name: str, path: str, mock_requests
) -> None:
    calls, enqueue = mock_requests
    enqueue()

    getattr(server, tool_name)()

    _assert_request(calls[0], method="GET", path=path, params={"page": 1})
    for optional in ("fields", "sort_by", "sort_order", "filter_by", "filter_on", "filter_with"):
        assert optional not in calls[0]["params"]


@pytest.mark.parametrize(
    ("tool_name", "kwargs", "path"),
    [
        ("list_custom_fields", {"fields": "all", "page": 4}, "/v1/custom_fields"),
        ("list_custom_emails", {"page": 4}, "/v1/custom_emails"),
        ("list_forms", {"page": 4}, "/v1/forms"),
        ("list_form_entries", {"form_uuid": "form-uuid-123", "page": 4}, "/v1/forms/form-uuid-123/entries"),
    ],
)
def test_paginated_read_only_list_tools_send_documented_page_params(
    tool_name: str, kwargs: dict[str, Any], path: str, mock_requests
) -> None:
    calls, enqueue = mock_requests
    enqueue()

    getattr(server, tool_name)(**kwargs)

    expected = {"page": 4}
    if tool_name == "list_custom_fields":
        expected["fields"] = "all"
    _assert_request(calls[0], method="GET", path=path, params=expected)


@pytest.mark.parametrize(
    ("tool_name", "id_kwarg", "path"),
    [
        ("get_user", "user_id", "/v1/users/user-123"),
        ("get_matter", "matter_id", "/v1/prospects/matter-123"),
        ("get_contact", "contact_id", "/v1/contacts/contact-123"),
        ("get_task", "task_id", "/v1/tasks/task-123"),
        ("get_note", "note_id", "/v1/notes/note-123"),
        ("get_event", "event_id", "/v1/events/event-123"),
    ],
)
def test_single_resource_tools_send_fields_only_when_provided(
    tool_name: str, id_kwarg: str, path: str, mock_requests
) -> None:
    calls, enqueue = mock_requests
    enqueue()

    getattr(server, tool_name)(**{id_kwarg: path.rsplit("/", 1)[-1], "fields": "all"})

    _assert_request(calls[0], method="GET", path=path, params={"fields": "all"})


@pytest.mark.parametrize(
    ("tool_name", "id_kwarg", "path"),
    [
        ("get_user", "user_id", "/v1/users/user-123"),
        ("get_matter", "matter_id", "/v1/prospects/matter-123"),
        ("get_contact", "contact_id", "/v1/contacts/contact-123"),
        ("get_task", "task_id", "/v1/tasks/task-123"),
        ("get_note", "note_id", "/v1/notes/note-123"),
        ("get_event", "event_id", "/v1/events/event-123"),
    ],
)
def test_single_resource_tools_omit_unsupplied_fields_param(
    tool_name: str, id_kwarg: str, path: str, mock_requests
) -> None:
    calls, enqueue = mock_requests
    enqueue()

    getattr(server, tool_name)(**{id_kwarg: path.rsplit("/", 1)[-1]})

    _assert_request(calls[0], method="GET", path=path)


@pytest.mark.parametrize(
    ("kwargs", "path"),
    [
        ({"phone": "+1 (828) 555-0199"}, "/v1/prospects/find_by_phone/%2B1%20%28828%29%20555-0199"),
        ({"email": "ada+intake@example.com"}, "/v1/prospects/find_by_email/ada%2Bintake%40example.com"),
        ({"name": "Ada Lovelace"}, "/v1/prospects/find_by_name/Ada%20Lovelace"),
    ],
)
def test_find_matter_routes_by_path_with_url_encoded_values(
    kwargs: dict[str, str], path: str, mock_requests
) -> None:
    calls, enqueue = mock_requests
    enqueue()

    server.find_matter(**kwargs)

    _assert_request(calls[0], method="GET", path=path)


@pytest.mark.parametrize(
    ("tool_name", "kwargs", "path", "body", "auth"),
    [
        (
            "create_matter",
            {"case_title": "Estate intake"},
            "/v1/prospects",
            {"case_title": "Estate intake"},
            True,
        ),
        (
            "create_contact",
            {"first_name": "Ada", "last_name": "Lovelace"},
            "/v1/contacts",
            {"first_name": "Ada", "last_name": "Lovelace"},
            True,
        ),
        (
            "create_task",
            {"name": "Review intake"},
            "/v1/tasks",
            {"name": "Review intake", "priority": "medium"},
            True,
        ),
        (
            "create_event",
            {
                "name": "Strategy meeting",
                "start_date": "2026-07-04T09:00:00Z",
                "end_date": "2026-07-04T10:00:00Z",
            },
            "/v1/events",
            {
                "name": "Strategy meeting",
                "start_date": "2026-07-04T09:00:00Z",
                "end_date": "2026-07-04T10:00:00Z",
                "all_day": False,
                "send_invites": True,
            },
            True,
        ),
        (
            "create_interaction",
            {
                "interaction_type": "Call",
                "body": "Discussed intake",
                "happened_at": "2026-07-04T12:00:00Z",
            },
            "/v1/interactions",
            {
                "interaction_type": "Call",
                "body": "Discussed intake",
                "happened_at": "2026-07-04T12:00:00Z",
                "interactable_type": "Prospect",
            },
            True,
        ),
        (
            "submit_form",
            {"form_uuid": "form-uuid-123", "fields": {"first_name": "Ada"}},
            "/v1/forms/form-uuid-123/submit",
            {"first_name": "Ada"},
            False,
        ),
    ],
)
def test_create_tools_omit_empty_optional_body_fields(
    tool_name: str,
    kwargs: dict[str, Any],
    path: str,
    body: dict[str, Any],
    auth: bool,
    mock_requests,
) -> None:
    calls, enqueue = mock_requests
    enqueue()

    getattr(server, tool_name)(**kwargs)

    _assert_request(calls[0], method="POST", path=path, body=body, auth=auth)


@pytest.mark.parametrize("operator", ["null", "not_null", "empty", "present", "blank"])
def test_filter_by_without_filter_on_allows_valueless_presence_operators(operator: str) -> None:
    assert build_list_params(filter_by="closed_at", filter_with=operator) == {
        "page": 1,
        "filter_by": "closed_at",
        "filter_with": operator,
    }


def test_filter_by_without_filter_on_rejects_value_requiring_operators() -> None:
    with pytest.raises(ValueError, match="filter_by requires filter_on"):
        build_list_params(filter_by="case_title", filter_with="like")


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"name": "Review", "priority": "urgent"}, "priority"),
        ({"name": "Review", "taskable_type": "Matter"}, "taskable_type"),
    ],
)
def test_create_task_enum_validation_fires_before_http(
    kwargs: dict[str, Any], match: str, mock_requests
) -> None:
    calls, _enqueue = mock_requests

    with pytest.raises(ValueError, match=match):
        server.create_task(**kwargs)

    assert calls == []


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"name": "Bad", "body": "Body", "notable_type": "Contact", "notable_id": "1"}, "notable_type"),
        (
            {
                "name": "Bad",
                "start_date": "2026-07-04T09:00:00Z",
                "end_date": "2026-07-04T10:00:00Z",
                "eventable_type": "Matter",
            },
            "eventable_type",
        ),
    ],
)
def test_polymorphic_enum_validation_fires_before_http(
    kwargs: dict[str, Any], match: str, mock_requests
) -> None:
    calls, _enqueue = mock_requests
    tool = server.create_note if "notable_type" in kwargs else server.create_event

    with pytest.raises(ValueError, match=match):
        tool(**kwargs)

    assert calls == []
