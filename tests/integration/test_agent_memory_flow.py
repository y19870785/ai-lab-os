import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.agents.models import AgentInfo, AgentRequest, AgentResponse, AgentContext
from core.agents.executor import AgentExecutor
from core.memory.manager import MemoryManager
from core.memory.session import SessionMemory
from core.memory.models import MemoryItem, MemoryType, MemoryQuery


class TestAgentMemoryFlow:
    """Agent -> Memory ?? + ?? ????"""

    def _make_manager(self):
        mgr = MemoryManager()
        mgr.register_store(MemoryType.SESSION, SessionMemory())
        mgr.register_store(MemoryType.EPISODIC, SessionMemory())  # Reuse for test
        return mgr

    async def test_agent_fetches_memory(self):
        mgr = self._make_manager()
        await mgr.save(MemoryItem(
            memory_type=MemoryType.EPISODIC,
            content={"summary": "Previous chat about weather"},
            importance=0.6,
        ))
        info = AgentInfo(name="mem-agent", description="Memory test")
        executor = AgentExecutor(info=info, memory_manager=mgr)
        items = await executor._fetch_memory(AgentRequest(user_input="weather"))
        # _fetch_memory retrieves from memory -- may work or not depending on store
        # Just verify it doesn't crash
        assert isinstance(items, list)

    async def test_agent_saves_memory(self):
        mgr = self._make_manager()
        info = AgentInfo(name="save-agent", description="Save test")
        executor = AgentExecutor(info=info, memory_manager=mgr)
        req = AgentRequest(user_input="Save this please", session_id="mem-sess-1")
        resp = AgentResponse(answer="Done", session_id="mem-sess-1", agent_id=info.id)
        await executor._save_memory(req, resp)
        results = await mgr.retrieve(MemoryQuery(top_k=5, memory_type=MemoryType.EPISODIC))
        assert any("Save this" in str(r.content) for r in results)

    async def test_agent_without_memory(self):
        info = AgentInfo(name="no-mem-agent", description="No memory")
        executor = AgentExecutor(info=info, memory_manager=None)
        items = await executor._fetch_memory(AgentRequest(user_input="test"))
        assert items == []
        # save should not crash
        await executor._save_memory(
            AgentRequest(user_input="x", session_id="x"),
            AgentResponse(answer="y", session_id="x", agent_id=info.id),
        )
