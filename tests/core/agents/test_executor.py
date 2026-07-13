import pytest
from core.agents import AgentExecutor, AgentInfo, AgentRequest, AgentResponse, AgentConfig
from core.agents.models import AgentStatus

class TestAgentExecutor:
    @pytest.mark.asyncio
    async def test_execute_basic(self):
        info = AgentInfo(id="a1", name="Echo")
        executor = AgentExecutor(info)
        resp = await executor.execute(AgentRequest(user_input="hello"))
        assert isinstance(resp, AgentResponse)
        assert "hello" in resp.answer
        assert resp.status == "ok"
        assert resp.latency_ms >= 0
    @pytest.mark.asyncio
    async def test_execute_no_llm(self):
        info = AgentInfo(id="a1", name="Test")
        executor = AgentExecutor(info)
        resp = await executor.execute(AgentRequest(user_input="ping"))
        assert "[no llm]" in resp.answer
        assert "ping" in resp.answer
    @pytest.mark.asyncio
    async def test_execute_with_mock_llm(self):
        from core.providers.llm.mock import MockLLMProvider
        llm = MockLLMProvider()
        await llm.initialize()
        info = AgentInfo(id="a1", name="Test")
        executor = AgentExecutor(info, llm_provider=llm)
        resp = await executor.execute(AgentRequest(user_input="hello"))
        assert "[mock]" in resp.answer
    @pytest.mark.asyncio
    async def test_execute_session_id(self):
        info = AgentInfo(id="a1", name="Test")
        executor = AgentExecutor(info)
        resp = await executor.execute(AgentRequest(user_input="hi", session_id="sess_x"))
        assert resp.session_id == "sess_x"
        assert resp.agent_id == "a1"
    @pytest.mark.asyncio
    async def test_execute_with_memory_disabled(self):
        info = AgentInfo(id="a1", name="Test")
        executor = AgentExecutor(info)
        resp = await executor.execute(AgentRequest(user_input="hi", memory_enabled=False))
        assert resp.status == "ok"