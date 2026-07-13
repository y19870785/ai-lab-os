"""MCP Protocol —— MCP Client 的抽象接口。

所有 MCP Client 实现必须遵循此接口。
上层（ToolAdapter）只依赖这个 Protocol，不依赖任何具体 MCP SDK。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from core.tools.adapters.mcp.models import (
    MCPServerInfo, MCPToolInfo, MCPToolCall, MCPToolResult, MCPCapabilities,
)


class MCPClientProtocol(ABC):
    """MCP Client 抽象接口

    负责与一个 MCP Server 通信：连接、发现工具、调用工具。
    与具体传输方式（stdio / HTTP / WebSocket）无关。
    """

    @abstractmethod
    async def initialize(self) -> None:
        """建立与 MCP Server 的连接并完成握手"""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """关闭与 MCP Server 的连接"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查与 MCP Server 的连接是否正常"""
        ...

    @abstractmethod
    async def discover_tools(self) -> list[MCPToolInfo]:
        """发现 MCP Server 提供的所有工具"""
        ...

    @abstractmethod
    async def invoke_tool(self, call: MCPToolCall) -> MCPToolResult:
        """调用 MCP Server 上的一个工具"""
        ...

    @abstractmethod
    async def get_capabilities(self) -> MCPCapabilities:
        """获取 MCP Server 的能力声明"""
        ...

    @property
    @abstractmethod
    def server_info(self) -> MCPServerInfo:
        """获取连接的 Server 元数据"""
        ...
