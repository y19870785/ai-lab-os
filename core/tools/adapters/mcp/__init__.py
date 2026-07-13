"""MCP Adapter —— 入口模块。

MCP Adapter 负责：
1. 连接 MCP Server
2. 发现 MCP Tool
3. 包装为 ToolProtocol
4. 注册到 ToolRegistry
5. 让 ToolExecutor 无差别调用

架构位置：
    ToolExecutor → ToolProtocol → MCPToolWrapper → MCPClient → MCP Server
"""

from core.tools.adapters.mcp.models import (
    MCPServerInfo, MCPServerStatus, MCPToolInfo, MCPToolCall,
    MCPToolResult, MCPCapabilities, MCPToolSchema,
)
from core.tools.adapters.mcp.protocol import MCPClientProtocol
from core.tools.adapters.mcp.client import MCPClient
from core.tools.adapters.mcp.converter import MCPConverter
from core.tools.adapters.mcp.registry import MCPToolRegistry
from core.tools.adapters.mcp.wrapper import MCPToolWrapper
from core.tools.adapters.mcp.mock import create_mock_mcp_server
from core.tools.adapters.mcp.exceptions import (
    MCPError, MCPConnectionError, MCPTimeoutError,
    MCPToolNotFoundError, MCPValidationError, MCPDiscoveryError,
)

__all__ = [
    # Models
    "MCPServerInfo", "MCPServerStatus", "MCPToolInfo", "MCPToolCall",
    "MCPToolResult", "MCPCapabilities", "MCPToolSchema",
    # Core
    "MCPClientProtocol", "MCPClient", "MCPConverter",
    "MCPToolRegistry", "MCPToolWrapper",
    # Mock
    "create_mock_mcp_server",
    # Exceptions
    "MCPError", "MCPConnectionError", "MCPTimeoutError",
    "MCPToolNotFoundError", "MCPValidationError", "MCPDiscoveryError",
]
