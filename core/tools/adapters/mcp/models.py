"""MCP Adapter 数据模型 —— 独立于任何 MCP SDK，只定义协议层数据结构。

MCP (Model Context Protocol) 的核心概念：
- Server: 提供工具的外部服务
- Tool: Server 暴露的一个具体工具
- ToolCall: 一次工具调用请求
- ToolResult: 一次工具调用结果
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class MCPServerStatus(str, Enum):
    """MCP Server 状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPServerInfo:
    """MCP Server 元数据"""
    name: str
    url: str = ""
    version: str = "1.0.0"
    description: str = ""
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolSchema:
    """MCP Tool 的参数 schema —— JSON Schema 格式"""
    type: str = "object"
    properties: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)


@dataclass
class MCPToolInfo:
    """MCP Tool 元数据，对应一个 MCP Server 上的工具"""
    name: str
    description: str = ""
    server_name: str = ""
    input_schema: MCPToolSchema = field(default_factory=MCPToolSchema)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolCall:
    """一次 MCP 工具调用"""
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""
    success: bool = False
    content: Any = None
    error: str | None = None
    call_id: str = ""


@dataclass
class MCPCapabilities:
    """MCP Server 能力声明"""
    tools: bool = True
    resources: bool = False
    prompts: bool = False
    logging: bool = False
