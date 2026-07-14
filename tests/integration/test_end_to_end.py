import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.tools.registry import ToolRegistry
from core.tools.executor import ToolExecutor
from core.tools.builtin.echo import EchoTool
from core.tools.builtin.calculator import CalculatorTool
from core.tools.adapters.mcp import (
    MCPClient, MCPServerInfo, MCPToolInfo, MCPToolSchema, MCPToolRegistry,
)
from core.agents.models import AgentInfo, AgentRequest, AgentResponse, AgentContext
from core.agents.executor import AgentExecutor
from core.memory.manager import MemoryManager
from core.memory.models import MemoryItem, MemoryType


class TestEndToEnd:
    """????????Agent -> Memory -> Knowledge -> Provider -> Tool -> MCP"""

    async def test_full_pipeline_no_tools(self):
        """?????Agent ???? -> Context -> Mock LLM -> ?? -> ?? Memory"""
        class MockLLM:
            async def generate(self, req):
                from core.providers.llm.protocol import LLMResponse
                return LLMResponse(content=f"I understood: {req.messages[-1].content}")

        mgr = MemoryManager()
        from core.memory.session import SessionMemory
        from core.memory.models import MemoryType
        mgr.register_store(MemoryType.SESSION, SessionMemory())
        mgr.register_store(MemoryType.EPISODIC, SessionMemory())
        info = AgentInfo(name="e2e-agent", description="End-to-end test agent")
        executor = AgentExecutor(
            info=info, llm_provider=MockLLM(), memory_manager=mgr,
        )
        req = AgentRequest(
            user_input="What is the capital of France?",
            session_id="e2e-session-1",
            memory_enabled=True,
        )
        resp = await executor.execute(req)
        # ????
        assert resp.status == "ok"
        assert "capital" in resp.answer.lower() or "I understood" in resp.answer
        # ?? Memory ??
        from core.memory.models import MemoryQuery
        results = await mgr.retrieve(MemoryQuery(top_k=10))
        found = any("capital of France" in str(r.content) for r in results)
        assert found, "Memory should contain the saved interaction"

    async def test_full_pipeline_with_builtin_tools(self):
        """???? + ??????"""
        class MockLLM:
            async def generate(self, req):
                from core.providers.llm.protocol import LLMResponse
                return LLMResponse(content="Let me calculate that for you")

        reg = ToolRegistry()
        echo = EchoTool()
        calc = CalculatorTool()
        reg.register(echo.info, lambda: EchoTool())
        reg.register(calc.info, lambda: CalculatorTool())
        from core.tools.permissions import PermissionManager
        pm = PermissionManager(agent_permissions=["execute"])
        te = ToolExecutor(registry=reg, permission_manager=pm)
        mgr = MemoryManager()
        from core.memory.session import SessionMemory
        from core.memory.models import MemoryType
        mgr.register_store(MemoryType.SESSION, SessionMemory())
        mgr.register_store(MemoryType.EPISODIC, SessionMemory())
        info = AgentInfo(name="tool-agent", description="Agent with tools")
        executor = AgentExecutor(info=info, llm_provider=MockLLM(),
                                 memory_manager=mgr, tool_registry=reg, tool_executor=te)
        ctx = AgentContext(session_id="e2e-tool", agent_id=info.id)
        ctx.variables = {"tool_calls": [
            {"name": "echo", "arguments": {"text": "hello"}},
            {"name": "calculator", "arguments": {"expression": "2+3"}},
        ]}
        req = AgentRequest(user_input="echo and calc", session_id="e2e-tool", tools_enabled=True)
        tools = await executor._invoke_tools(req, ctx)
        assert len(tools) == 2
        assert tools[0].tool_name == "echo"
        assert tools[1].tool_name == "calculator"
        assert tools[0].success
        assert tools[1].success

    async def test_full_pipeline_with_mcp(self):
        """???? + MCP ??"""
        class MockLLM:
            async def generate(self, req):
                from core.providers.llm.protocol import LLMResponse
                return LLMResponse(content="Let me search for that")

        # ?? MCP
        mcp_client = MCPClient(MCPServerInfo(name="e2e-mcp"))
        await mcp_client.initialize()
        mcp_client.register_tool(
            MCPToolInfo(name="lookup", description="Lookup data",
                        input_schema=MCPToolSchema(
                            properties={"key": {"type": "string"}},
                            required=["key"],
                        )),
            lambda args: f"Found: value_for_{args['key']}",
        )
        reg = ToolRegistry()
        mcp_reg = MCPToolRegistry(reg)
        await mcp_reg.add_server(mcp_client)
        from core.tools.permissions import PermissionManager
        pm = PermissionManager(agent_permissions=["execute"])
        te = ToolExecutor(registry=reg, permission_manager=pm)
        mgr = MemoryManager()
        from core.memory.session import SessionMemory
        from core.memory.models import MemoryType
        mgr.register_store(MemoryType.SESSION, SessionMemory())
        mgr.register_store(MemoryType.EPISODIC, SessionMemory())
        info = AgentInfo(name="e2e-mcp-agent", description="MCP agent")
        executor = AgentExecutor(info=info, llm_provider=MockLLM(),
                                 memory_manager=mgr, tool_registry=reg, tool_executor=te)
        ctx = AgentContext(session_id="e2e-mcp", agent_id=info.id)
        ctx.variables = {"tool_calls": [{
            "name": "mcp.e2e-mcp.lookup",
            "arguments": {"key": "config"},
        }]}
        req = AgentRequest(user_input="lookup config", session_id="e2e-mcp", tools_enabled=True)
        tools = await executor._invoke_tools(req, ctx)
        assert len(tools) == 1
        assert tools[0].success is True
        assert "value_for_config" in tools[0].result

    async def test_error_recovery(self):
        """?????LLM ??? Agent ????"""
        class BrokenLLM:
            async def generate(self, req):
                raise RuntimeError("LLM service unavailable")

        info = AgentInfo(name="recovery-agent", description="Error recovery")
        executor = AgentExecutor(info=info, llm_provider=BrokenLLM())
        req = AgentRequest(user_input="test", session_id="recovery-1")
        resp = await executor.execute(req)
        assert resp.status == "failed"
        assert resp.failure is not None
        assert "unavailable" in resp.failure.message.lower()
        assert resp.answer == ""

    async def test_echo_agent_no_deps(self):
        """Bare agents expose missing LLM instead of returning a fake echo."""
        info = AgentInfo(name="bare-agent", description="Bare minimum")
        executor = AgentExecutor(info=info)
        req = AgentRequest(user_input="echo this", session_id="bare-1")
        resp = await executor.execute(req)
        assert resp.status == "failed"
        assert resp.failure is not None
        assert "not configured" in resp.failure.message.lower()
        assert resp.answer == ""
