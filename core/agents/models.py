"""Agent Layer data models."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from core.errors import FailureInfo

class AgentStatus(str, Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    READY = "ready"
    RUNNING = "running"
    IDLE = "idle"
    STOPPED = "stopped"
    DESTROYED = "destroyed"
    DEGRADED = "degraded"
    ERROR = "error"

class AgentInfo(BaseModel):
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: AgentStatus = AgentStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentRequest(BaseModel):
    user_input: str = ""
    session_id: str = ""
    agent_id: str = ""
    memory_enabled: bool = True
    knowledge_enabled: bool = True
    tools_enabled: bool = True
    trace_id: str = ""
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

class ToolCallRecord(BaseModel):
    tool_name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    success: bool = True
    error: str | None = None
    elapsed_ms: float = 0.0

class AgentResponse(BaseModel):
    answer: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float = 0.0
    session_id: str = ""
    agent_id: str = ""
    status: str = "ok"
    trace_id: str = ""
    retryable: bool = False
    failure: FailureInfo | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class AgentContext(BaseModel):
    session_id: str = ""
    agent_id: str = ""
    memory_items: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_results: list[dict[str, Any]] = Field(default_factory=list)
    tool_state: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str = ""
    messages: list[dict[str, str]] = Field(default_factory=list)
