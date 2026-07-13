import pytest
from core.agents import ContextBuilder, AgentInfo, AgentRequest, AgentContext

class TestContextBuilder:
    @pytest.mark.asyncio
    async def test_build_basic(self):
        info = AgentInfo(name="Helper", description="I help people")
        builder = ContextBuilder(info)
        req = AgentRequest(user_input="hello")
        ctx = await builder.build(req)
        assert isinstance(ctx, AgentContext)
        assert len(ctx.messages) == 1
        assert ctx.messages[0]["role"] == "user"
        assert ctx.messages[0]["content"] == "hello"
    @pytest.mark.asyncio
    async def test_build_with_memory(self):
        info = AgentInfo(name="Test")
        builder = ContextBuilder(info)
        req = AgentRequest(user_input="hi")
        ctx = await builder.build(req, memory_items=[{"content": "previous chat"}])
        assert len(ctx.messages) >= 2
    @pytest.mark.asyncio
    async def test_build_with_knowledge(self):
        info = AgentInfo(name="Test")
        builder = ContextBuilder(info)
        req = AgentRequest(user_input="what is python")
        ctx = await builder.build(req, knowledge_results=[{"content": "Python is a language"}])
        assert len(ctx.messages) >= 2
    @pytest.mark.asyncio
    async def test_system_prompt_includes_capabilities(self):
        info = AgentInfo(name="Bot", capabilities=["search", "summarize"])
        builder = ContextBuilder(info)
        req = AgentRequest(user_input="help")
        ctx = await builder.build(req)
        assert "search" in ctx.system_prompt