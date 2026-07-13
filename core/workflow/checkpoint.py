"""WorkflowCheckpointManager —— 管理 Workflow 快照（暂停/恢复/回放）"""

from __future__ import annotations
from core.workflow.models import WorkflowCheckpoint, WorkflowStatus


class CheckpointManager:
    """Workflow 快照管理器 —— 内存模式"""

    def __init__(self):
        self._checkpoints: dict[str, WorkflowCheckpoint] = {}

    def save(self, checkpoint: WorkflowCheckpoint) -> None:
        """保存快照"""
        self._checkpoints[checkpoint.workflow_id] = checkpoint

    def load(self, workflow_id: str) -> WorkflowCheckpoint | None:
        """加载快照"""
        return self._checkpoints.get(workflow_id)

    def delete(self, workflow_id: str) -> bool:
        """删除快照"""
        return self._checkpoints.pop(workflow_id, None) is not None

    def exists(self, workflow_id: str) -> bool:
        """检查是否存在快照"""
        return workflow_id in self._checkpoints

    def list_ids(self) -> list[str]:
        """列出所有快照的 workflow_id"""
        return list(self._checkpoints.keys())

    @property
    def count(self) -> int:
        return len(self._checkpoints)
