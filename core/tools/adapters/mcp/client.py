"""MCPClient —— MCP Client 的默认实现。

当前版本基于内存模拟（Mock），不依赖真实 MCP SDK。
未来可替换为基于 mcp 包的 stdio/HTTP 传输实现。
"""

from __future__ import annotations
import asyncio
from typing import Any

from core.tools.adapters.mcp.models import (
    MCPServerInfo, MCPServerStatus, MCPToolInfo, MCPToolCall,
    MCPToolResult, MCPCapabilities, MCPToolSchema,
)
from core.tools.adapters.mcp.protocol import MCPClientProtocol
from core.tools.adapters.mcp.exceptions import (
    MCPConnectionError, MCPTimeoutError, MCPToolNotFoundError,
)


class MCPClient(MCPClientProtocol):
    """默认 MCP Client 实现 —— 内存模式。

    内置一个可注册的工具表，用于模拟 MCP Server 行为。
    生产环境中替换为真实 MCP SDK 传输层即可。
    """

    def __init__(self, server_info: MCPServerInfo, timeout: int = 30):
        self._server_info = server_info
        self._timeout = timeout
        self._tools: dict[str, MCPToolInfo] = {}
        self._tool_handlers: dict[str, Any] = {}
        self._initialized = False

    # ---- MCPClientProtocol 实现 ----

    async def initialize(self) -> None:
        """模拟 MCP 握手"""
        self._server_info.status = MCPServerStatus.CONNECTING
        await asyncio.sleep(0)  # 模拟网络延迟
        self._server_info.status = MCPServerStatus.CONNECTED
        self._initialized = True

    async def shutdown(self) -> None:
        self._server_info.status = MCPServerStatus.DISCONNECTED
        self._initialized = False
        self._tools.clear()
        self._tool_handlers.clear()

    async def health_check(self) -> bool:
        return self._initialized and self._server_info.status == MCPServerStatus.CONNECTED

    async def discover_tools(self) -> list[MCPToolInfo]:
        if not self._initialized:
            raise MCPConnectionError("MCP Client not initialized")
        return list(self._tools.values())

    async def invoke_tool(self, call: MCPToolCall) -> MCPToolResult:
        if not self._initialized:
            raise MCPConnectionError("MCP Client not initialized")

        handler = self._tool_handlers.get(call.tool_name)
        if handler is None:
            return MCPToolResult(
                success=False,
                error=f"Tool not found: {call.tool_name}",
                call_id=call.call_id,
            )

        try:
            # handler may be sync or async -- normalize to coroutine
            maybe_coro = handler(call.arguments)
            if asyncio.iscoroutine(maybe_coro):
                result = await asyncio.wait_for(maybe_coro, timeout=self._timeout)
            else:
                result = maybe_coro
            return MCPToolResult(
                success=True,
                content=result,
                call_id=call.call_id,
            )
        except asyncio.TimeoutError:
            return MCPToolResult(
                success=False,
                error=f"Tool {call.tool_name} timed out after {self._timeout}s",
                call_id=call.call_id,
            )
        except Exception as e:
            return MCPToolResult(
                success=False,
                error=str(e),
                call_id=call.call_id,
            )

    async def get_capabilities(self) -> MCPCapabilities:
        return MCPCapabilities(tools=len(self._tools) > 0)

    @property
    def server_info(self) -> MCPServerInfo:
        return self._server_info

    # ---- 扩展方法：注册模拟工具 ----

    def register_tool(self, info: MCPToolInfo, handler) -> None:
        """注册一个模拟 MCP Tool 及其处理函数"""
        info.server_name = self._server_info.name
        self._tools[info.name] = info
        self._tool_handlers[info.name] = handler

    def unregister_tool(self, name: str) -> bool:
        self._tools.pop(name, None)
        return self._tool_handlers.pop(name, None) is not None
