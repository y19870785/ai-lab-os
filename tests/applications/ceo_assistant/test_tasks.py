"""CEO Assistant —— 任务测试。

验证：
- 创建任务
- 截止时间/优先级解析
- 查询任务
- 不再把正式任务写入 Decision Memory
"""

import os
import sys

import pytest
import pytest_asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.reminder_intent import TaskReminderIntentParser
from core.clock import SystemClock
from core.errors import FailureException
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from applications.models import ApplicationRequest
from core.bus.bus import get_bus
from core.memory.manager import MemoryManager
from core.memory.models import MemoryType, MemoryQuery
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.memory.session import SessionMemory
from core.database import DatabaseManager
from core.user_tasks import SQLiteUserTaskRepository, UserTaskService


@pytest_asyncio.fixture
async def app_with_decision(tmp_path):
    """创建带 Decision Store 的 CEOAssistant。"""
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
    await ds.close()
    await task_service.close()
    db_manager.close_all()


class TestTasks:
    """任务功能测试。"""

    @pytest.mark.asyncio
    async def test_create_task(self, app_with_decision):
        """创建任务并验证不再存入 Decision Memory。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：跟进FDA检测结果",
        ))
        assert resp.status == "ok", f"状态出错: {resp.error}"
        assert "已创建任务" in resp.answer, f"回复应含任务确认: {resp.answer}"

        assert len(await app_with_decision._user_tasks.list()) == 1
        q = MemoryQuery(memory_type=MemoryType.DECISION, top_k=10)
        assert not [i for i in await app_with_decision._memory.retrieve_memory(q)
                    if i.content.get("type") == "task"]

    @pytest.mark.asyncio
    async def test_task_only_does_not_create_deadline(self, app_with_decision):
        """Task-only intent remains independent from Reminder scheduling."""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：完成报告",
        ))
        assert resp.status == "ok"
        assert resp.metadata["metadata"]["intent"] == "task"
        assert resp.metadata["due_at"] is None

    @pytest.mark.asyncio
    async def test_task_priority_high(self, app_with_decision):
        """紧急关键词应触发高优先级。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：紧急处理客户投诉",
        ))
        assert resp.status == "ok"
        assert resp.metadata.get("priority") == "high"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("expression", [
        "明天下午完成报告",
        "明天下午3点三刻完成报告",
        "明天下午3点45分30秒完成报告",
    ])
    async def test_unparsed_deadline_is_explicit_and_not_fabricated(
        self, app_with_decision, expression
    ):
        with pytest.raises(FailureException) as exc_info:
            await app_with_decision.run(ApplicationRequest(
                application_name="ceo-assistant",
                user_input=f"提醒我{expression}",
            ))
        assert exc_info.value.failure.code == "reminder.time_unsupported"

    @pytest.mark.asyncio
    async def test_task_priority_default(self, app_with_decision):
        """无明确优先级时默认为中。"""
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：开会",
        ))
        assert resp.status == "ok"
        assert resp.metadata.get("priority") == "medium"

    @pytest.mark.asyncio
    async def test_task_query(self, app_with_decision):
        """查询任务返回已有任务。"""
        # 先创建
        await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="添加任务：完成FDA报告",
        ))
        # 再查询
        resp = await app_with_decision.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="查看我的待办列表",
        ))
        assert resp.status == "ok"
        assert "FDA报告" in resp.answer or "待办任务" in resp.answer

    @pytest.mark.asyncio
    async def test_task_multiple(self, app_with_decision):
        """多条任务均应存储。"""
        for text in [
            "添加任务：完成报告",
            "添加任务：明天开会",
            "添加任务：回复邮件",
        ]:
            await app_with_decision.run(ApplicationRequest(
                application_name="ceo-assistant", user_input=text,
            ))

        tasks = await app_with_decision._user_tasks.list()
        assert len(tasks) >= 3, f"应有至少3个任务: {len(tasks)}"
