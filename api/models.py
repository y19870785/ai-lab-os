"""API Models。"""
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from typing import Any

from core.user_tasks import UserTaskPriority, UserTaskStatus
from core.reminders import ReminderOccurrenceStatus, ReminderStatus
from core.inbox import InboxResolvedType, InboxStatus, InboxSuggestedType

class ChatRequest(BaseModel):
    user_input: str = ""
    application_name: str = "ceo-assistant"
    session_id: str = ""
    idempotency_key: str = ""
    stream: bool = False

class ChatResponse(BaseModel):
    answer: str = ""
    status: str = "ok"
    mode: str = "mock"
    trace_id: str = ""
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    priority: UserTaskPriority = UserTaskPriority.MEDIUM
    due_at: datetime | None = None
    timezone: str = "UTC"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: UserTaskPriority | None = None
    due_at: datetime | None = None
    timezone: str | None = None
    metadata: dict[str, Any] | None = None
    revision: int | None = Field(default=None, ge=1)

class TaskResponse(BaseModel):
    id: str
    title: str
    description: str = ""
    status: UserTaskStatus
    priority: UserTaskPriority
    due_at: datetime | None = None
    timezone: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    source: str
    session_id: str = ""
    agent_id: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision: int
    overdue: bool = False


class ReminderCreateRequest(BaseModel):
    remind_at: datetime
    timezone: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReminderUpdateRequest(BaseModel):
    scheduled_for: datetime | None = None
    remind_at: datetime | None = None
    timezone: str
    revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_one_schedule(self):
        if self.scheduled_for is None and self.remind_at is None:
            raise ValueError("scheduled_for is required")
        if self.scheduled_for is not None and self.remind_at is not None:
            raise ValueError("scheduled_for and remind_at are mutually exclusive")
        return self

    @property
    def target_time(self) -> datetime:
        if self.scheduled_for is not None:
            return self.scheduled_for
        assert self.remind_at is not None
        return self.remind_at


class ReminderResponse(BaseModel):
    id: str
    user_task_id: str
    remind_at: datetime
    timezone: str
    status: ReminderStatus
    scheduler_job_id: str | None = None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None = None
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision: int


class ReminderOccurrenceResponse(BaseModel):
    id: str
    reminder_id: str
    user_task_id: str
    scheduled_at: datetime
    triggered_at: datetime | None = None
    status: ReminderOccurrenceStatus
    trace_id: str = ""
    idempotency_key: str
    attempt: int

class AppInfo(BaseModel):
    application_id: str = ""
    name: str = ""
    version: str = ""
    status: str = ""

class APIErrorResponse(BaseModel):
    status: str = "error"
    code: str = ""
    message: str = ""
    component: str = "api"
    retryable: bool = False
    trace_id: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


ErrorResponse = APIErrorResponse


class InboxCaptureRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    suggested_type: InboxSuggestedType = InboxSuggestedType.UNKNOWN


class InboxResolveTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    due_at: datetime | None = None
    priority: UserTaskPriority = UserTaskPriority.MEDIUM


class InboxResolveReminderRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    scheduled_at: datetime
    timezone: str
    description: str = ""
    priority: UserTaskPriority = UserTaskPriority.MEDIUM


class InboxResolveWorkLogRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""


class InboxItemResponse(BaseModel):
    id: str
    content: str
    source: str
    status: InboxStatus
    suggested_type: InboxSuggestedType
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    resolved_type: InboxResolvedType | None = None
    resolved_target_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision: int


class InboxPageResponse(BaseModel):
    items: list[InboxItemResponse]
    status: InboxStatus | None
    limit: int
    offset: int
    has_more: bool
