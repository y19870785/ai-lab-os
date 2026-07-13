"""WorkflowRegistry —— Workflow 注册与发现中心"""

from __future__ import annotations
from typing import Callable
from core.workflow.models import WorkflowInfo
from core.workflow.protocol import WorkflowProtocol
from core.workflow.exceptions import WorkflowNotFoundError

WorkflowFactory = Callable[[], WorkflowProtocol]


class WorkflowRegistry:
    """Workflow 注册中心"""

    def __init__(self):
        self._workflows: dict[str, WorkflowInfo] = {}
        self._factories: dict[str, WorkflowFactory] = {}

    def register(self, info: WorkflowInfo, factory: WorkflowFactory) -> None:
        """注册一个 Workflow"""
        self._workflows[info.name] = info
        self._factories[info.name] = factory

    def unregister(self, name: str) -> bool:
        """移除一个 Workflow"""
        self._factories.pop(name, None)
        return self._workflows.pop(name, None) is not None

    def get(self, name: str) -> WorkflowProtocol:
        """获取 Workflow 实例（懒加载）"""
        factory = self._factories.get(name)
        if factory is None:
            raise WorkflowNotFoundError(f"Workflow not found: {name}")
        return factory()

    def get_info(self, name: str) -> WorkflowInfo:
        """获取 Workflow 元数据"""
        info = self._workflows.get(name)
        if info is None:
            raise WorkflowNotFoundError(f"Workflow not found: {name}")
        return info

    def list(self) -> list[WorkflowInfo]:
        """列出所有 Workflow"""
        return list(self._workflows.values())

    def list_names(self) -> list[str]:
        """列出所有 Workflow 名称"""
        return list(self._workflows.keys())

    def search(self, tag: str = "", capability: str = "", name_pattern: str = "") -> list[WorkflowInfo]:
        """搜索 Workflow"""
        results = list(self._workflows.values())
        if tag:
            results = [w for w in results if tag in w.tags]
        if capability:
            results = [w for w in results if capability in w.capabilities]
        if name_pattern:
            results = [w for w in results if name_pattern.lower() in w.name.lower()]
        return results

    def exists(self, name: str) -> bool:
        return name in self._workflows

    @property
    def count(self) -> int:
        return len(self._workflows)
