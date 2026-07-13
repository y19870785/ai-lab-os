"""DateTimeTool — current date/time and formatting."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

from core.tools.models import ToolRequest, ToolResult, ToolInfo, ToolCategory, ParameterSchema
from core.tools.protocol import ToolProtocol


class DateTimeTool(ToolProtocol):
    def __init__(self):
        self._info = ToolInfo(
            name="datetime",
            description="Get current date/time or format a given timestamp. Supports 'now', 'today', 'utc', and format strings.",
            version="1.0.0",
            category=ToolCategory.UTILITY,
            tags=["time", "utility"],
            parameters=ParameterSchema(
                properties={
                    "action": {
                        "type": "string",
                        "description": "One of: now (ISO datetime), today (date only), utc (UTC ISO), unixtime, iso_format",
                    },
                    "format": {
                        "type": "string",
                        "description": "strftime format string when action='iso_format', e.g. '%%Y-%%m-%%d %%H:%%M:%%S'",
                    },
                },
                required=["action"],
            ),
            permissions=[],
        )

    async def initialize(self) -> None:
        pass

    async def execute(self, request: ToolRequest) -> ToolResult:
        action = request.arguments.get("action", "now")
        now = datetime.now(timezone(timedelta(hours=8)))  # Asia/Shanghai

        if action == "now":
            return ToolResult(success=True, output=now.isoformat())
        elif action == "today":
            return ToolResult(success=True, output=now.strftime("%Y-%m-%d"))
        elif action == "utc":
            return ToolResult(success=True, output=datetime.now(timezone.utc).isoformat())
        elif action == "unixtime":
            return ToolResult(success=True, output=now.timestamp())
        elif action == "iso_format":
            fmt = request.arguments.get("format", "%Y-%m-%d %H:%M:%S")
            return ToolResult(success=True, output=now.strftime(fmt))
        else:
            return ToolResult(success=False, error=f"Unknown action: {action}")

    async def validate(self, request: ToolRequest) -> bool:
        return "action" in request.arguments

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    @property
    def info(self) -> ToolInfo:
        return self._info
