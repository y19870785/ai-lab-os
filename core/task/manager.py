"""TaskManager —— 统一管理所有 Task 的生命周期。

职责：
- Task 注册 / 查询 / 删除
- Task 状态追踪
- Task 统计
"""

from __future__ import annotations
from core.task.models import TaskInfo, TaskStatus, TaskStatistics
from core.task.registry import TaskRegistry
from core.task.exceptions import TaskNotFoundError


class TaskManager:
    """Task 统一管理器"""

    def __init__(self, registry: TaskRegistry | None = None):
        self._registry = registry or TaskRegistry()

    def register(self, info: TaskInfo, status: TaskStatus = TaskStatus.CREATED) -> None:
        self._registry.register(info, status)

    def unregister(self, task_id: str) -> bool:
        return self._registry.unregister(task_id)

    def get(self, task_id: str) -> TaskInfo:
        return self._registry.get(task_id)

    def get_status(self, task_id: str) -> TaskStatus | None:
        return self._registry.get_status(task_id)

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        self._registry.set_status(task_id, status)

    def list(self) -> list[TaskInfo]:
        return self._registry.list()

    def search(self, tag: str = "", name_pattern: str = "") -> list[TaskInfo]:
        return self._registry.search(tag=tag, name_pattern=name_pattern)

    def exists(self, task_id: str) -> bool:
        return self._registry.exists(task_id)

    def statistics(self) -> TaskStatistics:
        raw = self._registry.statistics()
        return TaskStatistics(**raw)

    @property
    def count(self) -> int:
        return self._registry.count
