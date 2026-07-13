"""Workflow 状态机 —— 统一管理所有状态转换。

禁止在代码中散落状态修改，所有转换必须经过此状态机。
"""

from __future__ import annotations
from core.workflow.models import WorkflowStatus
from core.workflow.exceptions import WorkflowStateError

# 合法状态转换表
_VALID_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.CREATED: {WorkflowStatus.READY},
    WorkflowStatus.READY: {WorkflowStatus.PLANNING, WorkflowStatus.CANCELLED},
    WorkflowStatus.PLANNING: {WorkflowStatus.RUNNING, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED},
    WorkflowStatus.RUNNING: {
        WorkflowStatus.WAITING, WorkflowStatus.PAUSED,
        WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.WAITING: {WorkflowStatus.RUNNING, WorkflowStatus.RETRYING, WorkflowStatus.CANCELLED},
    WorkflowStatus.RETRYING: {WorkflowStatus.RUNNING, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED},
    WorkflowStatus.PAUSED: {WorkflowStatus.RESUMED, WorkflowStatus.CANCELLED},
    WorkflowStatus.RESUMED: {WorkflowStatus.RUNNING},
    WorkflowStatus.COMPLETED: set(),  # 终态
    WorkflowStatus.FAILED: {WorkflowStatus.RETRYING},  # 手动重试
    WorkflowStatus.CANCELLED: set(),  # 终态
}


class WorkflowStateMachine:
    """Workflow 状态机"""

    def __init__(self, initial: WorkflowStatus = WorkflowStatus.CREATED):
        self._current = initial

    @property
    def current(self) -> WorkflowStatus:
        return self._current

    def can_transition(self, target: WorkflowStatus) -> bool:
        """检查是否允许转换到目标状态"""
        return target in _VALID_TRANSITIONS.get(self._current, set())

    def transition(self, target: WorkflowStatus) -> None:
        """执行状态转换，非法转换抛出 WorkflowStateError"""
        if not self.can_transition(target):
            raise WorkflowStateError(
                f"非法状态转换: {self._current.value} -> {target.value}"
            )
        self._current = target

    def is_terminal(self) -> bool:
        """是否处于终态（已完成、已失败、已取消）"""
        return self._current in {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}

    def is_runnable(self) -> bool:
        """是否可以执行"""
        return self._current in {WorkflowStatus.READY, WorkflowStatus.RESUMED}

    def reset(self) -> None:
        """重置到初始状态"""
        self._current = WorkflowStatus.CREATED
