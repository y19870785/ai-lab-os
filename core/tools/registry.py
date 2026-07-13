"""ToolRegistry — registration, discovery, and auto-discovery."""
from __future__ import annotations
from typing import Callable
from core.tools.models import ToolInfo, ToolStatus
from core.tools.protocol import ToolProtocol
from core.tools.exceptions import ToolNotFoundError, ToolNotReadyError

ToolFactory = Callable[[], ToolProtocol]

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}
        self._instances: dict[str, ToolProtocol] = {}
        self._factories: dict[str, ToolFactory] = {}
    def register(self, info: ToolInfo, factory: ToolFactory) -> None:
        self._tools[info.name] = info
        self._factories[info.name] = factory
    def unregister(self, name: str) -> bool:
        self._instances.pop(name, None)
        self._factories.pop(name, None)
        return self._tools.pop(name, None) is not None
    def get(self, name: str) -> ToolProtocol:
        if name in self._instances:
            return self._instances[name]
        factory = self._factories.get(name)
        if factory is None:
            raise ToolNotFoundError(f"Tool not found: {name}")
        instance = factory()
        self._instances[name] = instance
        return instance
    def get_info(self, name: str) -> ToolInfo:
        info = self._tools.get(name)
        if info is None: raise ToolNotFoundError(f"Tool not found: {name}")
        return info
    def list(self) -> list[ToolInfo]:
        return list(self._tools.values())
    def search(self, category: str | None = None, tag: str | None = None, name_pattern: str | None = None) -> list[ToolInfo]:
        results = list(self._tools.values())
        if category:
            results = [t for t in results if t.category.value == category]
        if tag:
            results = [t for t in results if tag in t.tags]
        if name_pattern:
            results = [t for t in results if name_pattern.lower() in t.name.lower()]
        return results
    def list_names(self) -> list[str]:
        return list(self._tools.keys())
    def exists(self, name: str) -> bool:
        return name in self._tools
    @property
    def count(self) -> int:
        return len(self._tools)