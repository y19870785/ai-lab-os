"""Scheduler 数据模型 —— AI-Lab 统一调度中心的核心数据结构。

Job = 一个可调度的任务。
Trigger = 触发条件（Cron / Interval / One-shot / Manual / Event）。
Schedule = Job + Trigger 的组合。
JobRun = 一次执行记录。
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ---- 枚举 ----

class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONE_SHOT = "one_shot"
    MANUAL = "manual"
    EVENT = "event"


class JobRunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# ---- Trigger ----

class Trigger(BaseModel):
    """触发条件"""
    trigger_type: TriggerType = TriggerType.MANUAL
    # Cron: "*/5 * * * *"
    cron_expression: str = ""
    # Interval: 秒
    interval_seconds: int = 0
    # One-shot: 执行时间
    run_at: datetime | None = None
    # Event: 事件类型
    event_type: str = ""
    # 时区
    timezone: str = "Asia/Shanghai"
    # 下次执行时间（运行时计算）
    next_run_at: datetime | None = None


# ---- Job ----

class JobInfo(BaseModel):
    """Job 元数据 —— 注册到 Registry"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Job(BaseModel):
    """一个可调度的任务"""
    info: JobInfo = Field(default_factory=JobInfo)
    trigger: Trigger = Field(default_factory=Trigger)
    workflow_name: str = ""  # 关联的 Workflow
    workflow_variables: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.ACTIVE
    max_retries: int = 3
    timeout: int = 300  # 秒
    max_concurrent: int = 1
    retry_count: int = 0
    run_count: int = 0
    last_run_at: datetime | None = None
    last_result: str = ""


class JobRun(BaseModel):
    """一次 Job 执行记录"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    job_id: str = ""
    job_name: str = ""
    status: JobRunStatus = JobRunStatus.RUNNING
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    latency_ms: float = 0.0
    result: Any = None
    error: str | None = None


class ScheduleRequest(BaseModel):
    """调度请求"""
    job_name: str = ""
    workflow_name: str = ""
    trigger: Trigger = Field(default_factory=Trigger)
    variables: dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""
    agent_id: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
