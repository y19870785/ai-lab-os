"""Multi-Agent Coordination —— 数据模型。

定义 Agent 协作所需的核心数据结构：
AgentRole、AgentMessage、AgentTask、CollaborationContext、AgentCapability。
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ---- Enums ----

class AgentRoleType(str, Enum):
    """预定义的 Agent 角色类型。可扩展。"""
    PLANNER = "planner"
    RESEARCHER = "researcher"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    EXECUTOR = "executor"
    COORDINATOR = "coordinator"
    ANALYST = "analyst"
    CUSTOM = "custom"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DelegationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    REJECTED = "rejected"


class CoordinationStatus(str, Enum):
    """Orchestrator 协调状态。"""
    CREATED = "created"
    PLANNING = "planning"
    DISPATCHING = "dispatching"
    RUNNING = "running"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---- Agent Role ----

class AgentCapability(BaseModel):
    """Agent 能力声明。"""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)


class AgentRole(BaseModel):
    """Agent 角色定义。

    每个角色声明其能力和允许的工具集。
    """
    role_type: AgentRoleType = AgentRoleType.CUSTOM
    name: str = ""
    description: str = ""
    capabilities: list[AgentCapability] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    system_prompt_template: str = ""
    priority: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- Agent Message ----

class AgentMessage(BaseModel):
    """Agent 间通信消息。

    支持点对点（有 receiver）和广播（无 receiver）。
    """
    message_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    sender: str = ""          # agent_id
    receiver: str = ""        # agent_id 或空（广播）
    conversation_id: str = ""  # 会话追踪
    message_type: str = "text"  # text | task | result | error | handoff
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentMessageResponse(BaseModel):
    """消息响应。"""
    original_message_id: str = ""
    responder: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---- Agent Task (Delegation) ----

class AgentTask(BaseModel):
    """可委派的 Agent 子任务。

    复用 Task Runtime 的生命周期，增加 Agent 特定上下文。
    """
    task_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    parent_task_id: str = ""
    assigned_agent: str = ""       # agent_id
    assigned_role: AgentRoleType = AgentRoleType.EXECUTOR
    title: str = ""
    description: str = ""
    input_data: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = ""
    status: DelegationStatus = DelegationStatus.PENDING
    timeout: int = 300
    max_retries: int = 2
    priority: int = 5
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- Collaboration Context ----

class CollaborationContext(BaseModel):
    """多 Agent 协作共享上下文。

    不要直接共享 Memory。中间结果写这里，
    最终结果才写入 Memory / Knowledge。
    """
    session_id: str = ""
    goal: str = ""
    plan: list[dict[str, Any]] = Field(default_factory=list)
    active_agents: list[str] = Field(default_factory=list)
    intermediate_results: dict[str, Any] = Field(default_factory=dict)  # agent_id -> result
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    conversation_history: list[AgentMessage] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    status: CoordinationStatus = CoordinationStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- Team Configuration ----

class TeamConfig(BaseModel):
    """Agent Team 配置。"""
    team_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    description: str = ""
    agents: list[str] = Field(default_factory=list)  # agent_ids
    roles: dict[str, AgentRole] = Field(default_factory=dict)  # agent_id -> role
    coordinator_agent: str = ""  # designated coordinator
    max_parallel: int = 5
    default_timeout: int = 300
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- Orchestrator Result ----

class CoordinationResult(BaseModel):
    """Orchestrator 执行结果。"""
    session_id: str = ""
    status: CoordinationStatus = CoordinationStatus.COMPLETED
    goal: str = ""
    agent_results: dict[str, Any] = Field(default_factory=dict)  # agent_id -> AgentResponse
    merged_result: str = ""
    intermediate_steps: list[dict[str, Any]] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    agent_count: int = 0
    message_count: int = 0
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
