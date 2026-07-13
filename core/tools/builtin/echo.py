"""EchoTool — returns input unchanged, for testing the tool runtime."""
from __future__ import annotations

from core.tools.models import ToolRequest, ToolResult, ToolInfo, ToolCategory, ParameterSchema
from core.tools.protocol import ToolProtocol


class EchoTool(ToolProtocol):
    def __init__(self):
        self._info = ToolInfo(
            name="echo",
            description="Echo the input text back unchanged. Useful for testing the tool runtime.",
            version="1.0.0",
            category=ToolCategory.UTILITY,
            tags=["test", "utility"],
            parameters=ParameterSchema(
                properties={
                    "text": {"type": "string", "description": "The text to echo back."}
                },
                required=["text"],
            ),
            permissions=[],
        )

    async def initialize(self) -> None:
        pass

    async def execute(self, request: ToolRequest) -> ToolResult:
        text = request.arguments.get("text", "")
        return ToolResult(success=True, output=text)

    async def validate(self, request: ToolRequest) -> bool:
        return "text" in request.arguments

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    @property
    def info(self) -> ToolInfo:
        return self._info
