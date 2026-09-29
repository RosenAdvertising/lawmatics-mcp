from __future__ import annotations

import pytest

from lawmatics_mcp.client import (
    LawmaticsAPIError,
    LawmaticsAuthError,
    LawmaticsClient,
    LawmaticsRateLimitError,
    build_list_params,
)


def test_bearer_header_on_normal_requests_and_no_auth_on_submit_form(mock_requests):
    calls, enqueue = mock_requests
    enqueue()
    enqueue()

    client = LawmaticsClient()
    client.get_current_user()
    client.submit_form(
        "form-uuid",
        {"first_name": "Ada"},
        utm_source="google",
        utm_campaign="intake",
    )

    assert calls[0]["url"] == "https://api.lawmatics.com/v1/users/me"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[0]["kwargs"]["timeout"] == 30
    assert calls[1]["url"] == "https://api.lawmatics.com/v1/forms/form-uuid/submit"
    assert "Authorization" not in calls[1]["headers"]
    assert calls[1]["json"] == {
        "first_name": "Ada",
        "utm_source": "google",
        "utm_campaign": "intake",
    }


def test_matters_use_prospects_paths_and_cents_fields_pass_through(mock_requests):
    calls, enqueue = mock_requests
    enqueue()
    enqueue()
    enqueue()

    client = LawmaticsClient()
    client.list_matters()
    client.get_matter("123")
    client.create_matter(
        case_title="Estate intake",
        estimated_value_cents=12345,
        extra_fields={"actual_value_cents": 67890, "lead_cost_cents": 2500},
    )

    assert calls[0]["url"] == "https://api.lawmatics.com/v1/prospects"
    assert calls[1]["url"] == "https://api.lawmatics.com/v1/prospects/123"
    assert calls[2]["url"] == "https://api.lawmatics.com/v1/prospects"
    assert all("/matters" not in call["url"] for call in calls)
    assert calls[2]["json"]["estimated_value_cents"] == 12345
    assert calls[2]["json"]["actual_value_cents"] == 67890
    assert calls[2]["json"]["lead_cost_cents"] == 2500


def test_shared_list_param_helper_serializes_and_validates_filters():
    params = build_list_params(
        page=2,
        fields="first_name,actual_value_cents",
        sort_by="actual_value_cents",
        sort_order="asc",
        filter_by="estimated_value_cents",
        filter_on="10000",
        filter_with="<=",
    )

    assert params == {
        "page": 2,
        "fields": "first_name,actual_value_cents",
        "sort_by": "actual_value_cents",
        "sort_order": "asc",
        "filter_by": "estimated_value_cents",
        "filter_on": "10000",
        "filter_with": "<=",
    }

    with pytest.raises(ValueError, match="filter_by requires filter_on"):
        build_list_params(filter_by="case_title")

    assert build_list_params(filter_by="closed_at", filter_with="null") == {
        "page": 1,
        "filter_by": "closed_at",
        "filter_with": "null",
    }
    assert build_list_params(filter_by="closed_at", filter_with="not_null") == {
        "page": 1,
        "filter_by": "closed_at",
        "filter_with": "not_null",
    }


def test_find_matter_requires_exactly_one_value_and_uses_encoded_paths(mock_requests):
    calls, enqueue = mock_requests
    enqueue()
    enqueue()

    client = LawmaticsClient()
    client.find_matter(phone="+1 828 555")
    client.find_matter(name="John Smith")

    assert calls[0]["url"].endswith("/prospects/find_by_phone/%2B1%20828%20555")
    assert calls[1]["url"].endswith("/prospects/find_by_name/John%20Smith")

    with pytest.raises(ValueError, match="exactly one"):
        client.find_matter()
    with pytest.raises(ValueError, match="exactly one"):
        client.find_matter(phone="123", email="a@example.com")


@pytest.mark.parametrize(
    ("identifier", "encoded"),
    [
        ("../x", "..%2Fx"),
        ("x?secret", "x%3Fsecret"),
        ("x#fragment", "x%23fragment"),
        ("a/b", "a%2Fb"),
    ],
)
def test_string_identifiers_are_confined_to_one_encoded_path_segment(
    mock_requests, identifier, encoded
):
    calls, enqueue = mock_requests
    enqueue()
    LawmaticsClient().get_matter(identifier)
    assert calls[0]["url"] == f"https://api.lawmatics.com/v1/prospects/{encoded}"


def test_create_note_body_shape_and_notable_type_validation(mock_requests):
    calls, enqueue = mock_requests
    enqueue()

    client = LawmaticsClient()
    client.create_note("Call summary", "Client called back.", "Prospect", "55")

    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://api.lawmatics.com/v1/notes"
    assert calls[0]["json"] == {
        "name": "Call summary",
        "body": "Client called back.",
        "notable_type": "Prospect",
        "notable_id": "55",
    }

    with pytest.raises(ValueError, match="notable_type"):
        client.create_note("Bad", "Body", "Contact", "55")
    assert len(calls) == 1


def test_complete_task_sends_done_true_by_put(mock_requests):
    calls, enqueue = mock_requests
    enqueue()

    LawmaticsClient().complete_task("task-9")

    assert calls[0]["method"] == "PUT"
    assert calls[0]["url"] == "https://api.lawmatics.com/v1/tasks/task-9"
    assert calls[0]["json"] == {"done": True}


def test_task_priority_and_taskable_type_validation_before_http(mock_requests):
    calls, _enqueue = mock_requests
    client = LawmaticsClient()

    with pytest.raises(ValueError, match="priority"):
        client.create_task("Review", priority="urgent")

    with pytest.raises(ValueError, match="taskable_type"):
        client.create_task("Review", taskable_type="Matter")

    assert calls == []


def test_429_raises_rate_limit_error_with_retry_after_and_no_retry(mock_requests):
    calls, enqueue = mock_requests
    enqueue(status_code=429, headers={"Retry-After": "60"}, text="rate limited")

    with pytest.raises(LawmaticsRateLimitError, match="Retry after 60 seconds"):
        LawmaticsClient().get_current_user()

    assert len(calls) == 1


def test_401_raises_rerun_setup_error_and_does_not_refresh(mock_requests):
    calls, enqueue = mock_requests
    enqueue(status_code=401, text="unauthorized")

    with pytest.raises(LawmaticsAuthError, match="lawmatics-mcp-setup"):
        LawmaticsClient().get_current_user()

    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.lawmatics.com/v1/users/me"
    assert all("/oauth/token" not in call["url"] for call in calls)


def test_403_reports_permission_or_expired_authorization_guidance(mock_requests):
    calls, enqueue = mock_requests
    enqueue(status_code=403, text="private vendor body")
    with pytest.raises(LawmaticsAuthError) as exc_info:
        LawmaticsClient().get_current_user()
    assert (
        str(exc_info.value)
        == "Lawmatics access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawmatics-mcp-setup if so)."
    )
    assert calls[0]["kwargs"]["timeout"] == 30


def test_non_success_empty_response_body_is_an_error(mock_requests):
    calls, enqueue = mock_requests
    enqueue(status_code=500, text="")
    with pytest.raises(LawmaticsAPIError) as exc_info:
        LawmaticsClient().get_current_user()
    assert exc_info.value.status_code == 500
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [[], "VENDOR-SECRET https://evil.test"])
def test_success_response_with_non_object_json_is_a_safe_error(mock_requests, payload):
    _calls, enqueue = mock_requests
    enqueue(status_code=200, json_data=payload)
    with pytest.raises(LawmaticsAPIError) as exc_info:
        LawmaticsClient().get_current_user()
    assert str(exc_info.value) == "Lawmatics API error 200"
    assert "VENDOR-SECRET" not in str(exc_info.value)


def test_validation_rejections_log_only_pii_free_reasons(mock_requests, caplog):
    calls, _enqueue = mock_requests
    client = LawmaticsClient()

    with pytest.raises(ValueError, match="exactly one"):
        client.find_matter(phone="+1 555 0100", email="person@example.com")

    assert calls == []
    assert "Lawmatics validation rejected request" in caplog.text
    assert "+1 555 0100" not in caplog.text
    assert "person@example.com" not in caplog.text


@pytest.mark.parametrize(
    "call",
    [
        lambda client: client.list_custom_fields(page=0),
        lambda client: client.list_custom_emails(page=0),
        lambda client: client.list_forms(page=0),
        lambda client: client.list_form_entries("form-uuid", page=0),
    ],
)
def test_specialized_list_tools_reject_invalid_pages_before_http(
    call, mock_requests, caplog
):
    calls, _enqueue = mock_requests

    with pytest.raises(ValueError, match="page must be 1 or greater"):
        call(LawmaticsClient())

    assert calls == []
    assert "page must be 1 or greater" in caplog.text


def test_api_failure_does_not_emit_vendor_body_to_errors_or_logs(mock_requests, caplog):
    calls, enqueue = mock_requests
    sensitive_body = "contact person@example.com named Ada"
    enqueue(status_code=500, text=sensitive_body)

    with pytest.raises(LawmaticsAPIError) as exc_info:
        LawmaticsClient().get_current_user()

    assert len(calls) == 1
    assert sensitive_body not in str(exc_info.value)
    assert "person@example.com" not in caplog.text
    assert "Ada" not in caplog.text
