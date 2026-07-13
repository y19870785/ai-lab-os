"""ToolSandbox — execution isolation and timeout enforcement."""
from __future__ import annotations
import asyncio
from typing import Any
from core.tools.models import ToolRequest, ToolResult, ToolInfo
from core.tools.exceptions import ToolTimeoutError, ToolExecutionError

class ToolSandbox:
    def __init__(self, default_timeout: int = 30):
        self._default_timeout = default_timeout
    async def execute(self, fn, request: ToolRequest, info: ToolInfo, *args: Any, **kwargs: Any) -> ToolResult:
        timeout = min(info.timeout or self._default_timeout, 300)
        try:
            result = await asyncio.wait_for(fn(request, *args, **kwargs), timeout=timeout)
            if isinstance(result, ToolResult):
                return result
            return ToolResult(success=True, output=result)
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"Tool {info.name} timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))