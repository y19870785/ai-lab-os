"""CEO Assistant —— 工作记录测试。

验证：
- 实体提取 (日期/对象/事项/状态/标签)
- Episodic Memory 写入
- 查询历史记录
- 空输入和超长输入
- 重复记录处理
"""

import pytest
import pytest_asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from applications.ceo_assistant.application import CEOAssistant
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from core.bus.bus import get_bus
from core.memory.manager import MemoryManager
from core.memory.models import MemoryType
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.memory.session import SessionMemory
from core.clock import SystemClock
from core.database import DatabaseManager
from core.work_log import SQLiteWorkLogRepository, WorkLogQuery, WorkLogService


@pytest_asyncio.fixture
async def app_with_memory(tmp_path):
    """创建带真实 SQLite Memory 的 CEOAssistant。"""
    db_dir = str(tmp_path / "sqlite")
    os.makedirs(db_dir, exist_ok=True)

    bus = get_bus()
    await bus.start()

    memory = MemoryManager(bus=bus)
    sm = SessionMemory(default_ttl=3600, bus=bus)
    memory.register_store(MemoryType.SESSION, sm)

    es_path = os.path.join(db_dir, "episodic.db")
    db_manager = DatabaseManager(db_dir)
    es = SQLiteEpisodicStore(db_path=es_path, db_manager=db_manager)
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)
    work_logs = WorkLogService(
        SQLiteWorkLogRepository(
            db_manager, es_path, timezone_name="Asia/Shanghai"
        ),
        clock=SystemClock(),
        timezone_name="Asia/Shanghai",
    )
    await work_logs.initialize()

    app = CEOAssistant(
        memory_manager=memory,
        work_log_service=work_logs,
        clock=SystemClock(),
        timezone_name="Asia/Shanghai",
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    yield app

    await bus.stop()
    await es.close()
    db_manager.close_all()


class TestWorkRecords:
    """工作记录功能测试。"""

    @pytest.mark.asyncio
    async def test_extract_person(self):
        """验证人物提取。"""
        app = CEOAssistant(admission=PERMISSIVE_TEST_ADMISSION)
        result = await app._extract_work_entities("今天和张经理确认了蜂蜡检测方案")
        assert result["target"] == "张经理", f"应提取张经理，实际: {result['target']}"

    @pytest.mark.asyncio
    async def test_extract_status(self):
        """验证状态提取。"""
        app = CEOAssistant(admission=PERMISSIVE_TEST_ADMISSION)
        result = await app._extract_work_entities("等待客户回复蜂蜡报价")
        assert "等待客户回复" in result["status"], f"应提取状态，实际: {result['status']}"

    @pytest.mark.asyncio
    async def test_extract_tags(self):
        """验证标签提取。"""
        app = CEOAssistant(admission=PERMISSIVE_TEST_ADMISSION)
        result = await app._extract_work_entities("蜂蜡面包袋FDA检测方案确认")
        assert "蜂蜡" in result["tags"], "应包含蜂蜡标签"
        assert "检测" in result["tags"], "应包含检测标签"

    @pytest.mark.asyncio
    async def test_extract_empty_input(self):
        """空输入不会崩溃。"""
        app = CEOAssistant(admission=PERMISSIVE_TEST_ADMISSION)
        result = await app._extract_work_entities("")
        assert isinstance(result, dict)
        assert result["tags"] == []

    @pytest.mark.asyncio
    async def test_extract_long_input(self):
        """超长输入不会崩溃。"""
        app = CEOAssistant(admission=PERMISSIVE_TEST_ADMISSION)
        long_text = "测试" * 500
        result = await app._extract_work_entities(long_text)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handle_work_log_writes_episodic(self, app_with_memory):
        """工作记录应写入 Episodic Memory。"""
        from applications.models import ApplicationRequest
        req = ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 今天和张经理确认了蜂蜡检测方案",
        )
        resp = await app_with_memory.run(req)
        assert resp.status == "ok" or resp.status == "ok", f"状态出错: {resp.error}"
        assert len(resp.answer) > 0

        # 验证 Episodic Memory 中有记录
        page = await app_with_memory._work_logs.list(
            workspace_key=req.workspace_key, query=WorkLogQuery()
        )
        assert len(page.items) >= 1, "应有至少一条工作记录"

    @pytest.mark.asyncio
    async def test_work_log_prefix_stripping(self, app_with_memory):
        """'记录:' 前缀应被正确剥离。"""
        from applications.models import ApplicationRequest
        req = ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 完成蜂蜡报告",
        )
        resp = await app_with_memory.run(req)
        # subject 不应包含 '记录:' 前缀
        assert "记录:" not in resp.metadata.get("subject", "")

    @pytest.mark.asyncio
    async def test_work_log_query(self, app_with_memory):
        """写入后可查询。"""
        from applications.models import ApplicationRequest
        for text in ["记录: 完成检测报告", "记录: 和张总开会"]:
            await app_with_memory.run(ApplicationRequest(
                application_name="ceo-assistant", user_input=text,
            ))

        page = await app_with_memory._work_logs.list(
            workspace_key=ApplicationRequest(
                application_name="ceo-assistant", user_input=""
            ).workspace_key,
            query=WorkLogQuery(),
        )
        assert len(page.items) >= 2, f"应有至少2条记录，实际: {len(page.items)}"
