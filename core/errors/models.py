"""Serializable, immutable failure model shared by all runtimes."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.errors.codes import ErrorCategory, ErrorSeverity


_SECRET_KEYS = ("api_key", "apikey", "authorization", "bearer", "password", "secret", "token")
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}"),
)


def sanitize_text(value: str) -> str:
    """Remove common credential shapes before failures reach logs or APIs."""

    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("<REDACTED>", result)
    return result[:1000]


def sanitize_details(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<REDACTED>"
            if any(secret in str(key).lower() for secret in _SECRET_KEYS)
            else sanitize_details(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_details(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_text(str(value))


class FailureInfo(BaseModel):
    """Stable failure contract used by results, events, health and APIs."""

    model_config = ConfigDict(frozen=True)

    code: str
    category: ErrorCategory
    message: str
    component: str
    operation: str
    retryable: bool = False
    severity: ErrorSeverity = ErrorSeverity.ERROR
    trace_id: str = ""
    cause_type: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        return sanitize_text(value)

    @field_validator("details", mode="before")
    @classmethod
    def sanitize_failure_details(cls, value: Any) -> dict[str, Any]:
        return sanitize_details(value or {})

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
