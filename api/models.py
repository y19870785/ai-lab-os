"""API Models。"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any

from core.user_tasks import UserTaskPriority, UserTaskStatus
from core.reminders import ReminderOccurrenceStatus, ReminderStatus

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
    remind_at: datetime
    timezone: str
    revision: int | None = Field(default=None, ge=1)


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
