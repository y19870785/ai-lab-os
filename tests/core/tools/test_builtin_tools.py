import pytest
pytestmark = pytest.mark.asyncio(scope="function")
from core.tools.registry import ToolRegistry
from core.tools.executor import ToolExecutor
from core.tools.builtin.echo import EchoTool
from core.tools.builtin.calculator import CalculatorTool
from core.tools.builtin.datetime import DateTimeTool
from core.tools.builtin.uuid import UUIDTool
from core.tools.models import ToolRequest


class TestBuiltinTools:
    def _make_executor(self, tool):
        reg = ToolRegistry()
        reg.register(tool.info, type(tool))
        return ToolExecutor(registry=reg)

    async def test_echo(self):
        e = self._make_executor(EchoTool())
        result = await e.execute(ToolRequest(tool_name="echo", arguments={"text": "hello world"}))
        assert result.success is True
        assert result.output == "hello world"

    async def test_echo_empty(self):
        e = self._make_executor(EchoTool())
        result = await e.execute(ToolRequest(tool_name="echo", arguments={"text": ""}))
        assert result.success is True
        assert result.output == ""

    async def test_calculator_add(self):
        e = self._make_executor(CalculatorTool())
        result = await e.execute(ToolRequest(tool_name="calculator", arguments={"expression": "2 + 3 * 4"}))
        assert result.success is True
        assert result.output == 14

    async def test_calculator_sqrt(self):
        e = self._make_executor(CalculatorTool())
        result = await e.execute(ToolRequest(tool_name="calculator", arguments={"expression": "sqrt(16)"}))
        assert result.success is True
        assert result.output == 4.0

    async def test_calculator_invalid(self):
        e = self._make_executor(CalculatorTool())
        result = await e.execute(ToolRequest(tool_name="calculator", arguments={"expression": "__import__('os').system('dir')"}))
        assert result.success is False

    async def test_datetime_now(self):
        e = self._make_executor(DateTimeTool())
        result = await e.execute(ToolRequest(tool_name="datetime", arguments={"action": "now"}))
        assert result.success is True
        assert "T" in str(result.output)

    async def test_datetime_today(self):
        e = self._make_executor(DateTimeTool())
        result = await e.execute(ToolRequest(tool_name="datetime", arguments={"action": "today"}))
        assert result.success is True
        assert len(str(result.output)) == 10  # YYYY-MM-DD

    async def test_datetime_unixtime(self):
        e = self._make_executor(DateTimeTool())
        result = await e.execute(ToolRequest(tool_name="datetime", arguments={"action": "unixtime"}))
        assert result.success is True
        assert isinstance(result.output, float)

    async def test_uuid_single(self):
        e = self._make_executor(UUIDTool())
        result = await e.execute(ToolRequest(tool_name="uuid", arguments={}))
        assert result.success is True
        assert len(str(result.output)) == 36  # standard UUID format

    async def test_uuid_multiple(self):
        e = self._make_executor(UUIDTool())
        result = await e.execute(ToolRequest(tool_name="uuid", arguments={"count": 3}))
        assert result.success is True
        assert len(result.output) == 3

    async def test_uuid_max_clamped(self):
        e = self._make_executor(UUIDTool())
        result = await e.execute(ToolRequest(tool_name="uuid", arguments={"count": 200}))
        assert result.success is True
        assert len(result.output) == 100  # clamped to 100

    async def test_health_check_all(self):
        for tool_cls in [EchoTool, CalculatorTool, DateTimeTool, UUIDTool]:
            t = tool_cls()
            assert await t.health_check() is True
