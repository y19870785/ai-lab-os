"""Tool System data models."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class ToolStatus(str, Enum):
    REGISTERED = "registered"
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    DISABLED = "disabled"

class ToolCategory(str, Enum):
    UTILITY = "utility"
    DATA = "data"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    SYSTEM = "system"
    EXTERNAL = "external"
    CUSTOM = "custom"

class ToolPermission(str, Enum):
    READ = "read"
    WRITE = "write"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    SYSTEM = "system"
    DATABASE = "database"
    EXECUTE = "execute"

class ParameterSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)

class ToolInfo(BaseModel):
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: ToolCategory = ToolCategory.UTILITY
    tags: list[str] = Field(default_factory=list)
    parameters: ParameterSchema = Field(default_factory=ParameterSchema)
    return_schema: ParameterSchema = Field(default_factory=ParameterSchema)
    permissions: list[ToolPermission] = Field(default_factory=list)
    timeout: int = 30
    max_retries: int = 0
    status: ToolStatus = ToolStatus.REGISTERED
    metadata: dict[str, Any] = Field(default_factory=dict)

class ToolRequest(BaseModel):
    tool_name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""
    agent_id: str = ""
    trace_id: str = ""

class ToolResult(BaseModel):
    success: bool = False
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    token_usage: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)