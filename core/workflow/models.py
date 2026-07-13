"""Workflow Engine 数据模型 —— AI-Lab 任务调度中心的核心数据结构。

Workflow = 一个完整的任务执行单元。
Step = Workflow 中的一个步骤，每步调用 Agent 或 Tool。
Plan = 执行计划，由 Planner 生成。
Checkpoint = 快照，用于恢复。
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ---- Workflow 状态机 ----

class WorkflowStatus(str, Enum):
    CREATED = "created"
    READY = "ready"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(str, Enum):
    AGENT_CALL = "agent_call"
    TOOL_CALL = "tool_call"
    CONDITION = "condition"
    PARALLEL = "parallel"
    WAIT = "wait"


# ---- Workflow 定义 ----

class WorkflowInfo(BaseModel):
    """Workflow 元数据 —— 注册到 Registry"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkflowStep(BaseModel):
    """Workflow 中的一个步骤"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:8])
    name: str = ""
    step_type: StepType = StepType.AGENT_CALL
    agent_name: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout: int = 60
    max_retries: int = 1
    depends_on: list[str] = Field(default_factory=list)  # 依赖的其他 step id
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    retry_count: int = 0


class WorkflowPlan(BaseModel):
    """Planner 生成的执行计划"""
    workflow_id: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    estimated_steps: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRequest(BaseModel):
    """触发 Workflow 的请求"""
    workflow_name: str = ""
    workflow_id: str = ""
    user_input: str = ""
    session_id: str = ""
    agent_id: str = ""
    trace_id: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    """Workflow 执行结果"""
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.COMPLETED
    steps_completed: int = 0
    steps_failed: int = 0
    total_latency_ms: float = 0.0
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


# ---- Checkpoint ----

class WorkflowCheckpoint(BaseModel):
    """Workflow 快照 —— 用于暂停/恢复"""
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.RUNNING
    current_step_index: int = 0
    completed_step_ids: list[str] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    step_outputs: dict[str, Any] = Field(default_factory=dict)  # step_id -> output
    retry_counts: dict[str, int] = Field(default_factory=dict)  # step_id -> count
    memory_refs: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
