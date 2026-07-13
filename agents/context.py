"""Agent 上下文管理。管理 Agent 单次运行的状态——输入、工具调用、产出。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentTask(BaseModel):
    """交给 Agent 执行的任务。"""
    task_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    agent_id: str
    user_id: str = ""

    # 任务内容
    instruction: str
    input_data: dict[str, Any] = {}
    context: dict[str, Any] = {}

    # 约束
    max_tokens: int = 32000
    max_tool_calls: int = 50
    timeout: int = 120
    require_approval: bool = False


class AgentResult(BaseModel):
    """Agent 执行结果。"""
    task_id: str
    agent_id: str
    success: bool
    output: Any = None
    error: str | None = None
    token_usage: int = 0
    tool_calls_count: int = 0
    elapsed_ms: int = 0
    completed_at: datetime | None = None
