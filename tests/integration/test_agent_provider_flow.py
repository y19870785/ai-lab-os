import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.agents.models import AgentInfo, AgentRequest, AgentContext
from core.agents.executor import AgentExecutor


class TestAgentProviderFlow:
    """Agent -> Provider Layer (Mock LLM) ????"""

    async def test_agent_with_mock_llm(self):
        class MockLLM:
            async def generate(self, req):
                from core.providers.llm.protocol import LLMResponse
                return LLMResponse(content=f"Echo: {req.messages[-1].content}")

        info = AgentInfo(name="llm-agent", description="LLM test")
        executor = AgentExecutor(info=info, llm_provider=MockLLM())
        ctx = AgentContext(session_id="s1", agent_id=info.id)
        ctx.messages = [{"role": "user", "content": "Hello"}]
        answer = await executor._invoke_llm(ctx)
        assert "Echo: Hello" in answer

    async def test_agent_without_llm(self):
        info = AgentInfo(name="no-llm-agent", description="No LLM")
        executor = AgentExecutor(info=info, llm_provider=None)
        ctx = AgentContext(session_id="s2", agent_id=info.id)
        ctx.messages = [{"role": "user", "content": "Hi"}]
        answer = await executor._invoke_llm(ctx)
        assert "[no llm]" in answer or "Hi" in answer

    async def test_full_execute_with_mock_llm(self):
        class MockLLM:
            async def generate(self, req):
                from core.providers.llm.protocol import LLMResponse
                return LLMResponse(content="The answer is 42")

        info = AgentInfo(name="full-agent", description="Full test")
        executor = AgentExecutor(info=info, llm_provider=MockLLM())
        req = AgentRequest(user_input="What is the answer?", session_id="s3")
        resp = await executor.execute(req)
        assert resp.status == "ok"
        assert "42" in resp.answer
        assert resp.session_id == "s3"
        assert resp.agent_id == info.id
        assert resp.latency_ms >= 0  # may be 0 for mock LLM
