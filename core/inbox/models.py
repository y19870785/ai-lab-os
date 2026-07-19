"""Domain models for the unified Inbox."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.workspace.models import WorkspaceKey


MAX_INBOX_CONTENT_LENGTH = 4_000


def _contains_sensitive_key(value: Any) -> bool:
    sensitive = {"api_key", "apikey", "token", "secret", "password", "authorization"}
    if isinstance(value, dict):
        return any(
            str(key).strip().lower().replace("-", "_") in sensitive
            or _contains_sensitive_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


class InboxStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class InboxSuggestedType(StrEnum):
    TASK = "task"
    REMINDER = "reminder"
    WORK_LOG = "work_log"
    NOTE = "note"
    UNKNOWN = "unknown"


class InboxResolvedType(StrEnum):
    USER_TASK = "user_task"
    REMINDER = "reminder"
    WORK_LOG = "work_log"
    NOTE = "note"
    DISMISSED = "dismissed"


class InboxItem(BaseModel):
    """A captured item awaiting an explicit human resolution decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(default_factory=lambda: f"inbox_{uuid4().hex}", min_length=1, max_length=80)
    workspace_key: WorkspaceKey
    content: str = Field(min_length=1, max_length=MAX_INBOX_CONTENT_LENGTH)
    source: str = Field(min_length=1, max_length=64)
    status: InboxStatus = InboxStatus.PENDING
    suggested_type: InboxSuggestedType = InboxSuggestedType.UNKNOWN
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    resolved_type: InboxResolvedType | None = None
    resolved_target_id: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision: int = Field(default=1, ge=1)

    @field_validator("content", "source")
    @classmethod
    def _strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @field_validator("created_at", "updated_at", "resolved_at")
    @classmethod
    def _normalize_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_sensitive_key(value):
            raise ValueError("inbox metadata contains a sensitive key")
        try:
            json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("inbox metadata must be JSON serializable") from exc
        return value

    @model_validator(mode="after")
    def _validate_state(self) -> "InboxItem":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")

        resolution_fields = (self.resolved_at, self.resolved_type, self.resolved_target_id)
        if self.status == InboxStatus.PENDING:
            if any(value is not None for value in resolution_fields):
                raise ValueError("pending item cannot contain resolution fields")
            return self

        if self.resolved_at is None or self.resolved_type is None:
            raise ValueError("non-pending item requires resolved_at and resolved_type")
        if self.resolved_at < self.created_at:
            raise ValueError("resolved_at must not precede created_at")

        if self.status == InboxStatus.DISMISSED:
            if self.resolved_type != InboxResolvedType.DISMISSED:
                raise ValueError("dismissed item requires resolved_type=dismissed")
            if self.resolved_target_id is not None:
                raise ValueError("dismissed item cannot have a target")
            return self

        if self.resolved_type == InboxResolvedType.DISMISSED:
            raise ValueError("resolved item cannot use resolved_type=dismissed")
        if self.resolved_type == InboxResolvedType.NOTE:
            if self.resolved_target_id is not None:
                raise ValueError("note resolution cannot have a target")
        elif not self.resolved_target_id:
            raise ValueError("resolved target id is required for this resolution type")
        return self


class InboxPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[InboxItem, ...]
    status: InboxStatus | None
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool


def canonical_workspace(workspace_key: WorkspaceKey) -> WorkspaceKey:
    """Normalize empty workspace components to the canonical default scope."""

    return WorkspaceKey(
        tenant_id=workspace_key.tenant_id or "default",
        workspace_id=workspace_key.workspace_id or "default",
        namespace=workspace_key.namespace or "default",
        session_id=workspace_key.session_id,
        user_id=workspace_key.user_id,
        trace_id=workspace_key.trace_id,
    )
