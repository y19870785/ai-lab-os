"""UUIDTool — generate UUIDs (v4 or v7 if available)."""
from __future__ import annotations
import uuid

from core.tools.models import ToolRequest, ToolResult, ToolInfo, ToolCategory, ParameterSchema
from core.tools.protocol import ToolProtocol


class UUIDTool(ToolProtocol):
    def __init__(self):
        self._info = ToolInfo(
            name="uuid",
            description="Generate UUIDs. Supports v4 (random) and v7 (time-ordered) if available on Python 3.14+.",
            version="1.0.0",
            category=ToolCategory.UTILITY,
            tags=["utility", "id"],
            parameters=ParameterSchema(
                properties={
                    "version": {"type": "integer", "description": "UUID version: 4 (default) or 7"},
                    "count": {"type": "integer", "description": "Number of UUIDs to generate (default 1, max 100)"},
                },
                required=[],
            ),
            permissions=[],
        )

    async def initialize(self) -> None:
        pass

    async def execute(self, request: ToolRequest) -> ToolResult:
        version = request.arguments.get("version", 4)
        count = min(request.arguments.get("count", 1), 100)

        try:
            results = []
            for _ in range(count):
                if version == 7 and hasattr(uuid, "uuid7"):
                    results.append(str(uuid.uuid7()))
                else:
                    results.append(str(uuid.uuid4()))

            if count == 1:
                return ToolResult(success=True, output=results[0])

            return ToolResult(success=True, output=results)
        except Exception as e:
            return ToolResult(success=False, error=f"UUID generation error: {e}")

    async def validate(self, request: ToolRequest) -> bool:
        return True  # No required params

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    @property
    def info(self) -> ToolInfo:
        return self._info
