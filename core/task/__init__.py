"""AI-Lab Task Runtime —— 统一任务编排中心。

Task Runtime 是 Scheduler + Workflow 之上的统一协调层。
回答"为什么执行、谁负责整个任务生命周期、多个 Workflow 如何组合"。

架构位置：
    Application → Task → Scheduler → Workflow → Agent → Knowledge → Provider → Tool
"""

from core.task.models import (
    TaskInfo, TaskRequest, TaskResult, TaskContext, TaskCheckpoint,
    TaskDependency, TaskStatistics, TaskStatus, TaskPriority, TaskType,
    DependencyType,
)
from core.task.protocol import TaskProtocol
from core.task.runtime import TaskRuntime
from core.task.manager import TaskManager
from core.task.registry import TaskRegistry
from core.task.planner import RuleTaskPlanner, TaskPlannerProtocol, get_task_planner
from core.task.state import TaskStateMachine
from core.task.dependencies import DependencyResolver
from core.task.context import ContextManager
from core.task.checkpoint import CheckpointManager
from core.task.config import TaskConfig
from core.task.events import TaskEventTypes, publish_task_event
from core.task.exceptions import (
    TaskError, TaskTimeout, TaskCancelled, TaskPlanningError,
    TaskExecutionError, TaskDependencyError, TaskNotFoundError, TaskStateError,
)

__all__ = [
    # Models
    "TaskInfo", "TaskRequest", "TaskResult", "TaskContext", "TaskCheckpoint",
    "TaskDependency", "TaskStatistics", "TaskStatus", "TaskPriority", "TaskType",
    "DependencyType",
    # Core
    "TaskProtocol", "TaskRuntime", "TaskManager", "TaskRegistry",
    "TaskStateMachine", "DependencyResolver", "ContextManager", "CheckpointManager",
    # Planner
    "RuleTaskPlanner", "TaskPlannerProtocol", "get_task_planner",
    # Config
    "TaskConfig",
    # Events
    "TaskEventTypes", "publish_task_event",
    # Exceptions
    "TaskError", "TaskTimeout", "TaskCancelled", "TaskPlanningError",
    "TaskExecutionError", "TaskDependencyError", "TaskNotFoundError", "TaskStateError",
]
