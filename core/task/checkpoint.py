"""TaskCheckpointManager —— 管理 Task 级快照。

每个 Workflow 执行完成后自动保存快照。
支持 SQLite / Redis / 远程存储（当前：内存模式）。
"""

from __future__ import annotations
from core.task.models import TaskCheckpoint, TaskStatus


class CheckpointManager:
    """Task 快照管理器 —— 内存模式"""

    def __init__(self):
        self._checkpoints: dict[str, TaskCheckpoint] = {}

    def save(self, checkpoint: TaskCheckpoint) -> None:
        self._checkpoints[checkpoint.task_id] = checkpoint

    def load(self, task_id: str) -> TaskCheckpoint | None:
        return self._checkpoints.get(task_id)

    def delete(self, task_id: str) -> bool:
        return self._checkpoints.pop(task_id, None) is not None

    def exists(self, task_id: str) -> bool:
        return task_id in self._checkpoints

    def list_ids(self) -> list[str]:
        return list(self._checkpoints.keys())

    @property
    def count(self) -> int:
        return len(self._checkpoints)
