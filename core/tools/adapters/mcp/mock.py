"""Mock MCP Provider —— 用于测试的模拟 MCP Server。

提供可预测的工具响应，不依赖任何外部服务。
"""

from __future__ import annotations
from core.tools.adapters.mcp.models import (
    MCPServerInfo, MCPToolInfo, MCPToolCall, MCPToolResult, MCPToolSchema,
)
from core.tools.adapters.mcp.client import MCPClient


def create_mock_mcp_server(
    name: str = "mock-server",
    tools: list[tuple[str, str, dict]] | None = None,
) -> MCPClient:
    """创建一个模拟 MCP Server，预注册一组工具。

    Args:
        name: Server 名称
        tools: 工具列表，每项为 (tool_name, description, handler_keyword)
               如果为 None，默认创建 weather 和 search 两个工具
    """
    server_info = MCPServerInfo(
        name=name,
        url=f"mock://{name}",
        description=f"Mock MCP Server: {name}",
    )
    client = MCPClient(server_info, timeout=10)

    if tools is None:
        tools = [
            ("weather", "Get weather for a city", "weather"),
            ("search", "Search for documents", "search"),
        ]

    for tool_name, desc, keyword in tools:
        info = MCPToolInfo(
            name=tool_name,
            description=desc,
            input_schema=MCPToolSchema(
                properties={
                    "query": {"type": "string", "description": "Search query"},
                },
                required=["query"],
            ),
        )
        client.register_tool(info, _make_handler(keyword))

    return client


def _make_handler(keyword: str):
    """创建模拟工具处理函数"""
    async def handler(args: dict) -> str:
        query = args.get("query", "")
        return f"[{keyword}] Result for: {query}"
    return handler
