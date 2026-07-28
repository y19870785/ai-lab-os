"""Structured contracts for the deterministic Daily Review read model."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

DEFAULT_DAILY_REVIEW_LIMIT = 50
DEFAULT_DAILY_REVIEW_OFFSET = 0


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Daily Review datetimes must be timezone-aware")
    return value.astimezone(UTC)


class DailyReviewDate(StrEnum):
    TODAY = "today"
    YESTERDAY = "yesterday"


class DailyReviewSourceType(StrEnum):
    WORK_LOG = "work_log"
    USER_TASK = "user_task"
    WAITING_FOR = "waiting_for"
    REMINDER = "reminder"
    INBOX = "inbox"


class DailyReviewSourceStatus(StrEnum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"


class DailyReviewQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_date: DailyReviewDate
    limit: int = Field(default=DEFAULT_DAILY_REVIEW_LIMIT, ge=1, le=100)
    offset: int = Field(default=DEFAULT_DAILY_REVIEW_OFFSET, ge=0)


class DailyReviewWorkspace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    workspace_id: str
    namespace: str

    @field_validator("tenant_id", "workspace_id", "namespace", mode="before")
    @classmethod
    def _normalize_component(cls, value: object) -> str:
        return str(value or "").strip() or "default"


class DailyReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: DailyReviewSourceType
    source_id: str
    title: str
    status: str
    reason_code: str
    effective_at: datetime | None
    relevant_time_fields: dict[str, datetime] = Field(default_factory=dict)

    @field_validator("source_id", "title", "status", "reason_code")
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Daily Review item text must not be blank")
        return normalized

    @field_validator("effective_at")
    @classmethod
    def _effective_at(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)

    @field_validator("relevant_time_fields")
    @classmethod
    def _relevant_times(cls, value: dict[str, datetime]) -> dict[str, datetime]:
        return {
            str(key): _aware_utc(item)
            for key, item in value.items()
            if item is not None
        }


class DailyReviewSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_total_count: int = Field(ge=0)
    page_item_count: int = Field(ge=0)
    items: tuple[DailyReviewItem, ...] = ()

    @model_validator(mode="after")
    def _page_count_matches_items(self) -> Self:
        if self.page_item_count != len(self.items):
            raise ValueError("page_item_count must equal the item count")
        if self.page_item_count > self.section_total_count:
            raise ValueError("page_item_count cannot exceed section_total_count")
        return self


class DailyReviewPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool

    @model_validator(mode="after")
    def _validate_page(self) -> Self:
        if self.count > self.limit:
            raise ValueError("page count cannot exceed limit")
        expected_has_more = self.offset + self.count < self.total_count
        if self.has_more != expected_has_more:
            raise ValueError("has_more does not match page metadata")
        return self


class DailyReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace: DailyReviewWorkspace
    review_date: date
    timezone: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    as_of: datetime
    source_status: dict[DailyReviewSourceType, DailyReviewSourceStatus]
    page: DailyReviewPage
    completed: DailyReviewSection
    in_progress: DailyReviewSection
    blocked: DailyReviewSection
    informational: DailyReviewSection
    follow_ups: DailyReviewSection
    pending_inbox: DailyReviewSection

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return normalized

    @field_validator(
        "period_start",
        "period_end",
        "generated_at",
        "as_of",
    )
    @classmethod
    def _datetimes(cls, value: datetime) -> datetime:
        normalized = _aware_utc(value)
        if normalized is None:  # pragma: no cover - non-optional field guard
            raise ValueError("Daily Review datetime is required")
        return normalized

    @model_validator(mode="after")
    def _validate_review(self) -> Self:
        if self.period_start >= self.period_end:
            raise ValueError("period_start must precede period_end")
        if self.generated_at != self.as_of:
            raise ValueError("generated_at and as_of must use one instant")
        expected_sources = set(DailyReviewSourceType)
        if set(self.source_status) != expected_sources:
            raise ValueError("source_status must cover every canonical source")
        sections = (
            self.completed,
            self.in_progress,
            self.blocked,
            self.informational,
            self.follow_ups,
            self.pending_inbox,
        )
        if sum(section.section_total_count for section in sections) != self.page.total_count:
            raise ValueError("section totals must equal page total_count")
        if sum(section.page_item_count for section in sections) != self.page.count:
            raise ValueError("section page counts must equal page count")
        return self
