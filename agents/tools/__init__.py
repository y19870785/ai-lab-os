"""工具系统。提供 Agent 可调用的标准化工具接口。

工具是 Agent 与外部世界交互的唯一通道。
支持注册、发现、执行和审计。
"""

from agents.tools.protocol import (
    ExecutionType,
    Tool,
    ToolCall,
    ToolCallStatus,
    ToolFilter,
)
from agents.tools.registry import ToolRegistry

__all__ = [
    "ExecutionType",
    "Tool",
    "ToolCall",
    "ToolCallStatus",
    "ToolFilter",
    "ToolRegistry",
]
