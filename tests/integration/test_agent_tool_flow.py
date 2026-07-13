import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.tools.registry import ToolRegistry
from core.tools.executor import ToolExecutor
from core.tools.builtin.echo import EchoTool
from core.tools.builtin.calculator import CalculatorTool
from core.tools.models import ToolRequest, ToolResult
from core.agents.executor import AgentExecutor
from core.agents.models import AgentRequest, AgentResponse, AgentInfo, AgentContext


class TestAgentToolFlow:
    """Agent -> ToolExecutor -> Builtin Tool ????"""

    def _make_executor(self):
        registry = ToolRegistry()
        echo = EchoTool()
        calc = CalculatorTool()
        registry.register(echo.info, lambda: EchoTool())
        registry.register(calc.info, lambda: CalculatorTool())
        tool_executor = ToolExecutor(registry=registry)
        return registry, tool_executor

    async def test_agent_calls_echo_tool(self):
        registry, tool_executor = self._make_executor()
        # ?? LLM ?? tool_calls
        class FakeLLM:
            async def generate(self, req):
                from core.providers.llm.protocol import LLMResponse
                return LLMResponse(content="I will echo that")
        info = AgentInfo(name="test-agent", description="Testing")
        executor = AgentExecutor(info=info, llm_provider=FakeLLM(), tool_registry=registry)
        # ? tool_executor ??
        executor._tool_executor = tool_executor
        ctx = AgentContext(session_id="s1", agent_id=info.id)
        ctx.variables = {"tool_calls": [{"name": "echo", "arguments": {"text": "hello from agent"}}]}
        req = AgentRequest(user_input="echo hello", session_id="s1", tools_enabled=True)
        tools = await executor._invoke_tools(req, ctx)
        assert len(tools) == 1
        assert tools[0].tool_name == "echo"
        assert tools[0].success is True
        assert "hello from agent" in tools[0].result

    async def test_agent_calls_calculator(self):
        registry, tool_executor = self._make_executor()
        info = AgentInfo(name="calc-agent", description="Math")
        executor = AgentExecutor(info=info, tool_registry=registry)
        executor._tool_executor = tool_executor
        ctx = AgentContext(session_id="s2", agent_id=info.id)
        ctx.variables = {"tool_calls": [{"name": "calculator", "arguments": {"expression": "6 * 7"}}]}
        req = AgentRequest(user_input="6*7", session_id="s2", tools_enabled=True)
        tools = await executor._invoke_tools(req, ctx)
        assert len(tools) == 1
        assert tools[0].success is True
        assert "42" in tools[0].result

    async def test_agent_with_no_tool_calls(self):
        registry, tool_executor = self._make_executor()
        info = AgentInfo(name="no-tool-agent", description="No tools")
        executor = AgentExecutor(info=info, tool_registry=registry)
        executor._tool_executor = tool_executor
        ctx = AgentContext(session_id="s3", agent_id=info.id)
        ctx.variables = {}
        req = AgentRequest(user_input="hi", session_id="s3", tools_enabled=True)
        tools = await executor._invoke_tools(req, ctx)
        assert tools == []

    async def test_tool_executor_reports_error(self):
        registry, tool_executor = self._make_executor()
        info = AgentInfo(name="err-agent", description="Error")
        executor = AgentExecutor(info=info, tool_registry=registry)
        executor._tool_executor = tool_executor
        ctx = AgentContext(session_id="s4", agent_id=info.id)
        ctx.variables = {"tool_calls": [{"name": "nonexistent", "arguments": {}}]}
        req = AgentRequest(user_input="bad tool", session_id="s4", tools_enabled=True)
        tools = await executor._invoke_tools(req, ctx)
        assert len(tools) == 1
        assert tools[0].success is False
