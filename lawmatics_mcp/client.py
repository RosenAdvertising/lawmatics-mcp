#!/usr/bin/env python3
"""Lawmatics API client for confirmed v0.1 MCP operations."""

from __future__ import annotations

import logging
import os
from typing import Any, NoReturn
from urllib.parse import quote

import requests

from lawmatics_mcp import credentials

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lawmatics.com/v1"
TOKEN_URL = "https://api.lawmatics.com/oauth/token"
AUTHORIZE_URL = "https://app.lawmatics.com/oauth/authorize"
DEFAULT_REDIRECT_URI = "http://localhost:8124/callback"

ENV_KEYS = [
    "LAWMATICS_CLIENT_ID",
    "LAWMATICS_CLIENT_SECRET",
    "LAWMATICS_REDIRECT_URI",
    "LAWMATICS_ACCESS_TOKEN",
]

VALID_SORT_ORDERS = {"asc", "desc"}
VALID_FILTER_OPERATORS = {
    "=",
    "!=",
    "<=",
    "<",
    ">=",
    ">",
    "like",
    "ilike",
    "null",
    "not_null",
    "empty",
    "present",
    "blank",
}
VALUELESS_FILTER_OPERATORS = {"null", "not_null", "empty", "present", "blank"}

TASK_PRIORITIES = {"high", "medium", "low"}
TASKABLE_TYPES = {"Prospect", "Contact", "Company", "Client"}
NOTABLE_TYPES = {"Prospect", "Company"}
EVENTABLE_TYPES = {"Prospect", "Contact", "Client"}
REMINDER_TYPES = {"minutes", "hours", "days", "weeks", "months"}


def _reject(reason: str) -> NoReturn:
    """Reject invalid input after recording a PII-free reason."""

    logger.warning("Lawmatics validation rejected request: %s", reason)
    raise ValueError(reason)


def _validate_page(page: int) -> int:
    """Return a valid one-indexed page or reject it with a safe log."""

    if page < 1:
        _reject("page must be 1 or greater")
    return page


class LawmaticsAPIError(RuntimeError):
    """Base error for Lawmatics API failures."""


class LawmaticsAuthError(LawmaticsAPIError):
    """Raised when the stored Lawmatics access token is invalid or revoked."""


class LawmaticsRateLimitError(LawmaticsAPIError):
    """Raised when Lawmatics returns 429 Too Many Requests."""

    def __init__(self, retry_after: str | None):
        self.retry_after = retry_after or ""
        suffix = f" Retry-After: {self.retry_after}." if self.retry_after else ""
        super().__init__(
            "Lawmatics API rate limit exceeded (50 requests/minute per firm)."
            f"{suffix} Retry later; this client does not auto-sleep."
        )


def _json_response(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError as exc:
        logger.warning(
            "Lawmatics API response rejected: invalid JSON status=%s",
            resp.status_code,
        )
        raise LawmaticsAPIError(
            f"Lawmatics API returned non-JSON response ({resp.status_code})"
        ) from exc


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """Drop empty optional values while preserving falsey real values like 0."""

    compacted: dict[str, Any] = {}
    for key, value in data.items():
        if value is None or value == "" or value == []:
            continue
        compacted[key] = value
    return compacted


def build_list_params(
    page: int = 1,
    fields: str = "",
    sort_by: str = "",
    sort_order: str = "",
    filter_by: str = "",
    filter_on: str = "",
    filter_with: str = "",
) -> dict[str, Any]:
    """Build standard Lawmatics list query params with client-side validation."""

    page = _validate_page(page)
    if sort_order and sort_order not in VALID_SORT_ORDERS:
        _reject("sort_order must be 'asc' or 'desc'")
    if filter_with and filter_with not in VALID_FILTER_OPERATORS:
        _reject(
            "filter_with must be one of: " + ", ".join(sorted(VALID_FILTER_OPERATORS))
        )
    if filter_on and not filter_by:
        _reject("filter_on requires filter_by")
    if filter_with and not filter_by:
        _reject("filter_with requires filter_by")

    params: dict[str, Any] = {"page": page}
    if fields:
        params["fields"] = fields
    if sort_by:
        params["sort_by"] = sort_by
    if sort_order:
        params["sort_order"] = sort_order

    operator = filter_with or "="
    if filter_by:
        if not filter_on and operator not in VALUELESS_FILTER_OPERATORS:
            _reject("filter_by requires filter_on unless filter_with is null/not_null")
        params["filter_by"] = filter_by
        if filter_on:
            params["filter_on"] = filter_on
        if filter_with:
            params["filter_with"] = filter_with

    return params


def build_fields_params(fields: str = "") -> dict[str, str]:
    """Build field-selection params for single-resource requests."""

    return {"fields": fields} if fields else {}


class LawmaticsClient:
    """Small requests-based client for confirmed Lawmatics API endpoints."""

    def __init__(
        self,
        access_token: str | None = None,
        session: requests.Session | None = None,
    ):
        credentials.load_into_environ(ENV_KEYS)
        self.access_token = access_token or os.environ.get("LAWMATICS_ACCESS_TOKEN", "")
        if not self.access_token:
            logger.warning(
                "Lawmatics client initialization rejected: access token unavailable"
            )
            raise RuntimeError(
                "Lawmatics access token not found. Run: lawmatics-mcp-setup"
            )
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )

    def _url(self, path: str) -> str:
        return f"{BASE_URL}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        auth: bool = True,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self.access_token}"} if auth else {}
        resp = self.session.request(
            method,
            self._url(path),
            params=params,
            json=json_body,
            headers=headers,
        )
        if resp.status_code == 401:
            logger.warning(
                "Lawmatics API request rejected: authentication failed method=%s",
                method,
            )
            raise LawmaticsAuthError(
                "Lawmatics token revoked/invalid - re-run lawmatics-mcp-setup"
            )
        if resp.status_code == 429:
            logger.warning(
                "Lawmatics API request rejected: rate limited method=%s",
                method,
            )
            raise LawmaticsRateLimitError(resp.headers.get("Retry-After"))
        if resp.status_code == 204:
            return {"success": True}
        if not resp.ok:
            logger.warning(
                "Lawmatics API request rejected: status=%s method=%s",
                resp.status_code,
                method,
            )
            raise LawmaticsAPIError(f"Lawmatics API error {resp.status_code}")
        return _json_response(resp)

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: Any = None, auth: bool = True) -> Any:
        return self._request("POST", path, json_body=body, auth=auth)

    def put(self, path: str, body: Any = None) -> Any:
        return self._request("PUT", path, json_body=body)

    # Identity

    def get_current_user(self) -> dict[str, Any]:
        return self.get("/users/me")

    def list_users(
        self,
        page: int = 1,
        fields: str = "",
        sort_by: str = "",
        sort_order: str = "",
        filter_by: str = "",
        filter_on: str = "",
        filter_with: str = "",
    ) -> dict[str, Any]:
        return self.get(
            "/users",
            build_list_params(
                page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
            ),
        )

    def get_user(self, user_id: str, fields: str = "") -> dict[str, Any]:
        return self.get(f"/users/{user_id}", build_fields_params(fields))

    # Matters: Lawmatics API resource is /prospects.

    def list_matters(
        self,
        page: int = 1,
        fields: str = "",
        sort_by: str = "",
        sort_order: str = "",
        filter_by: str = "",
        filter_on: str = "",
        filter_with: str = "",
    ) -> dict[str, Any]:
        return self.get(
            "/prospects",
            build_list_params(
                page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
            ),
        )

    def get_matter(self, matter_id: str, fields: str = "") -> dict[str, Any]:
        return self.get(f"/prospects/{matter_id}", build_fields_params(fields))

    def create_matter(
        self,
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
        body = _compact(
            {
                "case_title": case_title,
                "contact_id": contact_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "case_blurb": case_blurb,
                "practice_area_id": practice_area_id,
                "stage_id": stage_id,
                "estimated_value_cents": estimated_value_cents,
                "tags": tags or [],
            }
        )
        if extra_fields:
            body.update(_compact(extra_fields))
        return self.post("/prospects", body)

    def update_matter(
        self, matter_id: str, matter_data: dict[str, Any]
    ) -> dict[str, Any]:
        return self.put(f"/prospects/{matter_id}", matter_data)

    def find_matter(
        self, phone: str = "", email: str = "", name: str = ""
    ) -> dict[str, Any]:
        supplied = [
            (key, value)
            for key, value in {
                "phone": phone,
                "email": email,
                "name": name,
            }.items()
            if value
        ]
        if len(supplied) != 1:
            _reject("find_matter requires exactly one of phone, email, or name")
        key, value = supplied[0]
        finder = {
            "phone": "find_by_phone",
            "email": "find_by_email",
            "name": "find_by_name",
        }[key]
        return self.get(f"/prospects/{finder}/{quote(value, safe='')}")

    # Contacts

    def list_contacts(
        self,
        page: int = 1,
        fields: str = "",
        sort_by: str = "",
        sort_order: str = "",
        filter_by: str = "",
        filter_on: str = "",
        filter_with: str = "",
    ) -> dict[str, Any]:
        return self.get(
            "/contacts",
            build_list_params(
                page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
            ),
        )

    def get_contact(self, contact_id: str, fields: str = "") -> dict[str, Any]:
        return self.get(f"/contacts/{contact_id}", build_fields_params(fields))

    def create_contact(
        self,
        first_name: str,
        last_name: str,
        email: str = "",
        phone: str = "",
        notes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        body = _compact(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "notes": notes or [],
            }
        )
        return self.post("/contacts", body)

    def update_contact(
        self, contact_id: str, contact_data: dict[str, Any]
    ) -> dict[str, Any]:
        return self.put(f"/contacts/{contact_id}", contact_data)

    # Tasks

    def list_tasks(
        self,
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
        params = build_list_params(
            page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
        )
        params.update(
            _compact(
                {
                    "matter_id": matter_id,
                    "contact_id": contact_id,
                    "company_id": company_id,
                    "user_id": user_id,
                }
            )
        )
        return self.get("/tasks", params)

    def get_task(self, task_id: str, fields: str = "") -> dict[str, Any]:
        return self.get(f"/tasks/{task_id}", build_fields_params(fields))

    def create_task(
        self,
        name: str,
        description: str = "",
        due_date: str = "",
        user_ids: list[str] | None = None,
        priority: str = "medium",
        taskable_type: str = "",
        taskable_id: str = "",
        tag_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if priority not in TASK_PRIORITIES:
            _reject("priority must be one of: high, medium, low")
        if taskable_type and taskable_type not in TASKABLE_TYPES:
            _reject("taskable_type must be one of: Prospect, Contact, Company, Client")
        body = _compact(
            {
                "name": name,
                "description": description,
                "due_date": due_date,
                "user_ids": user_ids or [],
                "priority": priority,
                "taskable_type": taskable_type,
                "taskable_id": taskable_id,
                "tag_ids": tag_ids or [],
            }
        )
        return self.post("/tasks", body)

    def update_task(self, task_id: str, task_data: dict[str, Any]) -> dict[str, Any]:
        return self.put(f"/tasks/{task_id}", task_data)

    def complete_task(self, task_id: str) -> dict[str, Any]:
        return self.put(f"/tasks/{task_id}", {"done": True})

    def list_task_statuses(self) -> dict[str, Any]:
        return self.get("/task_statuses")

    # Notes

    def list_notes(
        self,
        page: int = 1,
        fields: str = "",
        sort_by: str = "",
        sort_order: str = "",
        filter_by: str = "",
        filter_on: str = "",
        filter_with: str = "",
    ) -> dict[str, Any]:
        return self.get(
            "/notes",
            build_list_params(
                page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
            ),
        )

    def get_note(self, note_id: str, fields: str = "") -> dict[str, Any]:
        return self.get(f"/notes/{note_id}", build_fields_params(fields))

    def create_note(
        self, name: str, body: str, notable_type: str, notable_id: str
    ) -> dict[str, Any]:
        if notable_type not in NOTABLE_TYPES:
            _reject("notable_type must be one of: Prospect, Company")
        return self.post(
            "/notes",
            {
                "name": name,
                "body": body,
                "notable_type": notable_type,
                "notable_id": notable_id,
            },
        )

    def update_note(self, note_id: str, note_data: dict[str, Any]) -> dict[str, Any]:
        return self.put(f"/notes/{note_id}", note_data)

    # Events

    def list_events(
        self,
        page: int = 1,
        fields: str = "",
        sort_by: str = "",
        sort_order: str = "",
        filter_by: str = "",
        filter_on: str = "",
        filter_with: str = "",
    ) -> dict[str, Any]:
        return self.get(
            "/events",
            build_list_params(
                page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
            ),
        )

    def get_event(self, event_id: str, fields: str = "") -> dict[str, Any]:
        return self.get(f"/events/{event_id}", build_fields_params(fields))

    def create_event(
        self,
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
        if eventable_type and eventable_type not in EVENTABLE_TYPES:
            _reject("eventable_type must be one of: Prospect, Contact, Client")
        if reminder_type and reminder_type not in REMINDER_TYPES:
            _reject("reminder_type must be one of: minutes, hours, days, weeks, months")
        body = _compact(
            {
                "name": name,
                "start_date": start_date,
                "end_date": end_date,
                "eventable_type": eventable_type,
                "eventable_id": eventable_id,
                "user_ids": user_ids or [],
                "all_day": all_day,
                "time_zone": time_zone,
                "reminder_type": reminder_type,
                "reminder_delay_length": reminder_delay_length,
                "send_invites": send_invites,
                "event_type_id": event_type_id,
            }
        )
        return self.post("/events", body)

    def update_event(self, event_id: str, event_data: dict[str, Any]) -> dict[str, Any]:
        return self.put(f"/events/{event_id}", event_data)

    # Custom fields

    def list_custom_fields(self, fields: str = "all", page: int = 1) -> dict[str, Any]:
        return self.get(
            "/custom_fields",
            _compact({"fields": fields, "page": _validate_page(page)}),
        )

    def get_custom_field(self, custom_field_id: str) -> dict[str, Any]:
        return self.get(f"/custom_fields/{custom_field_id}")

    # Interactions

    def list_interactions(
        self,
        page: int = 1,
        fields: str = "",
        sort_by: str = "",
        sort_order: str = "",
        filter_by: str = "",
        filter_on: str = "",
        filter_with: str = "",
    ) -> dict[str, Any]:
        return self.get(
            "/interactions",
            build_list_params(
                page, fields, sort_by, sort_order, filter_by, filter_on, filter_with
            ),
        )

    def create_interaction(
        self,
        interaction_type: str,
        body: str,
        happened_at: str,
        interactable_type: str = "Prospect",
        interactable_id: str = "",
        created_by_id: str = "",
    ) -> dict[str, Any]:
        payload = _compact(
            {
                "interaction_type": interaction_type,
                "body": body,
                "happened_at": happened_at,
                "interactable_type": interactable_type,
                "interactable_id": interactable_id,
                "created_by_id": created_by_id,
            }
        )
        return self.post("/interactions", payload)

    # Custom emails

    def list_custom_emails(self, page: int = 1) -> dict[str, Any]:
        return self.get("/custom_emails", {"page": _validate_page(page)})

    def get_custom_email(self, custom_email_id: str) -> dict[str, Any]:
        return self.get(f"/custom_emails/{custom_email_id}")

    # Forms

    def list_forms(self, page: int = 1) -> dict[str, Any]:
        return self.get("/forms", {"page": _validate_page(page)})

    def get_form(self, form_uuid: str) -> dict[str, Any]:
        return self.get(f"/forms/{form_uuid}", {"fields": "all"})

    def list_form_entries(self, form_uuid: str, page: int = 1) -> dict[str, Any]:
        return self.get(f"/forms/{form_uuid}/entries", {"page": _validate_page(page)})

    def submit_form(
        self,
        form_uuid: str,
        fields: dict[str, Any],
        utm_source: str = "",
        utm_campaign: str = "",
        referring_url: str = "",
    ) -> dict[str, Any]:
        body = dict(fields)
        body.update(
            _compact(
                {
                    "utm_source": utm_source,
                    "utm_campaign": utm_campaign,
                    "referring_url": referring_url,
                }
            )
        )
        return self.post(f"/forms/{form_uuid}/submit", body, auth=False)
