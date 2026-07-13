import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.agents.models import AgentInfo, AgentRequest, AgentContext
from core.agents.executor import AgentExecutor
from core.agents.context import ContextBuilder


class TestAgentKnowledgeFlow:
    """Agent -> Knowledge ?? + Context ??"""

    async def test_context_builder_with_memory_and_knowledge(self):
        info = AgentInfo(name="ctx-agent", description="Context test", capabilities=["research"])
        builder = ContextBuilder(info)
        memory = [{"content": "User asked about pricing"}]
        knowledge = [{"content": "Product X costs ", "score": 0.95}]
        ctx = await builder.build(
            AgentRequest(user_input="What is the price?", session_id="s1"),
            memory_items=memory,
            knowledge_results=knowledge,
        )
        assert ctx.session_id == "s1"
        assert len(ctx.messages) >= 1
        assert ctx.messages[-1]["role"] == "user"
        assert ctx.messages[-1]["content"] == "What is the price?"

    async def test_context_builder_empty(self):
        info = AgentInfo(name="empty-ctx", description="Empty")
        builder = ContextBuilder(info)
        ctx = await builder.build(AgentRequest(user_input="hello", session_id="s2"))
        assert len(ctx.messages) == 1
        assert ctx.messages[0]["content"] == "hello"

    async def test_context_system_prompt(self):
        info = AgentInfo(name="Helper", description="I help with tasks", capabilities=["search", "calculate"])
        builder = ContextBuilder(info)
        ctx = await builder.build(AgentRequest(user_input="hi"))
        assert "Helper" in ctx.system_prompt
        assert "search" in ctx.system_prompt
