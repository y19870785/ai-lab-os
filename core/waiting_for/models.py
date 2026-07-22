"""Canonical Waiting-For domain models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.workspace.models import WorkspaceKey


_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
}


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).strip().lower().replace("-", "_") in _SENSITIVE_KEYS
            or _contains_sensitive_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _validate_metadata(value: dict[str, Any]) -> dict[str, Any]:
    if _contains_sensitive_key(value):
        raise ValueError("waiting-for metadata contains a sensitive key")
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("waiting-for metadata must be JSON serializable") from exc
    return value


def canonical_workspace(workspace_key: WorkspaceKey) -> WorkspaceKey:
    """Normalize empty ownership components while retaining request context."""

    return WorkspaceKey(
        tenant_id=workspace_key.tenant_id or "default",
        workspace_id=workspace_key.workspace_id or "default",
        namespace=workspace_key.namespace or "default",
        user_id=workspace_key.user_id,
        session_id=workspace_key.session_id,
        trace_id=workspace_key.trace_id,
    )


class WaitingForStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class WaitingForEventType(StrEnum):
    CREATED = "created"
    FOLLOWED_UP = "followed_up"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    REOPENED = "reopened"


class WaitingForView(StrEnum):
    OPEN = "open"
    ATTENTION = "attention"
    DUE = "due"
    OVERDUE = "overdue"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    ALL = "all"


class WaitingFor(BaseModel):
    """Current snapshot of one external dependency."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(default_factory=lambda: f"wf_{uuid4().hex}", min_length=4, max_length=80)
    workspace_key: WorkspaceKey
    subject: str = Field(min_length=1, max_length=500)
    waiting_on: str = Field(min_length=1, max_length=200)
    context: str = Field(default="", max_length=4_000)
    status: WaitingForStatus = WaitingForStatus.OPEN
    expected_by: datetime | None = None
    next_review_at: datetime | None = None
    timezone: str = "UTC"
    linked_user_task_id: str | None = Field(default=None, max_length=160)
    linked_reminder_id: str | None = Field(default=None, max_length=160)
    source: str = Field(min_length=1, max_length=64)
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    cancelled_at: datetime | None = None
    resolution_note: str = Field(default="", max_length=4_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision: int = Field(default=1, ge=1)

    @field_validator("subject", "waiting_on", "source")
    @classmethod
    def _strip_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("context", "resolution_note")
    @classmethod
    def _strip_optional_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not value.startswith("wf_"):
            raise ValueError("waiting-for id must start with wf_")
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator(
        "expected_by",
        "next_review_at",
        "created_at",
        "updated_at",
        "resolved_at",
        "cancelled_at",
    )
    @classmethod
    def _normalize_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("metadata")
    @classmethod
    def _metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_metadata(value)

    @model_validator(mode="after")
    def _validate_state(self) -> "WaitingFor":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.resolved_at is not None and self.cancelled_at is not None:
            raise ValueError("resolved_at and cancelled_at are mutually exclusive")
        if self.status == WaitingForStatus.OPEN:
            if self.resolved_at is not None or self.cancelled_at is not None:
                raise ValueError("open item cannot contain terminal timestamps")
            if self.resolution_note:
                raise ValueError("open item cannot contain a resolution note")
        elif self.status == WaitingForStatus.RESOLVED:
            if self.resolved_at is None or self.cancelled_at is not None:
                raise ValueError("resolved item requires only resolved_at")
        elif self.status == WaitingForStatus.CANCELLED:
            if self.cancelled_at is None or self.resolved_at is not None:
                raise ValueError("cancelled item requires only cancelled_at")
            if self.resolution_note:
                raise ValueError("cancelled item cannot contain a resolution note")
        return self

    def review_due(self, now: datetime) -> bool:
        now = _aware_utc(now)
        return (
            self.status == WaitingForStatus.OPEN
            and self.next_review_at is not None
            and self.next_review_at <= now
        )

    def expected_overdue(self, now: datetime) -> bool:
        now = _aware_utc(now)
        return (
            self.status == WaitingForStatus.OPEN
            and self.expected_by is not None
            and self.expected_by < now
        )

    def attention_due(self, now: datetime) -> bool:
        return self.review_due(now) or self.expected_overdue(now)


class WaitingForEvent(BaseModel):
    """Immutable append-only history entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(default_factory=lambda: f"wfe_{uuid4().hex}", min_length=5, max_length=80)
    waiting_for_id: str = Field(min_length=4, max_length=80)
    workspace_key: WorkspaceKey
    sequence: int = Field(ge=1)
    event_type: WaitingForEventType
    occurred_at: datetime
    note: str = Field(default="", max_length=4_000)
    source: str = Field(min_length=1, max_length=64)
    trace_id: str = Field(default="", max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_event_id(cls, value: str) -> str:
        if not value.startswith("wfe_"):
            raise ValueError("waiting-for event id must start with wfe_")
        return value

    @field_validator("waiting_for_id")
    @classmethod
    def _validate_waiting_for_id(cls, value: str) -> str:
        if not value.startswith("wf_"):
            raise ValueError("waiting-for id must start with wf_")
        return value

    @field_validator("source")
    @classmethod
    def _strip_source(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source must not be blank")
        return value

    @field_validator("note")
    @classmethod
    def _strip_note(cls, value: str) -> str:
        return value.strip()

    @field_validator("occurred_at")
    @classmethod
    def _normalize_occurred_at(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator("metadata")
    @classmethod
    def _event_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_metadata(value)


class WaitingForPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[WaitingFor, ...]
    view: WaitingForView
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool
    generated_at: datetime


class WaitingForEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[WaitingForEvent, ...]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool


class WaitingForMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item: WaitingFor
    event: WaitingForEvent


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)
