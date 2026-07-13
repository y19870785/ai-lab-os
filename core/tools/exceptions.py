"""Tool System exceptions."""
from __future__ import annotations
class ToolError(Exception): pass
class ToolNotFoundError(ToolError): pass
class ToolExecutionError(ToolError): pass
class ToolTimeoutError(ToolError): pass
class ToolPermissionDeniedError(ToolError): pass
class ToolValidationError(ToolError): pass
class ToolNotReadyError(ToolError): pass