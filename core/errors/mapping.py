"""Exception classification and transport mappings."""

from __future__ import annotations

import asyncio
from typing import Any

from core.errors.codes import ErrorCategory, ErrorSeverity
from core.errors.exceptions import FailureException
from core.errors.models import FailureInfo


_HTTP_STATUS = {
    ErrorCategory.VALIDATION: 400,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.ALREADY_EXISTS: 409,
    ErrorCategory.CONFLICT: 409,
    ErrorCategory.PERMISSION_DENIED: 403,
    ErrorCategory.NOT_CONFIGURED: 503,
    ErrorCategory.DISABLED: 503,
    ErrorCategory.UNAVAILABLE: 503,
    ErrorCategory.DEPENDENCY_FAILURE: 503,
    ErrorCategory.TIMEOUT: 504,
    ErrorCategory.RATE_LIMITED: 429,
}


def _classify(exception: BaseException) -> tuple[ErrorCategory, bool]:
    if isinstance(exception, FailureException):
        return exception.failure.category, exception.failure.retryable
    if isinstance(exception, (asyncio.TimeoutError, TimeoutError)):
        return ErrorCategory.TIMEOUT, True
    if isinstance(exception, asyncio.CancelledError):
        return ErrorCategory.CANCELLED, False
    if isinstance(exception, PermissionError):
        return ErrorCategory.PERMISSION_DENIED, False
    if isinstance(exception, FileNotFoundError):
        return ErrorCategory.NOT_FOUND, False
    if isinstance(exception, FileExistsError):
        return ErrorCategory.ALREADY_EXISTS, False
    if isinstance(exception, ValueError):
        return ErrorCategory.VALIDATION, False
    if isinstance(exception, (ConnectionError, OSError)):
        return ErrorCategory.UNAVAILABLE, True

    name = exception.__class__.__name__.lower()
    message = str(exception).lower()
    if "notconfigured" in name or "not configured" in message:
        return ErrorCategory.NOT_CONFIGURED, False
    if "disabled" in name or " disabled" in message:
        return ErrorCategory.DISABLED, False
    if "unavailable" in name or "unavailable" in message:
        return ErrorCategory.UNAVAILABLE, True
    if "notfound" in name or "not found" in message:
        return ErrorCategory.NOT_FOUND, False
    if "alreadyexists" in name or "already exists" in message:
        return ErrorCategory.ALREADY_EXISTS, False
    if "permission" in name or "forbidden" in name:
        return ErrorCategory.PERMISSION_DENIED, False
    if "ratelimit" in name or "rate limit" in message:
        return ErrorCategory.RATE_LIMITED, True
    if "validation" in name or "invalid" in message:
        return ErrorCategory.VALIDATION, False
    if "state" in name or "conflict" in name:
        return ErrorCategory.CONFLICT, False
    if "timeout" in name or "timed out" in message:
        return ErrorCategory.TIMEOUT, True
    if "persistence" in name or "database" in name or "sqlite" in name:
        return ErrorCategory.PERSISTENCE_FAILURE, True
    return ErrorCategory.INTERNAL, False


def failure_from_exception(
    exception: BaseException,
    *,
    component: str,
    operation: str,
    trace_id: str = "",
    code: str | None = None,
    category: ErrorCategory | None = None,
    retryable: bool | None = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    details: dict[str, Any] | None = None,
) -> FailureInfo:
    """Convert an exception once while preserving an existing classification."""

    if isinstance(exception, FailureException):
        failure = exception.failure
        if not trace_id or failure.trace_id:
            return failure
        return failure.model_copy(update={"trace_id": trace_id})

    inferred_category, inferred_retryable = _classify(exception)
    final_category = category or inferred_category
    final_retryable = inferred_retryable if retryable is None else retryable
    safe_message = str(exception) or exception.__class__.__name__
    if final_category == ErrorCategory.INTERNAL:
        safe_message = "Unexpected internal error"
    return FailureInfo(
        code=code or f"{component}.{operation}.{final_category.value}",
        category=final_category,
        message=safe_message,
        component=component,
        operation=operation,
        retryable=final_retryable,
        severity=severity,
        trace_id=trace_id,
        cause_type=exception.__class__.__name__,
        details=details or {},
    )


def failure_event_payload(failure: FailureInfo, *, status: str = "failed") -> dict[str, Any]:
    return {"status": status, **failure.to_dict()}


def http_status_for_failure(failure: FailureInfo) -> int:
    return _HTTP_STATUS.get(failure.category, 500)
