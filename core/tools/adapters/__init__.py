"""Tool Adapters —— MCP, HTTP, Shell, Docker, Browser 等外部工具适配器。

所有 Adapter 遵循统一接口（ToolAdapterProtocol）。
上层只依赖 ToolProtocol，不依赖任何 Adapter 实现。
"""
