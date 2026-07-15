"""API Models。"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any

from core.user_tasks import UserTaskPriority, UserTaskStatus

class ChatRequest(BaseModel):
    user_input: str = ""
    application_name: str = "alpha_assistant"
    session_id: str = ""
    stream: bool = False

class ChatResponse(BaseModel):
    answer: str = ""
    status: str = "ok"
    mode: str = "mock"
    trace_id: str = ""
    latency_ms: float = 0.0

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
    revision: int | None = None

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
