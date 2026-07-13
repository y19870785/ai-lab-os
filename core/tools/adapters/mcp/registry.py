"""MCPToolRegistry —— 管理所有 MCP Client 及其发现的工具。

职责：
1. 持有所有 MCP Client 实例
2. 聚合所有 MCP Server 的工具列表
3. 将 MCP Tool 注册到 ToolRegistry，使其对 ToolExecutor 可见
"""

from __future__ import annotations

from core.tools.registry import ToolRegistry
from core.tools.adapters.mcp.protocol import MCPClientProtocol
from core.tools.adapters.mcp.models import MCPToolInfo, MCPServerInfo
from core.tools.adapters.mcp.converter import MCPConverter
from core.tools.adapters.mcp.exceptions import MCPDiscoveryError


class MCPToolRegistry:
    """MCP 工具注册中心 —— 连接 MCP Client 与 ToolRegistry"""

    def __init__(self, tool_registry: ToolRegistry):
        self._tool_registry = tool_registry
        self._clients: dict[str, MCPClientProtocol] = {}
        self._discovered: dict[str, list[MCPToolInfo]] = {}

    async def add_server(self, client: MCPClientProtocol) -> list[MCPToolInfo]:
        """添加一个 MCP Server，连接并发现其工具"""
        server_name = client.server_info.name

        await client.initialize()
        self._clients[server_name] = client

        try:
            tools = await client.discover_tools()
        except Exception as e:
            raise MCPDiscoveryError(f"Failed to discover tools from {server_name}: {e}")

        self._discovered[server_name] = tools

        # 注册到 ToolRegistry
        for mcp_tool in tools:
            tool_info = MCPConverter.mcp_tool_to_tool_info(mcp_tool)
            # 为每个 MCP 工具创建一个 MCPToolWrapper 工厂
            self._tool_registry.register(
                tool_info,
                self._make_factory(client, mcp_tool),
            )

        return tools

    async def remove_server(self, server_name: str) -> None:
        """移除一个 MCP Server"""
        client = self._clients.pop(server_name, None)
        if client is None:
            return

        # 从 ToolRegistry 中移除该 Server 的所有工具
        tools = self._discovered.pop(server_name, [])
        for mcp_tool in tools:
            tool_name = f"mcp.{server_name}.{mcp_tool.name}"
            self._tool_registry.unregister(tool_name)

        await client.shutdown()

    async def shutdown_all(self) -> None:
        """关闭所有 MCP Server 连接"""
        for name in list(self._clients.keys()):
            await self.remove_server(name)

    def list_servers(self) -> list[str]:
        """列出所有已连接的 MCP Server"""
        return list(self._clients.keys())

    def list_tools(self, server_name: str | None = None) -> list[MCPToolInfo]:
        """列出已发现的 MCP 工具"""
        if server_name:
            return self._discovered.get(server_name, [])
        result = []
        for tools in self._discovered.values():
            result.extend(tools)
        return result

    def get_client(self, server_name: str) -> MCPClientProtocol | None:
        """获取指定 Server 的 MCP Client"""
        return self._clients.get(server_name)

    def _make_factory(self, client: MCPClientProtocol, mcp_tool: MCPToolInfo):
        """创建一个闭包工厂，用于 ToolRegistry 的懒加载"""

        # 延迟导入避免循环依赖
        from core.tools.adapters.mcp.wrapper import MCPToolWrapper

        def factory():
            return MCPToolWrapper(client=client, mcp_tool=mcp_tool)

        return factory
