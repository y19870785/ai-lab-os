"""Agent Runtime Integration Tests.

Validates end-to-end Agent flow with Memory and Tools.
"""

import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.agents.models import AgentRequest, AgentInfo, AgentContext
from core.agents.runtime import DefaultAgentRuntime
from core.agents.config import AgentConfig
from core.providers.llm.mock import MockLLMProvider
from core.memory.manager import MemoryManager
from core.tools.registry import ToolRegistry
from core.tools.builtin.echo import EchoTool
from core.tools.builtin.calculator import CalculatorTool


class TestAgentMemoryFlow:

    async def test_agent_run_with_memory(self):
        llm = MockLLMProvider()
        await llm.initialize()
        memory = MemoryManager()
        info = AgentInfo(name="test-agent", description="Test")
        config = AgentConfig(memory_enabled=True, knowledge_enabled=False, tools_enabled=False)
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm, memory_manager=memory, config=config)
        await runtime.initialize()
        req = AgentRequest(user_input="What is AI-Lab?", session_id="s1", agent_id="test-agent", memory_enabled=True)
        resp = await runtime.run(req)
        assert resp.answer is not None
        await runtime.shutdown()
        await llm.shutdown()

    async def test_agent_run_without_memory(self):
        llm = MockLLMProvider()
        await llm.initialize()
        info = AgentInfo(name="test-agent")
        config = AgentConfig(memory_enabled=False)
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm, config=config)
        await runtime.initialize()
        req = AgentRequest(user_input="Hello", session_id="s2", agent_id="test-agent", memory_enabled=False)
        resp = await runtime.run(req)
        assert resp.answer is not None
        await runtime.shutdown()
        await llm.shutdown()

    async def test_agent_multiple_turns(self):
        llm = MockLLMProvider()
        await llm.initialize()
        memory = MemoryManager()
        info = AgentInfo(name="test-agent")
        config = AgentConfig(memory_enabled=True)
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm, memory_manager=memory, config=config)
        await runtime.initialize()
        sid = "s-multi"
        for msg in ["Hi", "How are you?", "What can you do?"]:
            resp = await runtime.run(AgentRequest(
                user_input=msg, session_id=sid, agent_id="test-agent", memory_enabled=True,
            ))
            assert resp.answer is not None
        await runtime.shutdown()
        await llm.shutdown()

    async def test_agent_context_building(self):
        llm = MockLLMProvider()
        await llm.initialize()
        memory = MemoryManager()
        info = AgentInfo(name="test-agent")
        config = AgentConfig(memory_enabled=True)
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm, memory_manager=memory, config=config)
        await runtime.initialize()
        req = AgentRequest(user_input="Test", session_id="s-ctx", agent_id="test-agent", memory_enabled=True)
        ctx = await runtime.build_context(req)
        assert isinstance(ctx, AgentContext)
        await runtime.shutdown()
        await llm.shutdown()

    async def test_agent_info(self):
        llm = MockLLMProvider()
        await llm.initialize()
        info = AgentInfo(name="test-agent")
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm)
        await runtime.initialize()
        assert runtime.info.name == "test-agent"
        await runtime.shutdown()
        await llm.shutdown()


class TestAgentToolFlow:

    async def test_agent_with_echo_tool(self):
        llm = MockLLMProvider()
        await llm.initialize()
        registry = ToolRegistry()
        echo = EchoTool()
        registry.register(echo.info, lambda: EchoTool())
        info = AgentInfo(name="tool-agent")
        config = AgentConfig(tools_enabled=True)
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm, tool_registry=registry, config=config)
        await runtime.initialize()
        req = AgentRequest(user_input="echo hello", session_id="ts", agent_id="tool-agent", tools_enabled=True)
        resp = await runtime.run(req)
        assert resp.answer is not None
        await runtime.shutdown()
        await llm.shutdown()

    async def test_agent_with_calculator(self):
        llm = MockLLMProvider()
        await llm.initialize()
        registry = ToolRegistry()
        calc = CalculatorTool()
        registry.register(calc.info, lambda: CalculatorTool())
        info = AgentInfo(name="calc-agent")
        config = AgentConfig(tools_enabled=True)
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm, tool_registry=registry, config=config)
        await runtime.initialize()
        req = AgentRequest(user_input="2+3", session_id="cs", agent_id="calc-agent", tools_enabled=True)
        resp = await runtime.run(req)
        assert resp.answer is not None
        await runtime.shutdown()
        await llm.shutdown()
