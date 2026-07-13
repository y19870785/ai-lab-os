import pytest
pytestmark = pytest.mark.asyncio(scope="function")
import asyncio
from core.tools.sandbox import ToolSandbox
from core.tools.models import ToolRequest, ToolResult, ToolInfo


async def _fast_tool(request: ToolRequest) -> ToolResult:
    return ToolResult(success=True, output="done")


async def _slow_tool(request: ToolRequest) -> ToolResult:
    await asyncio.sleep(10)
    return ToolResult(success=True)


class TestToolSandbox:
    async def test_fast_execution(self):
        sandbox = ToolSandbox()
        info = ToolInfo(name="fast", timeout=5)
        req = ToolRequest(tool_name="fast")
        result = await sandbox.execute(_fast_tool, req, info)
        assert result.success is True
        assert result.output == "done"

    async def test_timeout(self):
        sandbox = ToolSandbox()
        info = ToolInfo(name="slow", timeout=1)
        req = ToolRequest(tool_name="slow")
        result = await sandbox.execute(_slow_tool, req, info)
        assert result.success is False
        assert "timed out" in (result.error or "")

    async def test_exception_caught(self):
        async def _crash(request: ToolRequest) -> ToolResult:
            raise ValueError("boom")
        sandbox = ToolSandbox()
        info = ToolInfo(name="crash", timeout=5)
        req = ToolRequest(tool_name="crash")
        result = await sandbox.execute(_crash, req, info)
        assert result.success is False
        assert "boom" in (result.error or "")
