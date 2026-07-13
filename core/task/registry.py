"""TaskRegistry —— Task 注册与发现中心"""

from __future__ import annotations
from core.task.models import TaskInfo, TaskStatus
from core.task.exceptions import TaskNotFoundError


class TaskRegistry:
    """Task 注册中心"""

    def __init__(self):
        self._tasks: dict[str, TaskInfo] = {}
        self._statuses: dict[str, TaskStatus] = {}

    def register(self, info: TaskInfo, status: TaskStatus = TaskStatus.CREATED) -> None:
        self._tasks[info.id] = info
        self._statuses[info.id] = status

    def unregister(self, task_id: str) -> bool:
        self._statuses.pop(task_id, None)
        return self._tasks.pop(task_id, None) is not None

    def get(self, task_id: str) -> TaskInfo:
        info = self._tasks.get(task_id)
        if info is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return info

    def get_status(self, task_id: str) -> TaskStatus | None:
        return self._statuses.get(task_id)

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        self._statuses[task_id] = status

    def list(self) -> list[TaskInfo]:
        return list(self._tasks.values())

    def search(self, tag: str = "", name_pattern: str = "") -> list[TaskInfo]:
        results = list(self._tasks.values())
        if tag:
            results = [t for t in results if tag in t.tags]
        if name_pattern:
            results = [t for t in results if name_pattern.lower() in t.name.lower()]
        return results

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks

    def statistics(self) -> dict:
        stats = {"total": len(self._tasks), "active": 0, "completed": 0,
                 "failed": 0, "paused": 0}
        for s in self._statuses.values():
            if s == TaskStatus.RUNNING or s == TaskStatus.WAITING:
                stats["active"] += 1
            elif s == TaskStatus.COMPLETED:
                stats["completed"] += 1
            elif s == TaskStatus.FAILED:
                stats["failed"] += 1
            elif s == TaskStatus.PAUSED:
                stats["paused"] += 1
        return stats

    @property
    def count(self) -> int:
        return len(self._tasks)
