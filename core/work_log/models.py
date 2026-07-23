"""Canonical Work Log domain models and validation rules."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.workspace.models import WorkspaceKey


CANONICAL_ID_PATTERN = re.compile(r"^wl_[0-9a-f]{32}$")
LEGACY_ID_PATTERN = re.compile(r"^wl_legacy_[0-9a-f]{64}$")
INBOX_ALIAS_PATTERN = re.compile(r"^inbox_wl_[0-9a-f]{24}$")
_CONTEXT_ID_PATTERNS = {
    "user_task": re.compile(r"^ut_[A-Za-z0-9][A-Za-z0-9_-]{0,155}$"),
    "reminder": re.compile(r"^rem_[A-Za-z0-9][A-Za-z0-9_-]{0,155}$"),
    "waiting_for": re.compile(r"^wf_[A-Za-z0-9][A-Za-z0-9_-]{0,155}$"),
    "inbox": re.compile(r"^inbox_[A-Za-z0-9][A-Za-z0-9_-]{0,153}$"),
}


def is_context_target_id(value: str) -> bool:
    return not value.startswith("inbox_wl_") and any(
        pattern.fullmatch(value) for pattern in _CONTEXT_ID_PATTERNS.values()
    )


def canonical_workspace(workspace_key: WorkspaceKey) -> WorkspaceKey:
    """Normalize empty ownership components without losing request context."""

    return WorkspaceKey(
        tenant_id=workspace_key.tenant_id or "default",
        workspace_id=workspace_key.workspace_id or "default",
        namespace=workspace_key.namespace or "default",
        user_id=workspace_key.user_id,
        session_id=workspace_key.session_id,
        trace_id=workspace_key.trace_id,
    )


class WorkLogStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    INFORMATIONAL = "informational"


class WorkLogSource(StrEnum):
    CEO_ASSISTANT = "ceo_assistant"
    API = "api"
    CLI = "cli"
    INBOX = "inbox"
    LEGACY = "legacy"


class WorkLogContextKind(StrEnum):
    USER_TASK = "user_task"
    REMINDER = "reminder"
    WAITING_FOR = "waiting_for"
    INBOX = "inbox"


class WorkLogContextResolution(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    NOT_CHECKED = "not_checked"


class WorkLogContextRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: WorkLogContextKind
    target_id: str
    relation: str | None = Field(default=None, max_length=64)
    resolution: WorkLogContextResolution = WorkLogContextResolution.NOT_CHECKED

    @field_validator("target_id")
    @classmethod
    def _target_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("context target id must not be blank")
        return value

    @field_validator("relation")
    @classmethod
    def _relation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _kind_matches_id(self) -> Self:
        pattern = _CONTEXT_ID_PATTERNS[self.kind.value]
        if not pattern.fullmatch(self.target_id) or self.target_id.startswith(
            "inbox_wl_"
        ):
            raise ValueError("context kind and canonical target id do not match")
        return self


def normalize_tags(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        if len(item) > 64:
            raise ValueError("work log tag is too long")
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    if len(normalized) > 20:
        raise ValueError("work log accepts at most 20 tags")
    return tuple(normalized)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iana_timezone(value: str) -> str:
    value = value.strip()
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timezone must be a valid IANA name") from exc
    return value


class WorkLogRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    workspace_key: WorkspaceKey
    occurred_at: datetime
    timezone: str
    subject: str = Field(min_length=1, max_length=500)
    raw_text: str = Field(min_length=1, max_length=4_000)
    target: str | None = Field(default=None, max_length=200)
    status: WorkLogStatus = WorkLogStatus.COMPLETED
    tags: tuple[str, ...] = ()
    source: WorkLogSource
    context_refs: tuple[WorkLogContextRef, ...] = ()
    created_at: datetime
    legacy_memory_id: str | None = None
    legacy_raw_status: str | None = None
    legacy_raw_source: str | None = None
    legacy_projection_notes: tuple[str, ...] = ()
    schema_version: int = Field(ge=0, le=1)
    inbox_item_id: str | None = None

    @field_validator("id")
    @classmethod
    def _id(cls, value: str) -> str:
        if not (
            CANONICAL_ID_PATTERN.fullmatch(value)
            or LEGACY_ID_PATTERN.fullmatch(value)
        ):
            raise ValueError("work log id is not canonical")
        return value

    @field_validator("workspace_key")
    @classmethod
    def _workspace(cls, value: WorkspaceKey) -> WorkspaceKey:
        return canonical_workspace(value)

    @field_validator("occurred_at", "created_at")
    @classmethod
    def _datetime(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        return _iana_timezone(value)

    @field_validator("subject", "raw_text")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("work log text must not be blank")
        return value

    @field_validator("target")
    @classmethod
    def _target(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value) -> tuple[str, ...]:
        return normalize_tags(value or ())

    @field_validator("context_refs")
    @classmethod
    def _refs(
        cls, value: tuple[WorkLogContextRef, ...]
    ) -> tuple[WorkLogContextRef, ...]:
        if len(value) > 20:
            raise ValueError("work log accepts at most 20 context refs")
        identities = [(item.kind.value, item.target_id) for item in value]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate context refs are not allowed")
        return value

    @model_validator(mode="after")
    def _schema_identity(self) -> Self:
        if self.id.startswith("wl_legacy_") and self.schema_version != 0:
            raise ValueError("legacy projection schema_version must be 0")
        if CANONICAL_ID_PATTERN.fullmatch(self.id) and self.schema_version != 1:
            raise ValueError("canonical work log schema_version must be 1")
        return self


class WorkLogCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1, max_length=500)
    raw_text: str = Field(min_length=1, max_length=4_000)
    occurred_at: datetime | None = None
    timezone: str | None = None
    target: str | None = Field(default=None, max_length=200)
    status: WorkLogStatus = WorkLogStatus.COMPLETED
    tags: tuple[str, ...] = ()
    source: WorkLogSource
    context_refs: tuple[WorkLogContextRef, ...] = ()

    @field_validator("subject", "raw_text")
    @classmethod
    def _text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("work log text must not be blank")
        return value

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware_utc(value)

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str | None) -> str | None:
        return None if value is None else _iana_timezone(value)

    @field_validator("target")
    @classmethod
    def _target(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value) -> tuple[str, ...]:
        return normalize_tags(value or ())

    @field_validator("context_refs")
    @classmethod
    def _refs(
        cls, value: tuple[WorkLogContextRef, ...]
    ) -> tuple[WorkLogContextRef, ...]:
        if len(value) > 20:
            raise ValueError("work log accepts at most 20 context refs")
        identities = [(item.kind.value, item.target_id) for item in value]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate context refs are not allowed")
        return value


class WorkLogQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date_from: datetime | None = None
    date_to: datetime | None = None
    target: str | None = Field(default=None, max_length=200)
    tags: tuple[str, ...] = ()
    status: WorkLogStatus | None = None
    text: str | None = Field(default=None, max_length=500)
    context_ref: str | None = Field(default=None, max_length=160)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=10_000)
    sort: str = "occurred_at_desc_id_desc"

    @field_validator("date_from", "date_to")
    @classmethod
    def _dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware_utc(value)

    @field_validator("target", "text", "context_ref")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("work log query text must not be blank")
        return value

    @field_validator("context_ref")
    @classmethod
    def _context_ref(cls, value: str | None) -> str | None:
        if value is not None and not is_context_target_id(value):
            raise ValueError("work log context reference is invalid")
        return value

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value) -> tuple[str, ...]:
        return normalize_tags(value or ())

    @field_validator("sort")
    @classmethod
    def _sort(cls, value: str) -> str:
        if value != "occurred_at_desc_id_desc":
            raise ValueError("unsupported work log sort")
        return value

    @model_validator(mode="after")
    def _range(self) -> Self:
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from >= self.date_to
        ):
            raise ValueError("date_from must precede date_to")
        return self


class WorkLogPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[WorkLogRecord, ...]
    count: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0, le=10_000)
    has_more: bool
    total_count: int = Field(ge=0)
