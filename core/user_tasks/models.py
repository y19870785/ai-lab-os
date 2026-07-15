"""Canonical user-visible task domain models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class UserTaskStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class UserTaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must include timezone information")
    return value.astimezone(timezone.utc)


def _contains_sensitive_key(value: Any) -> bool:
    sensitive = {
        "api_key", "apikey", "token", "secret", "password", "authorization",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in sensitive or _contains_sensitive_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


class UserTask(BaseModel):
    id: str = Field(default_factory=lambda: f"ut_{uuid4().hex}")
    title: str
    description: str = ""
    status: UserTaskStatus = UserTaskStatus.ACTIVE
    priority: UserTaskPriority = UserTaskPriority.MEDIUM
    due_at: datetime | None = None
    timezone: str = "UTC"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    source: str = "api"
    session_id: str = ""
    agent_id: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    legacy_source_id: str | None = None
    revision: int = Field(default=1, ge=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("task title must not be blank")
        return value

    @field_validator("due_at", "created_at", "updated_at", "completed_at", "cancelled_at")
    @classmethod
    def normalize_datetimes(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("timezone must not be blank")
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_sensitive_key(value):
            raise ValueError("task metadata contains a sensitive key")
        try:
            json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("task metadata must be JSON serializable") from exc
        return value

    def is_overdue(self, now: datetime | None = None) -> bool:
        current = _aware_utc(now or utc_now())
        return bool(
            self.status == UserTaskStatus.ACTIVE
            and self.due_at is not None
            and self.due_at < current
        )

    def due_at_in_timezone(self) -> datetime | None:
        """Return the UTC instant in the task's validated presentation timezone."""

        return self.due_at.astimezone(ZoneInfo(self.timezone)) if self.due_at else None


class UserTaskQuery(BaseModel):
    status: UserTaskStatus | None = None
    priority: UserTaskPriority | None = None
    due_from: datetime | None = None
    due_to: datetime | None = None
    overdue: bool | None = None
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("due_from", "due_to")
    @classmethod
    def normalize_query_datetimes(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)


class LegacyImportResult(BaseModel):
    imported: int = 0
    skipped: int = 0
    failed: int = 0
