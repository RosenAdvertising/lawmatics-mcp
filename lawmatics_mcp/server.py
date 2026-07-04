#!/usr/bin/env python3
"""Lawmatics MCP server - 36 confirmed tools for legal CRM and intake."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from lawmatics_mcp.client import LawmaticsClient

mcp = FastMCP("lawmatics")


def _client() -> LawmaticsClient:
    return LawmaticsClient()


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@mcp.tool()
def get_current_user() -> dict[str, Any]:
    """Return the authenticated Lawmatics user via GET /users/me."""

    return _client().get_current_user()


@mcp.tool()
def list_users(
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """List firm users.

    Args:
        page: 1-indexed page number.
        fields: Comma-separated field list or "all".
        sort_by: Attribute to sort by.
        sort_order: "asc" or "desc".
        filter_by: Field name to filter on.
        filter_on: Filter value, unless using null/not_null.
        filter_with: Filter operator.
    """

    return _client().list_users(
        page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
    )


@mcp.tool()
def get_user(user_id: str, fields: str = "") -> dict[str, Any]:
    """Get one firm user.

    Args:
        user_id: Lawmatics user ID.
        fields: Comma-separated field list or "all".
    """

    return _client().get_user(user_id, fields)


# ---------------------------------------------------------------------------
# Matters (Lawmatics API resource: /prospects)
# ---------------------------------------------------------------------------


@mcp.tool()
def list_matters(
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """List matters. Matters are the /prospects resource in the Lawmatics API.

    Args:
        page: 1-indexed page number.
        fields: Comma-separated field list or "all".
        sort_by: Attribute to sort by.
        sort_order: "asc" or "desc".
        filter_by: Field name to filter on.
        filter_on: Filter value, unless using null/not_null.
        filter_with: Filter operator.
    """

    return _client().list_matters(
        page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
    )


@mcp.tool()
def get_matter(matter_id: str, fields: str = "") -> dict[str, Any]:
    """Get one matter via /prospects/{id}.

    Args:
        matter_id: Lawmatics prospect/matter ID.
        fields: Comma-separated field list or "all".
    """

    return _client().get_matter(matter_id, fields)


@mcp.tool()
def create_matter(
    case_title: str = "",
    contact_id: str = "",
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone: str = "",
    case_blurb: str = "",
    practice_area_id: str = "",
    stage_id: str = "",
    estimated_value_cents: int | None = None,
    tags: list[str] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a Lawmatics matter by POSTing to /prospects.

    Args:
        case_title: Matter case title.
        contact_id: Existing contact ID.
        first_name: Contact first name when creating/updating primary contact.
        last_name: Contact last name when creating/updating primary contact.
        email: Primary email.
        phone: Primary phone.
        case_blurb: Case description.
        practice_area_id: Practice area ID.
        stage_id: Stage ID.
        estimated_value_cents: Estimated matter value in integer cents.
        tags: Tag names; Lawmatics finds or creates them.
        extra_fields: Additional confirmed Lawmatics matter fields.
    """

    return _client().create_matter(
        case_title=case_title,
        contact_id=contact_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        case_blurb=case_blurb,
        practice_area_id=practice_area_id,
        stage_id=stage_id,
        estimated_value_cents=estimated_value_cents,
        tags=tags,
        extra_fields=extra_fields,
    )


@mcp.tool()
def update_matter(matter_id: str, matter_data: dict[str, Any]) -> dict[str, Any]:
    """Update a matter/prospect with a partial field dictionary.

    Args:
        matter_id: Lawmatics prospect/matter ID.
        matter_data: Fields to send in the PUT body.
    """

    return _client().update_matter(matter_id, matter_data)


@mcp.tool()
def find_matter(phone: str = "", email: str = "", name: str = "") -> dict[str, Any]:
    """Find one matter by exactly one phone, email, or name value.

    Args:
        phone: Phone value for /prospects/find_by_phone/{phone}.
        email: Email value for /prospects/find_by_email/{email}.
        name: Name value for /prospects/find_by_name/{name}.
    """

    return _client().find_matter(phone=phone, email=email, name=name)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@mcp.tool()
def list_contacts(
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """List contacts with standard Lawmatics list params.

    Args:
        page: 1-indexed page number.
        fields: Comma-separated field list or "all".
        sort_by: Attribute to sort by.
        sort_order: "asc" or "desc".
        filter_by: Field name to filter on.
        filter_on: Filter value, unless using null/not_null.
        filter_with: Filter operator.
    """

    return _client().list_contacts(
        page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
    )


@mcp.tool()
def get_contact(contact_id: str, fields: str = "") -> dict[str, Any]:
    """Get one contact.

    Args:
        contact_id: Lawmatics contact ID.
        fields: Comma-separated field list or "all".
    """

    return _client().get_contact(contact_id, fields)


@mcp.tool()
def create_contact(
    first_name: str,
    last_name: str,
    email: str = "",
    phone: str = "",
    notes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a contact.

    Args:
        first_name: Contact first name.
        last_name: Contact last name.
        email: Contact email.
        phone: Contact phone.
        notes: Optional list of {name, body} note dictionaries.
    """

    return _client().create_contact(first_name, last_name, email, phone, notes)


@mcp.tool()
def update_contact(contact_id: str, contact_data: dict[str, Any]) -> dict[str, Any]:
    """Update a contact with a partial field dictionary.

    Args:
        contact_id: Lawmatics contact ID.
        contact_data: Fields to send in the PUT body.
    """

    return _client().update_contact(contact_id, contact_data)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tasks(
    matter_id: str = "",
    contact_id: str = "",
    company_id: str = "",
    user_id: str = "",
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """List tasks with optional resource filters.

    Args:
        matter_id: Matter/prospect filter ID.
        contact_id: Contact filter ID.
        company_id: Company filter ID.
        user_id: Assigned user filter ID.
        page: 1-indexed page number.
        fields: Comma-separated field list or "all".
        sort_by: Attribute to sort by.
        sort_order: "asc" or "desc".
        filter_by: Field name to filter on.
        filter_on: Filter value, unless using null/not_null.
        filter_with: Filter operator.
    """

    return _client().list_tasks(
        matter_id,
        contact_id,
        company_id,
        user_id,
        page,
        fields,
        sort_by,
        sort_order,
        filter_by,
        filter_on,
        filter_with,
    )


@mcp.tool()
def get_task(task_id: str, fields: str = "") -> dict[str, Any]:
    """Get one task.

    Args:
        task_id: Lawmatics task ID.
        fields: Comma-separated field list or "all".
    """

    return _client().get_task(task_id, fields)


@mcp.tool()
def create_task(
    name: str,
    description: str = "",
    due_date: str = "",
    user_ids: list[str] | None = None,
    priority: str = "medium",
    taskable_type: str = "",
    taskable_id: str = "",
    tag_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create a task.

    Args:
        name: Task name.
        description: Task description.
        due_date: Due date as ISO8601 or MM/DD/YYYY.
        user_ids: Assigned user IDs.
        priority: One of high, medium, low.
        taskable_type: Optional Prospect, Contact, Company, or Client.
        taskable_id: ID for the taskable record.
        tag_ids: Tag IDs to apply.
    """

    return _client().create_task(
        name, description, due_date, user_ids, priority, taskable_type, taskable_id, tag_ids
    )


@mcp.tool()
def update_task(task_id: str, task_data: dict[str, Any]) -> dict[str, Any]:
    """Update a task with a partial field dictionary.

    Args:
        task_id: Lawmatics task ID.
        task_data: Fields to send in the PUT body.
    """

    return _client().update_task(task_id, task_data)


@mcp.tool()
def complete_task(task_id: str) -> dict[str, Any]:
    """Mark a task complete by sending {done: true}.

    Args:
        task_id: Lawmatics task ID.
    """

    return _client().complete_task(task_id)


@mcp.tool()
def list_task_statuses() -> dict[str, Any]:
    """List Lawmatics task statuses."""

    return _client().list_task_statuses()


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


@mcp.tool()
def list_notes(
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """List notes with standard Lawmatics list params.

    Args:
        page: 1-indexed page number.
        fields: Comma-separated field list or "all".
        sort_by: Attribute to sort by.
        sort_order: "asc" or "desc".
        filter_by: Field name to filter on.
        filter_on: Filter value, unless using null/not_null.
        filter_with: Filter operator.
    """

    return _client().list_notes(
        page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
    )


@mcp.tool()
def get_note(note_id: str, fields: str = "") -> dict[str, Any]:
    """Get one note.

    Args:
        note_id: Lawmatics note ID.
        fields: Comma-separated field list or "all".
    """

    return _client().get_note(note_id, fields)


@mcp.tool()
def create_note(
    name: str,
    body: str,
    notable_type: str,
    notable_id: str,
) -> dict[str, Any]:
    """Create a note for a Prospect or Company.

    Args:
        name: Note name.
        body: Note body text.
        notable_type: Prospect or Company.
        notable_id: ID for the notable record.
    """

    return _client().create_note(name, body, notable_type, notable_id)


@mcp.tool()
def update_note(note_id: str, note_data: dict[str, Any]) -> dict[str, Any]:
    """Update a note with a partial field dictionary.

    Args:
        note_id: Lawmatics note ID.
        note_data: Fields to send in the PUT body.
    """

    return _client().update_note(note_id, note_data)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@mcp.tool()
def list_events(
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """List events with standard Lawmatics list params.

    Args:
        page: 1-indexed page number.
        fields: Comma-separated field list or "all".
        sort_by: Attribute to sort by.
        sort_order: "asc" or "desc".
        filter_by: Field name to filter on.
        filter_on: Filter value, unless using null/not_null.
        filter_with: Filter operator.
    """

    return _client().list_events(
        page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
    )


@mcp.tool()
def get_event(event_id: str, fields: str = "") -> dict[str, Any]:
    """Get one event.

    Args:
        event_id: Lawmatics event ID.
        fields: Comma-separated field list or "all".
    """

    return _client().get_event(event_id, fields)


@mcp.tool()
def create_event(
    name: str,
    start_date: str,
    end_date: str,
    eventable_type: str = "",
    eventable_id: str = "",
    user_ids: list[str] | None = None,
    all_day: bool = False,
    time_zone: str = "",
    reminder_type: str = "",
    reminder_delay_length: int | None = None,
    send_invites: bool = True,
    event_type_id: str = "",
) -> dict[str, Any]:
    """Create a calendar event.

    Args:
        name: Event name.
        start_date: Start datetime in ISO8601.
        end_date: End datetime in ISO8601.
        eventable_type: Optional Prospect, Contact, or Client.
        eventable_id: ID for the eventable record.
        user_ids: Attendee/user IDs.
        all_day: Whether the event is all-day.
        time_zone: Event time zone.
        reminder_type: minutes, hours, days, weeks, or months.
        reminder_delay_length: Reminder delay number.
        send_invites: Whether Lawmatics should send invites.
        event_type_id: Event type ID.
    """

    return _client().create_event(
        name,
        start_date,
        end_date,
        eventable_type,
        eventable_id,
        user_ids,
        all_day,
        time_zone,
        reminder_type,
        reminder_delay_length,
        send_invites,
        event_type_id,
    )


@mcp.tool()
def update_event(event_id: str, event_data: dict[str, Any]) -> dict[str, Any]:
    """Update an event with a partial field dictionary.

    Args:
        event_id: Lawmatics event ID.
        event_data: Fields to send in the PUT body.
    """

    return _client().update_event(event_id, event_data)


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------


@mcp.tool()
def list_custom_fields(fields: str = "all", page: int = 1) -> dict[str, Any]:
    """List custom fields.

    Args:
        fields: Field selection; defaults to "all" for full shape.
        page: 1-indexed page number.
    """

    return _client().list_custom_fields(fields, page)


@mcp.tool()
def get_custom_field(custom_field_id: str) -> dict[str, Any]:
    """Get one custom field.

    Args:
        custom_field_id: Lawmatics custom field ID.
    """

    return _client().get_custom_field(custom_field_id)


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


@mcp.tool()
def list_interactions(
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """List interactions with standard Lawmatics list params.

    Args:
        page: 1-indexed page number.
        fields: Comma-separated field list or "all".
        sort_by: Attribute to sort by.
        sort_order: "asc" or "desc".
        filter_by: Field name to filter on.
        filter_on: Filter value, unless using null/not_null.
        filter_with: Filter operator.
    """

    return _client().list_interactions(
        page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
    )


@mcp.tool()
def create_interaction(
    interaction_type: str,
    body: str,
    happened_at: str,
    interactable_type: str = "Prospect",
    interactable_id: str = "",
    created_by_id: str = "",
) -> dict[str, Any]:
    """Create an interaction.

    Args:
        interaction_type: Free-text interaction type.
        body: Interaction body text.
        happened_at: ISO8601 timestamp when it happened.
        interactable_type: Relationship type; Prospect is documented.
        interactable_id: Related record ID.
        created_by_id: Optional user ID for the created_by relationship.
    """

    return _client().create_interaction(
        interaction_type,
        body,
        happened_at,
        interactable_type,
        interactable_id,
        created_by_id,
    )


# ---------------------------------------------------------------------------
# Custom emails
# ---------------------------------------------------------------------------


@mcp.tool()
def list_custom_emails(page: int = 1) -> dict[str, Any]:
    """List custom email templates and campaign stats.

    Args:
        page: 1-indexed page number.
    """

    return _client().list_custom_emails(page)


@mcp.tool()
def get_custom_email(custom_email_id: str) -> dict[str, Any]:
    """Get one custom email template/stat record.

    Args:
        custom_email_id: Lawmatics custom email ID.
    """

    return _client().get_custom_email(custom_email_id)


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


@mcp.tool()
def list_forms(page: int = 1) -> dict[str, Any]:
    """List custom forms.

    Args:
        page: 1-indexed page number.
    """

    return _client().list_forms(page)


@mcp.tool()
def get_form(form_uuid: str) -> dict[str, Any]:
    """Get one custom form with fields=all.

    Args:
        form_uuid: Lawmatics custom form UUID.
    """

    return _client().get_form(form_uuid)


@mcp.tool()
def list_form_entries(form_uuid: str, page: int = 1) -> dict[str, Any]:
    """List entries submitted for a custom form.

    Args:
        form_uuid: Lawmatics custom form UUID.
        page: 1-indexed page number.
    """

    return _client().list_form_entries(form_uuid, page)


@mcp.tool()
def submit_form(
    form_uuid: str,
    fields: dict[str, Any],
    utm_source: str = "",
    utm_campaign: str = "",
    referring_url: str = "",
) -> dict[str, Any]:
    """Submit a custom form as JSON without an Authorization header.

    Args:
        form_uuid: Lawmatics custom form UUID.
        fields: Form field ID to value mapping.
        utm_source: Optional UTM source.
        utm_campaign: Optional UTM campaign.
        referring_url: Optional referring URL.
    """

    return _client().submit_form(form_uuid, fields, utm_source, utm_campaign, referring_url)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

