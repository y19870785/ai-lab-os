import pytest
from core.agents import DefaultAgentRuntime, AgentInfo, AgentRequest, AgentResponse, AgentStatus

class TestAgentRuntime:
    @pytest.mark.asyncio
    async def test_initialize_and_run(self):
        from core.providers.llm.mock import MockLLMProvider
        llm = MockLLMProvider(); await llm.initialize()
        info = AgentInfo(id="a1", name="Test")
        runtime = DefaultAgentRuntime(info, llm_provider=llm)
        await runtime.initialize()
        assert runtime.info.status == AgentStatus.READY
        resp = await runtime.run(AgentRequest(
            user_input="hello", memory_enabled=False,
            knowledge_enabled=False, tools_enabled=False,
        ))
        assert isinstance(resp, AgentResponse)
        assert resp.status == "ok"
    @pytest.mark.asyncio
    async def test_shutdown(self):
        info = AgentInfo(id="a1", name="Test")
        runtime = DefaultAgentRuntime(info)
        await runtime.initialize()
        await runtime.shutdown()
        assert runtime.info.status == AgentStatus.DESTROYED
    @pytest.mark.asyncio
    async def test_run_before_init_raises(self):
        info = AgentInfo(id="a1", name="Test")
        runtime = DefaultAgentRuntime(info)
        with pytest.raises(Exception):
            await runtime.run(AgentRequest(user_input="hello"))
    @pytest.mark.asyncio
    async def test_info_property(self):
        info = AgentInfo(id="a1", name="Helper", capabilities=["search"])
        runtime = DefaultAgentRuntime(info)
        assert runtime.info.name == "Helper"
        assert "search" in runtime.info.capabilities
