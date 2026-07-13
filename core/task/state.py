"""Task 状态机 —— 11 状态统一管理。禁止 if-else 直接切换状态。"""

from __future__ import annotations
from core.task.models import TaskStatus
from core.task.exceptions import TaskStateError

_VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.WAITING, TaskStatus.PAUSED, TaskStatus.COMPLETED,
        TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.TIMEOUT},
    TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.RETRYING, TaskStatus.DESTROYED},
    TaskStatus.RETRYING: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.TIMEOUT: {TaskStatus.RETRYING, TaskStatus.DESTROYED},
    TaskStatus.CANCELLED: {TaskStatus.DESTROYED},
    TaskStatus.COMPLETED: {TaskStatus.DESTROYED},
    TaskStatus.DESTROYED: set(),
}


class TaskStateMachine:
    """Task 状态机"""

    def __init__(self, initial: TaskStatus = TaskStatus.CREATED):
        self._current = initial

    @property
    def current(self) -> TaskStatus:
        return self._current

    def can_transition(self, target: TaskStatus) -> bool:
        return target in _VALID_TRANSITIONS.get(self._current, set())

    def transition(self, target: TaskStatus) -> None:
        if not self.can_transition(target):
            raise TaskStateError(f"非法状态转换: {self._current.value} -> {target.value}")
        self._current = target

    def is_terminal(self) -> bool:
        return self._current in {TaskStatus.COMPLETED, TaskStatus.FAILED,
                                 TaskStatus.CANCELLED, TaskStatus.DESTROYED, TaskStatus.TIMEOUT}

    def is_runnable(self) -> bool:
        return self._current in {TaskStatus.READY, TaskStatus.RETRYING}

    def reset(self) -> None:
        self._current = TaskStatus.CREATED
