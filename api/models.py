"""API Models。"""
from pydantic import BaseModel, Field
from typing import Any

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
    name: str = ""
    workflow_names: list[str] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)

class TaskResponse(BaseModel):
    task_id: str = ""
    status: str = ""
    result: dict[str, Any] = Field(default_factory=dict)

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
