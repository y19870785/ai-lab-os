"""Durable Reminder and occurrence models."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from core.errors import FailureInfo
from core.errors.models import sanitize_details


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("reminder datetimes must include timezone information")
    return value.astimezone(timezone.utc)


class ReminderStatus(str, Enum):
    PENDING_SCHEDULE = "pending_schedule"
    SCHEDULED = "scheduled"
    PENDING_RESCHEDULE = "pending_reschedule"
    PENDING_CANCEL = "pending_cancel"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ReminderOccurrenceStatus(str, Enum):
    PROCESSING = "processing"
    TRIGGERED = "triggered"
    FAILED = "failed"


class Reminder(BaseModel):
    id: str = Field(default_factory=lambda: "rem_" + uuid.uuid4().hex)
    user_task_id: str
    remind_at: datetime
    timezone: str
    status: ReminderStatus = ReminderStatus.PENDING_SCHEDULE
    scheduler_job_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    cancelled_at: datetime | None = None
    last_failure: FailureInfo | None = None
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision: int = Field(default=1, ge=1)

    _normalize_remind_at = field_validator("remind_at")(_aware_utc)
    _normalize_created_at = field_validator("created_at")(_aware_utc)
    _normalize_updated_at = field_validator("updated_at")(_aware_utc)
    _normalize_cancelled_at = field_validator("cancelled_at")(_aware_utc)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = sanitize_details(value)
        if sanitized != value:
            raise ValueError("reminder metadata contains a sensitive key or value")
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("reminder metadata must be JSON serializable") from exc
        return value


class ReminderOccurrence(BaseModel):
    id: str = Field(default_factory=lambda: "occ_" + uuid.uuid4().hex)
    reminder_id: str
    user_task_id: str
    scheduled_at: datetime
    triggered_at: datetime | None = None
    status: ReminderOccurrenceStatus = ReminderOccurrenceStatus.PROCESSING
    trace_id: str = ""
    failure: FailureInfo | None = None
    idempotency_key: str
    attempt: int = Field(default=1, ge=1)

    _normalize_scheduled_at = field_validator("scheduled_at")(_aware_utc)
    _normalize_triggered_at = field_validator("triggered_at")(_aware_utc)


class ReconciliationResult(BaseModel):
    repaired: int = 0
    skipped: int = 0
    failed: int = 0
