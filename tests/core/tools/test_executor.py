import pytest
pytestmark = pytest.mark.asyncio(scope="function")
import asyncio
from core.tools.registry import ToolRegistry
from core.tools.executor import ToolExecutor
from core.tools.models import ToolInfo, ToolRequest, ToolResult, ToolCategory, ParameterSchema
from core.tools.protocol import ToolProtocol
from core.tools.exceptions import ToolNotFoundError


class _MockTool(ToolProtocol):
    def __init__(self, name="mock", will_succeed=True):
        self._info = ToolInfo(
            name=name,
            description="Mock tool",
            category=ToolCategory.UTILITY,
            parameters=ParameterSchema(
                properties={"value": {"type": "string"}},
                required=["value"],
            ),
            permissions=[],
        )
        self.will_succeed = will_succeed

    async def initialize(self): pass
    async def execute(self, request: ToolRequest) -> ToolResult:
        if self.will_succeed:
            return ToolResult(success=True, output=request.arguments.get("value"))
        return ToolResult(success=False, error="mock failure")
    async def validate(self, request: ToolRequest) -> bool: return True
    async def health_check(self) -> bool: return True
    async def shutdown(self) -> None: pass
    @property
    def info(self) -> ToolInfo: return self._info


class _SlowMockTool(ToolProtocol):
    def __init__(self):
        self._info = ToolInfo(name="slow_mock", description="Slow mock", timeout=1)
    async def initialize(self): pass
    async def execute(self, request: ToolRequest) -> ToolResult:
        await asyncio.sleep(5)
        return ToolResult(success=True)
    async def validate(self, request: ToolRequest) -> bool: return True
    async def health_check(self) -> bool: return True
    async def shutdown(self) -> None: pass
    @property
    def info(self) -> ToolInfo: return self._info


class TestToolExecutor:
    def _make_executor(self):
        reg = ToolRegistry()
        tool = _MockTool("mock")
        reg.register(tool.info, lambda: _MockTool("mock"))
        return ToolExecutor(registry=reg)

    async def test_successful_execution(self):
        executor = self._make_executor()
        req = ToolRequest(tool_name="mock", arguments={"value": "hello"}, agent_id="a1")
        result = await executor.execute(req)
        assert result.success is True
        assert result.output == "hello"

    async def test_validation_error(self):
        executor = self._make_executor()
        req = ToolRequest(tool_name="mock", arguments={})  # missing required "value"
        result = await executor.execute(req)
        assert result.success is False

    async def test_tool_not_found(self):
        reg = ToolRegistry()
        executor = ToolExecutor(registry=reg)
        req = ToolRequest(tool_name="nonexistent")
        result = await executor.execute(req)
        assert result.success is False

    async def test_execute_by_name(self):
        executor = self._make_executor()
        result = await executor.execute_by_name("mock", arguments={"value": "hi"})
        assert result.success is True
        assert result.output == "hi"

    async def test_metrics_recorded(self):
        executor = self._make_executor()
        req = ToolRequest(tool_name="mock", arguments={"value": "x"})
        await executor.execute(req)
        snap = executor.metrics.snapshot()
        assert "mock" in snap
        assert snap["mock"]["call_count"] == 1
        assert snap["mock"]["success_rate"] == 1.0

    async def test_audit_recorded(self):
        executor = self._make_executor()
        req = ToolRequest(tool_name="mock", arguments={"value": "x"}, agent_id="a1")
        await executor.execute(req)
        records = executor.audit.get_records()
        assert len(records) == 1
        assert records[0]["tool_name"] == "mock"

    async def test_tool_failure_metrics(self):
        reg = ToolRegistry()
        tool = _MockTool("bad", will_succeed=False)
        reg.register(tool.info, lambda: _MockTool("bad", will_succeed=False))
        executor = ToolExecutor(registry=reg)
        req = ToolRequest(tool_name="bad", arguments={"value": "x"})
        result = await executor.execute(req)
        assert result.success is False
        snap = executor.metrics.snapshot()
        assert snap["bad"]["success_rate"] == 0.0
