"""MCP 异常定义"""


class MCPError(Exception):
    """MCP 基础异常"""
    pass


class MCPConnectionError(MCPError):
    """连接 Server 失败"""
    pass


class MCPTimeoutError(MCPError):
    """调用超时"""
    pass


class MCPToolNotFoundError(MCPError):
    """工具未找到"""
    pass


class MCPValidationError(MCPError):
    """参数校验失败"""
    pass


class MCPDiscoveryError(MCPError):
    """工具发现失败"""
    pass
