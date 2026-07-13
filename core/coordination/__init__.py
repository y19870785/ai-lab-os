"""AI-Lab Multi-Agent Coordination Layer — 多 Agent 协作协调层。

架构位置：
    Application → Orchestrator → Agent Runtime → Workflow Runtime → Task Runtime

本层负责：
- Agent Team 注册与发现
- Agent 间消息通信
- 任务委派与调度
- 协作上下文管理
- 结果收集与合并

不直接执行任何业务逻辑。
"""

from core.coordination.models import (
    AgentRole, AgentRoleType, AgentMessage, AgentMessageResponse, AgentTask,
    CollaborationContext, TeamConfig, CoordinationResult,
    AgentCapability, DelegationStatus, CoordinationStatus, MessagePriority,
)
from core.coordination.protocol import (
    OrchestratorProtocol, MessageBusProtocol, DelegationProtocol, MergerProtocol,
)
from core.coordination.registry import AgentTeamRegistry
from core.coordination.communication import AgentMessageBus
from core.coordination.delegation import TaskDelegator
from core.coordination.merger import RuleBasedMerger, PriorityMerger
from core.coordination.planner import MultiAgentPlanner
from core.coordination.orchestrator import AgentOrchestrator
from core.coordination.events import CoordinationEventTypes, publish_coordination_event
from core.coordination.config import CoordinationConfig
from core.coordination.exceptions import (
    CoordinationError, TeamNotFoundError, RoleNotFoundError,
    AgentNotInTeamError, DelegationError, OrchestrationError,
    MessageDeliveryError, MergeError, CoordinationTimeoutError,
)

__all__ = [
    # Models
    "AgentRole", "AgentRoleType", "AgentMessage", "AgentMessageResponse",
    "AgentTask", "CollaborationContext", "TeamConfig", "CoordinationResult",
    "AgentCapability", "DelegationStatus", "CoordinationStatus", "MessagePriority",
    # Protocols
    "OrchestratorProtocol", "MessageBusProtocol", "DelegationProtocol", "MergerProtocol",
    # Implementations
    "AgentTeamRegistry", "AgentMessageBus", "TaskDelegator",
    "RuleBasedMerger", "PriorityMerger", "MultiAgentPlanner", "AgentOrchestrator",
    # Events
    "CoordinationEventTypes", "publish_coordination_event",
    # Config
    "CoordinationConfig",
    # Exceptions
    "CoordinationError", "TeamNotFoundError", "RoleNotFoundError",
    "AgentNotInTeamError", "DelegationError", "OrchestrationError",
    "MessageDeliveryError", "MergeError", "CoordinationTimeoutError",
]
