"""ToolAdapterProtocol —— 所有外部工具适配器的统一接口。

MCP Adapter、HTTP Adapter、Shell Adapter、Docker Adapter 等
都必须实现此接口。上层通过 AdapterRegistry 管理所有 Adapter。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class ToolAdapterProtocol(ABC):
    """外部工具适配器统一接口

    每个 Adapter 负责：
    1. 初始化与外部系统的连接
    2. 发现外部系统提供的工具
    3. 将工具注册到 ToolRegistry
    4. 健康检查
    5. 优雅关闭
    """

    @abstractmethod
    async def initialize(self) -> None:
        """初始化适配器，建立与外部系统的连接"""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """关闭适配器，清理资源"""
        ...

    @abstractmethod
    async def discover(self) -> list[Any]:
        """发现外部系统提供的工具，返回工具元数据列表"""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """检查适配器及外部系统是否正常"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称"""
        ...
