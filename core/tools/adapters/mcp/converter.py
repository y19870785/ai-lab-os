"""MCPConverter —— 将 MCP 数据结构转换为 AI-Lab Tool 数据结构。

这是 MCP Adapter 的核心：把外部 MCP Tool 包装成 ToolProtocol，
让 ToolExecutor 像对待内置工具一样对待 MCP 工具。
"""

from __future__ import annotations

from core.tools.models import (
    ToolInfo, ToolRequest, ToolResult, ToolCategory,
    ToolPermission, ParameterSchema,
)
from core.tools.adapters.mcp.models import (
    MCPToolInfo, MCPToolCall, MCPToolResult,
)


class MCPConverter:
    """MCP 数据格式 ↔ AI-Lab Tool 数据格式 双向转换器"""

    @staticmethod
    def mcp_tool_to_tool_info(mcp_tool: MCPToolInfo) -> ToolInfo:
        """将 MCPToolInfo 转换为 ToolInfo"""
        return ToolInfo(
            name=f"mcp.{mcp_tool.server_name}.{mcp_tool.name}",
            description=mcp_tool.description,
            version="1.0.0",
            category=ToolCategory.EXTERNAL,
            tags=["mcp", mcp_tool.server_name],
            parameters=ParameterSchema(
                type=mcp_tool.input_schema.type,
                properties=mcp_tool.input_schema.properties,
                required=mcp_tool.input_schema.required,
            ),
            permissions=[ToolPermission.EXECUTE],
            metadata={
                "mcp_server": mcp_tool.server_name,
                "mcp_tool": mcp_tool.name,
                "adapter": "mcp",
            },
        )

    @staticmethod
    def tool_request_to_mcp_call(request: ToolRequest) -> MCPToolCall:
        """将 ToolRequest 转换为 MCPToolCall"""
        return MCPToolCall(
            tool_name=request.tool_name,
            arguments=request.arguments,
            call_id=request.trace_id,
        )

    @staticmethod
    def mcp_result_to_tool_result(mcp_result: MCPToolResult) -> ToolResult:
        """将 MCPToolResult 转换为 ToolResult"""
        return ToolResult(
            success=mcp_result.success,
            output=mcp_result.content,
            error=mcp_result.error,
        )
