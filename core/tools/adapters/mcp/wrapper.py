"""MCPToolWrapper —— 将 MCP 工具包装为 AI-Lab ToolProtocol。

这是 MCP Adapter 的核心桥梁：
- 对外：暴露 ToolProtocol 接口，ToolExecutor 可以无差别调用
- 对内：通过 MCPClient 调用远程 MCP Server 上的工具
"""

from __future__ import annotations

from core.tools.models import ToolRequest, ToolResult, ToolInfo
from core.tools.protocol import ToolProtocol
from core.tools.adapters.mcp.protocol import MCPClientProtocol
from core.tools.adapters.mcp.models import MCPToolInfo, MCPToolCall
from core.tools.adapters.mcp.converter import MCPConverter


class MCPToolWrapper(ToolProtocol):
    """MCP 工具包装器 —— 实现 ToolProtocol，内部委托给 MCPClient"""

    def __init__(self, client: MCPClientProtocol, mcp_tool: MCPToolInfo):
        self._client = client
        self._mcp_tool = mcp_tool
        self._info = MCPConverter.mcp_tool_to_tool_info(mcp_tool)

    # ---- ToolProtocol 实现 ----

    async def initialize(self) -> None:
        """确保 MCP Client 已连接"""
        if not await self._client.health_check():
            await self._client.initialize()

    async def execute(self, request: ToolRequest) -> ToolResult:
        # Strip the mcp.<server> prefix to get the actual MCP tool name
        mcp_call = MCPConverter.tool_request_to_mcp_call(request)
        parts = mcp_call.tool_name.split(".")
        if len(parts) >= 3 and parts[0] == "mcp":
            mcp_call.tool_name = parts[-1]
        mcp_result = await self._client.invoke_tool(mcp_call)
        return MCPConverter.mcp_result_to_tool_result(mcp_result)

    async def validate(self, request: ToolRequest) -> bool:
        """校验参数：MCP Tool 的参数校验由 ToolValidator 通过 ToolInfo.parameters 完成"""
        return True

    async def health_check(self) -> bool:
        return await self._client.health_check()

    async def shutdown(self) -> None:
        pass  # 由 MCPToolRegistry 统一管理 Client 生命周期

    @property
    def info(self) -> ToolInfo:
        return self._info
