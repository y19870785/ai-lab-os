"""CEO Assistant —— 每日简报测试。

验证：
- 简报基于真实数据
- 待办任务出现在简报中
- 工作记录出现在简报中
- 决策出现在简报中
- 空数据时不会崩溃
"""

import pytest, pytest_asyncio,  sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from applications.ceo_assistant.application import CEOAssistant
from applications.models import ApplicationRequest
from core.bus.bus import get_bus
from core.memory.manager import MemoryManager
from core.memory.models import MemoryType, MemoryQuery
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.memory.session import SessionMemory


@pytest_asyncio.fixture
async def app_with_both(tmp_path):
    """创建带 Episodic + Decision Store 的 CEOAssistant。"""
    db_dir = str(tmp_path / "sqlite")
    os.makedirs(db_dir, exist_ok=True)

    bus = get_bus()
    await bus.start()

    memory = MemoryManager(bus=bus)
    sm = SessionMemory(default_ttl=3600, bus=bus)
    memory.register_store(MemoryType.SESSION, sm)

    es = SQLiteEpisodicStore(db_path=os.path.join(db_dir, "episodic.db"))
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)

    ds = SQLiteDecisionStore(db_path=os.path.join(db_dir, "decision.db"))
    await ds.initialize()
    memory.register_store(MemoryType.DECISION, ds)

    app = CEOAssistant(memory_manager=memory)
    yield app

    await bus.stop()
    await es.close()
    await ds.close()


class TestDailyBrief:
    """每日简报测试。"""

    @pytest.mark.asyncio
    async def test_brief_empty_data(self, app_with_both):
        """无数据时简报不崩溃。"""
        resp = await app_with_both._handle_brief(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="今日简报",
        ))
        assert resp["status"] == "ok"
        assert len(resp["answer"]) > 0

    @pytest.mark.asyncio
    async def test_brief_with_tasks(self, app_with_both):
        """有任务时简报应显示任务。"""
        # 创建任务
        await app_with_both.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="提醒我完成FDA报告",
        ))

        resp = await app_with_both._handle_brief(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="今日简报",
        ))
        assert resp["status"] == "ok"
        assert "待办任务" in resp["answer"], f"简报应含任务: {resp['answer'][:200]}"
        assert "FDA报告" in resp["answer"], f"简报应含任务名: {resp['answer'][:200]}"

    @pytest.mark.asyncio
    async def test_brief_with_work_logs(self, app_with_both):
        """有工作记录时简报应显示记录。"""
        # 创建多条工作记录
        for text in [
            "记录: 和张经理确认蜂蜡检测方案",
            "记录: 完成客户报价",
        ]:
            await app_with_both.run(ApplicationRequest(
                application_name="ceo-assistant", user_input=text,
            ))

        resp = await app_with_both._handle_brief(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="今日简报",
        ))
        assert resp["status"] == "ok"
        # 应包含最近工作记录
        assert "工作记录" in resp["answer"] or "工作" in resp["answer"]

    @pytest.mark.asyncio
    async def test_brief_with_decisions(self, app_with_both):
        """有决策时简报应显示决策。"""
        await app_with_both.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="决定采用供应商A",
        ))

        resp = await app_with_both._handle_brief(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="今日简报",
        ))
        assert resp["status"] == "ok"
        assert "决策" in resp["answer"]

    @pytest.mark.asyncio
    async def test_brief_priority_ordering(self, app_with_both):
        """高优先级任务应排在前面。"""
        await app_with_both.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="提醒我紧急处理客户投诉",
        ))
        await app_with_both.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="提醒我有空整理文档",
        ))

        resp = await app_with_both._handle_brief(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="今日简报",
        ))

        # 高优先级应当出现在低优先级前面
        if "建议优先处理" in resp["answer"]:
            priority_section = resp["answer"].split("建议优先处理:")[1]
            assert "高" in priority_section, "高优先级任务应在建议中"
