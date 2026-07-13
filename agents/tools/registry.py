"""工具注册中心。管理所有可用工具的注册、发现和执行。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agents.tools.protocol import Tool, ToolCall, ToolCallResult, ToolFilter, ToolHandler


class ToolRegistry(ABC):
    """工具注册中心。"""

    @abstractmethod
    async def register(self, tool: Tool, handler: ToolHandler) -> None:
        """注册一个工具及其执行器。"""
        ...

    @abstractmethod
    async def unregister(self, tool_name: str) -> None:
        """注销一个工具。"""
        ...

    @abstractmethod
    async def get_tool(self, tool_name: str) -> Tool | None:
        """获取工具定义。"""
        ...

    @abstractmethod
    async def list_tools(self, filter: ToolFilter | None = None) -> list[Tool]:
        """列出可用工具，可按条件过滤。"""
        ...

    @abstractmethod
    async def execute(self, call: ToolCall) -> ToolCallResult:
        """同步执行一个工具调用。"""
        ...

    @abstractmethod
    async def execute_async(self, call: ToolCall) -> str:
        """异步执行一个工具调用。返回 call_id。"""
        ...
