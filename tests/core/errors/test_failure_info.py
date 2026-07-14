import pytest
from pydantic import ValidationError

from core.errors import ErrorCategory, FailureInfo, failure_event_payload


def test_failure_info_is_immutable_and_serializable():
    failure = FailureInfo(
        code="provider.generate.failed",
        category=ErrorCategory.UNAVAILABLE,
        message="provider unavailable",
        component="provider",
        operation="generate",
        retryable=True,
        details={"attempt": 2},
    )

    assert failure.to_dict()["category"] == "unavailable"
    with pytest.raises(ValidationError):
        failure.code = "changed"


def test_failure_info_redacts_secrets_from_message_and_details():
    failure = FailureInfo(
        code="provider.failed",
        category=ErrorCategory.INTERNAL,
        message="request used sk-abcdefghijklmnop",
        component="provider",
        operation="generate",
        details={"api_key": "secret", "nested": {"token": "secret"}},
    )

    serialized = str(failure.to_dict())
    assert "abcdefghijklmnop" not in serialized
    assert "secret" not in serialized
    assert serialized.count("<REDACTED>") >= 3


def test_failure_event_payload_uses_flat_common_envelope():
    failure = FailureInfo(
        code="task.plan.empty",
        category=ErrorCategory.VALIDATION,
        message="empty",
        component="task.runtime",
        operation="plan",
        trace_id="trace-1",
    )

    payload = failure_event_payload(failure)
    assert payload["status"] == "failed"
    assert payload["code"] == failure.code
    assert payload["category"] == "validation"
    assert payload["trace_id"] == "trace-1"
    assert "failure" not in payload
