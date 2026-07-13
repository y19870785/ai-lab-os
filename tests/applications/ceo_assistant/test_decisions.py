"""CEO Assistant —— 决策测试。

验证：
- 决策创建
- trigger/chosen/alternatives/reason 提取
- outcome 追踪
- 与 Decision Memory 集成
"""

import pytest, pytest_asyncio,  sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from applications.ceo_assistant.application import CEOAssistant
from applications.models import ApplicationRequest
from core.bus.bus import get_bus
from core.memory.manager import MemoryManager
from core.memory.models import MemoryType, MemoryQuery
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.memory.session import SessionMemory


@pytest_asyncio.fixture
async def app_with_decision(tmp_path):
    db_dir = str(tmp_path / "sqlite")
    os.makedirs(db_dir, exist_ok=True)

    bus = get_bus()
    await bus.start()

    memory = MemoryManager(bus=bus)
    sm = SessionMemory(default_ttl=3600, bus=bus)
    memory.register_store(MemoryType.SESSION, sm)

    ds_path = os.path.join(db_dir, "decision.db")
    ds = SQLiteDecisionStore(db_path=ds_path)
    await ds.initialize()
    memory.register_store(MemoryType.DECISION, ds)

    app = CEOAssistant(memory_manager=memory)
    yield app

    await bus.stop()
    await ds.close()


class TestDecisions:
    """决策记录测试。"""

    @pytest.mark.asyncio
    async def test_create_decision(self, app_with_decision):
        """创建决策并验证存储。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="决定采用175.300方案进行蜂蜡检测",
        ))
        assert resp.status == "ok", f"状态出错: {resp.error}"
        assert "已记录决策" in resp.answer

        q = MemoryQuery(memory_type=MemoryType.DECISION, top_k=10)
        items = await app_with_decision._memory.retrieve_memory(q)
        decisions = [i for i in items if i.content.get("type") == "decision"]
        assert len(decisions) >= 1, f"应有至少1条决策"

    @pytest.mark.asyncio
    async def test_decision_extract_chosen(self, app_with_decision):
        """chosen 字段应被正确提取。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="决定采用方案A进行检测",
        ))
        assert resp.status == "ok"
        assert "方案A" in resp.metadata.get("chosen", "")

    @pytest.mark.asyncio
    async def test_decision_extract_alternatives(self, app_with_decision):
        """alternatives 字段应被提取。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="这次先按175.300做，不先做完整迁移测试",
        ))
        assert resp.status == "ok"
        assert len(resp.metadata.get("alternatives", [])) > 0

    @pytest.mark.asyncio
    async def test_decision_extract_reason(self, app_with_decision):
        """reason 字段应被提取。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="采用方案A，因为成本更低效率更高",
        ))
        assert resp.status == "ok"
        assert len(resp.metadata.get("reason", "")) > 0

    @pytest.mark.asyncio
    async def test_decision_outcome_pending(self, app_with_decision):
        """新建决策的 outcome 应为 pending。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="选择供应商A",
        ))
        assert resp.status == "ok"
        assert resp.metadata.get("outcome_status") == "pending"

    @pytest.mark.asyncio
    async def test_decision_multiple(self, app_with_decision):
        """多条决策均应独立存储。"""
        for text in [
            "决定使用DeepSeek作为默认LLM",
            "选择Chroma作为Vector Store",
            "采用本地Embedding方案",
        ]:
            await app_with_decision.run(ApplicationRequest(
                application_name="ceo-assistant", user_input=text,
            ))

        q = MemoryQuery(memory_type=MemoryType.DECISION, top_k=20)
        items = await app_with_decision._memory.retrieve_memory(q)
        decisions = [i for i in items if i.content.get("type") == "decision"]
        assert len(decisions) >= 3, f"应有至少3条决策: {len(decisions)}"
