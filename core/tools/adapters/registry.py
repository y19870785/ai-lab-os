"""AdapterRegistry —— 统一管理所有 ToolAdapter 实例。

支持热插拔：随时添加/移除 Adapter，不影响 ToolExecutor 运行。
"""

from __future__ import annotations

from core.tools.adapters.protocol import ToolAdapterProtocol


class AdapterRegistry:
    """适配器注册中心"""

    def __init__(self):
        self._adapters: dict[str, ToolAdapterProtocol] = {}

    def register(self, adapter: ToolAdapterProtocol) -> None:
        """注册一个适配器"""
        self._adapters[adapter.name] = adapter

    def unregister(self, name: str) -> bool:
        """移除一个适配器"""
        return self._adapters.pop(name, None) is not None

    def get(self, name: str) -> ToolAdapterProtocol | None:
        """获取指定适配器"""
        return self._adapters.get(name)

    def list_names(self) -> list[str]:
        """列出所有适配器名称"""
        return list(self._adapters.keys())

    def list_all(self) -> list[ToolAdapterProtocol]:
        """列出所有适配器实例"""
        return list(self._adapters.values())

    async def initialize_all(self) -> None:
        """初始化所有适配器"""
        for adapter in self._adapters.values():
            await adapter.initialize()

    async def shutdown_all(self) -> None:
        """关闭所有适配器"""
        for adapter in self._adapters.values():
            await adapter.shutdown()

    async def discover_all(self) -> dict[str, list]:
        """发现所有适配器的工具"""
        results = {}
        for name, adapter in self._adapters.items():
            results[name] = await adapter.discover()
        return results

    @property
    def count(self) -> int:
        return len(self._adapters)
