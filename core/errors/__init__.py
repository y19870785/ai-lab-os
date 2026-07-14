"""Authoritative failure semantics for AI-Lab runtimes."""

from core.errors.codes import ErrorCategory, ErrorSeverity, RuntimeStatus
from core.errors.exceptions import FailureException
from core.errors.mapping import (
    failure_event_payload,
    failure_from_exception,
    http_status_for_failure,
)
from core.errors.models import FailureInfo

__all__ = [
    "ErrorCategory",
    "ErrorSeverity",
    "FailureException",
    "FailureInfo",
    "RuntimeStatus",
    "failure_event_payload",
    "failure_from_exception",
    "http_status_for_failure",
]
