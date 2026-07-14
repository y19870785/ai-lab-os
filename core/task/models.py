"""Task Runtime 数据模型 —— 统一任务编排中心。

Task = 一个完整的业务任务（可能包含多个 Workflow）。
TaskContext = 跨 Workflow 的共享上下文。
TaskDependency = 任务间依赖关系。
TaskCheckpoint = 任务级快照。
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from core.errors import FailureInfo


# ---- 状态机 ----

class TaskStatus(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    DESTROYED = "destroyed"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    ONE_SHOT = "one_shot"
    RECURRING = "recurring"
    PIPELINE = "pipeline"
    MANUAL = "manual"


class DependencyType(str, Enum):
    AFTER = "after"
    BEFORE = "before"
    ALL_SUCCESS = "all_success"
    ANY_SUCCESS = "any_success"
    ALL_FAILED = "all_failed"
    ANY_FAILED = "any_failed"
    MANUAL = "manual"


# ---- Task 核心模型 ----

class TaskInfo(BaseModel):
    """Task 元数据"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    task_type: TaskType = TaskType.ONE_SHOT
    priority: TaskPriority = TaskPriority.NORMAL
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskRequest(BaseModel):
    """创建 Task 的请求"""
    task_name: str = ""
    task_type: TaskType = TaskType.ONE_SHOT
    priority: TaskPriority = TaskPriority.NORMAL
    workflow_names: list[str] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    dependencies: list["TaskDependency"] = Field(default_factory=list)
    timeout: int = 600
    max_retries: int = 3
    session_id: str = ""
    agent_id: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Task 执行结果"""
    task_id: str = ""
    status: TaskStatus = TaskStatus.COMPLETED
    workflow_results: dict[str, Any] = Field(default_factory=dict)  # wf_name -> result
    total_latency_ms: float = 0.0
    retry_count: int = 0
    errors: list[str] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = ""
    retryable: bool = False
    failure: FailureInfo | None = None


class TaskStatistics(BaseModel):
    """Task 统计"""
    total: int = 0
    active: int = 0
    completed: int = 0
    failed: int = 0
    paused: int = 0
    by_priority: dict[str, int] = Field(default_factory=dict)


# ---- Context + Dependency + Checkpoint ----

class TaskContext(BaseModel):
    """跨 Workflow 共享上下文"""
    task_id: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    memory_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    workflow_ids: list[str] = Field(default_factory=list)
    agent_ids: list[str] = Field(default_factory=list)
    checkpoint_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskDependency(BaseModel):
    """Task 间依赖关系"""
    depends_on_task_id: str = ""
    dependency_type: DependencyType = DependencyType.AFTER
    timeout: int = 0  # 等待超时（秒），0 表示无限等待


class TaskCheckpoint(BaseModel):
    """Task 级快照 —— 用于暂停/恢复"""
    task_id: str = ""
    status: TaskStatus = TaskStatus.RUNNING
    current_workflow_index: int = 0
    completed_workflows: list[str] = Field(default_factory=list)
    context: TaskContext = Field(default_factory=TaskContext)
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
