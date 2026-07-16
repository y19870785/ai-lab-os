"""CEO Assistant —— 端到端集成测试。

验证完整业务流程：记录→任务→决策→简报→查询
"""

import pytest, pytest_asyncio,  sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.reminder_intent import TaskReminderIntentParser
from core.clock import SystemClock
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from applications.models import ApplicationRequest
from core.bus.bus import get_bus
from core.memory.manager import MemoryManager
from core.memory.models import MemoryType, MemoryQuery
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.memory.session import SessionMemory
from core.database import DatabaseManager
from core.user_tasks import SQLiteUserTaskRepository, UserTaskService


@pytest_asyncio.fixture
async def full_app(tmp_path):
    """完整 Memory 环境。"""
    db_dir = str(tmp_path / "sqlite")
    os.makedirs(db_dir, exist_ok=True)

    bus = get_bus()
    await bus.start()

    memory = MemoryManager(bus=bus)
    memory.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus))

    es = SQLiteEpisodicStore(db_path=os.path.join(db_dir, "episodic.db"))
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)

    ds = SQLiteDecisionStore(db_path=os.path.join(db_dir, "decision.db"))
    await ds.initialize()
    memory.register_store(MemoryType.DECISION, ds)

    db_manager = DatabaseManager(db_dir)
    task_repo = SQLiteUserTaskRepository(db_manager, os.path.join(db_dir, "tasks.db"))
    task_service = UserTaskService(task_repo, bus=bus)
    await task_service.initialize()
    app = CEOAssistant(
        memory_manager=memory,
        user_task_service=task_service,
        task_intent_parser=TaskReminderIntentParser("Asia/Shanghai", SystemClock()),
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    yield app

    await bus.stop()
    await es.close()
    await ds.close()
    await task_service.close()
    db_manager.close_all()


class TestEndToEnd:
    """端到端业务场景。"""

    @pytest.mark.asyncio
    async def test_full_workday_cycle(self, full_app):
        """模拟一个完整工作日。"""
        # 早上：查看简报
        resp = await full_app._handle_brief(ApplicationRequest(
            application_name="ceo-assistant", user_input="简报",
        ))
        assert resp["status"] == "ok"

        # 记录工作
        await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 和张经理确认蜂蜡检测方案",
        ))
        await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 完成客户报价",
        ))

        # 创建任务
        await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：跟进FDA检测结果",
        ))

        # 记录决策
        await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="决定先完成蜂蜡检测再处理新报价",
        ))

        # 下班前：再次查看简报
        resp = await full_app._handle_brief(ApplicationRequest(
            application_name="ceo-assistant", user_input="简报",
        ))
        assert resp["status"] == "ok"

        # 简报应有完整信息
        answer = resp["answer"]
        assert "工作记录" in answer, f"简报应有工作记录: {answer[:300]}"
        assert "待办" in answer, f"简报应有待办: {answer[:300]}"
        assert "决策" in answer, f"简报应有决策: {answer[:300]}"

    @pytest.mark.asyncio
    async def test_conversation_memory(self, full_app):
        """连续对话应积累数据。"""
        # Turn 1: 记录
        resp1 = await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 和张经理开会讨论蜂蜡方案",
        ))
        assert resp1.status == "ok"

        # Turn 2: 创建任务
        resp2 = await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：交报告",
        ))
        assert resp2.status == "ok"

        # Turn 3: 查看简报，前面数据应在
        resp3 = await full_app._handle_brief(ApplicationRequest(
            application_name="ceo-assistant", user_input="简报",
        ))
        assert resp3["status"] == "ok" and len(resp3["answer"]) > 0
        assert "待办" in resp3["answer"]

    @pytest.mark.asyncio
    async def test_intent_routing_in_context(self, full_app):
        """不同意图在同一 session 中正确路由。"""
        # work_log
        r1 = await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 测试路由功能",
        ))
        assert r1.status == "ok"

        # task
        r2 = await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：完成路由测试",
        ))
        assert r2.status == "ok"

        # decision
        r3 = await full_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="决定采用路由方案A",
        ))
        assert r3.status == "ok"
