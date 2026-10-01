#!/usr/bin/env python3
"""Lawmatics API client for confirmed v0.1 MCP operations."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, NoReturn
from urllib.parse import quote

import requests
from mcp.server.mcpserver.exceptions import ToolError

from lawmatics_mcp import credentials

logger = logging.getLogger(__name__)


def _path_id(value, parameter: str) -> str:
    """Validate a plain identifier before URL quoting or any HTTP request."""
    expected = (
        "a non-empty plain identifier (ASCII letters, digits, -, _, ., ~); not . or .."
    )
    if (
        isinstance(value, bool)
        or not isinstance(value, (str, int))
        or str(value) in {".", ".."}
        or re.fullmatch(r"[A-Za-z0-9._~-]+", str(value)) is None
    ):
        message = f"Invalid argument '{parameter}': use {expected}."
        raise LawmaticsValidationError(message)
    return quote(str(value), safe="")


def _path_value(value: str, parameter: str) -> str:
    """Keep finder text usable without accepting path syntax or encoded input."""
    if (
        not value
        or value in {".", ".."}
        or any(ch in value for ch in "/\\%?#")
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
    ):
        raise LawmaticsValidationError(
            f"Invalid argument '{parameter}': use plain search text without path separators or percent encoding."
        )
    return quote(value, safe="")


class LawmaticsMissingCredentialsError(ToolError, RuntimeError):
    """The access token is not configured."""


class LawmaticsValidationError(ToolError, ValueError):
    """A locally detected invalid tool argument with a fixed safe message."""

    def __init__(self, safe_message: str):
        self.safe_message = safe_message
        super().__init__(safe_message)


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
    raise LawmaticsValidationError(reason)


def _validate_page(page: int) -> int:
    """Return a valid one-indexed page or reject it with a safe log."""

    if page < 1:
        _reject("page must be 1 or greater")
    return page


class LawmaticsAPIError(ToolError, RuntimeError):
    """Base error for Lawmatics API failures."""

    def __init__(
        self, status_code: int, safe_reason: str = "request could not be processed"
    ):
        self.status_code = status_code
        self.safe_reason = safe_reason
        super().__init__(f"Lawmatics API error {status_code}")


class LawmaticsAuthError(LawmaticsAPIError):
    """Raised when the stored Lawmatics access token is invalid or revoked."""

    def __init__(self, status_code: int):
        super().__init__(status_code, "authentication was rejected")
        if status_code == 403:
            message = "Lawmatics access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawmatics-mcp-setup if so)."
        else:
            message = "Lawmatics authentication was rejected or expired. Reauthorize with lawmatics-mcp-setup."
        self.args = (message,)


class LawmaticsRateLimitError(LawmaticsAPIError):
    """Raised when Lawmatics returns 429 Too Many Requests."""

    def __init__(self, retry_after: str | None):
        self.retry_after_seconds = _safe_retry_after(retry_after)
        super().__init__(429, "rate limit exceeded")
        hint = (
            f"Retry after {self.retry_after_seconds} seconds"
            if self.retry_after_seconds is not None
            else "Retry later"
        )
        self.args = (
            f"Lawmatics rate limit reached. {hint}; this client does not auto-retry.",
        )


def _safe_retry_after(value: str | None) -> int | None:
    """Accept numeric Retry-After seconds without shortening the retry hint."""
    if value is None or not value.isascii() or not value.isdecimal():
        return None
    try:
        return int(value)
    except (ValueError, OverflowError):
        return None


_SAFE_VENDOR_REASONS = {
    "invalid_request": "request parameters were invalid",
    "validation_error": "request parameters were invalid",
    "not_found": "the requested record was not found",
    "resource_not_found": "the requested record was not found",
    "forbidden": "the account is not allowed to perform this action",
    "conflict": "the request conflicts with the current record",
}


def _safe_vendor_reason(resp: requests.Response) -> str:
    """Map only a small set of vendor codes to fixed, reviewed text."""
    try:
        payload = resp.json()
    except (ValueError, TypeError):
        return "request could not be processed"
    if not isinstance(payload, dict):
        return "request could not be processed"
    error = payload.get("error")
    candidates = [error, payload.get("code")]
    if isinstance(error, dict):
        candidates.extend((error.get("code"), error.get("type")))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate in _SAFE_VENDOR_REASONS:
            return _SAFE_VENDOR_REASONS[candidate]
    return "request could not be processed"


def _json_response(resp: requests.Response) -> Any:
    try:
        payload = resp.json()
    except ValueError as exc:
        logger.warning(
            "Lawmatics API response rejected: invalid JSON status=%s",
            resp.status_code,
        )
        raise LawmaticsAPIError(
            resp.status_code, "response was not valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        logger.warning(
            "Lawmatics API response rejected: unexpected JSON shape status=%s",
            resp.status_code,
        )
        raise LawmaticsAPIError(resp.status_code, "response had an unexpected shape")
    return payload


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
            raise LawmaticsMissingCredentialsError(
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
            timeout=30,
        )
        if resp.status_code in (401, 403):
            logger.warning(
                "Lawmatics API request rejected: authentication failed method=%s",
                method,
            )
            raise LawmaticsAuthError(resp.status_code)
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
            raise LawmaticsAPIError(resp.status_code, _safe_vendor_reason(resp))
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
        return self.get(
            f"/users/{_path_id(user_id, 'user_id')}", build_fields_params(fields)
        )

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
        return self.get(
            f"/prospects/{_path_id(matter_id, 'matter_id')}",
            build_fields_params(fields),
        )

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
        return self.put(f"/prospects/{_path_id(matter_id, 'matter_id')}", matter_data)

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
        return self.get(f"/prospects/{finder}/{_path_value(value, key)}")

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
        return self.get(
            f"/contacts/{_path_id(contact_id, 'contact_id')}",
            build_fields_params(fields),
        )

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
        return self.put(f"/contacts/{_path_id(contact_id, 'contact_id')}", contact_data)

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
        return self.get(
            f"/tasks/{_path_id(task_id, 'task_id')}", build_fields_params(fields)
        )

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
        return self.put(f"/tasks/{_path_id(task_id, 'task_id')}", task_data)

    def complete_task(self, task_id: str) -> dict[str, Any]:
        return self.put(f"/tasks/{_path_id(task_id, 'task_id')}", {"done": True})

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
        return self.get(
            f"/notes/{_path_id(note_id, 'note_id')}", build_fields_params(fields)
        )

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
        return self.put(f"/notes/{_path_id(note_id, 'note_id')}", note_data)

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
        return self.get(
            f"/events/{_path_id(event_id, 'event_id')}", build_fields_params(fields)
        )

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
        return self.put(f"/events/{_path_id(event_id, 'event_id')}", event_data)

    # Custom fields

    def list_custom_fields(self, fields: str = "all", page: int = 1) -> dict[str, Any]:
        return self.get(
            "/custom_fields",
            _compact({"fields": fields, "page": _validate_page(page)}),
        )

    def get_custom_field(self, custom_field_id: str) -> dict[str, Any]:
        return self.get(
            f"/custom_fields/{_path_id(custom_field_id, 'custom_field_id')}"
        )

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
        return self.get(
            f"/custom_emails/{_path_id(custom_email_id, 'custom_email_id')}"
        )

    # Forms

    def list_forms(self, page: int = 1) -> dict[str, Any]:
        return self.get("/forms", {"page": _validate_page(page)})

    def get_form(self, form_uuid: str) -> dict[str, Any]:
        return self.get(f"/forms/{_path_id(form_uuid, 'form_uuid')}", {"fields": "all"})

    def list_form_entries(self, form_uuid: str, page: int = 1) -> dict[str, Any]:
        return self.get(
            f"/forms/{_path_id(form_uuid, 'form_uuid')}/entries",
            {"page": _validate_page(page)},
        )

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
        return self.post(
            f"/forms/{_path_id(form_uuid, 'form_uuid')}/submit", body, auth=False
        )
