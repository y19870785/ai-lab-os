"""CEO Assistant —— 持久化与恢复测试。

验证：
- 工作记录重启恢复
- 任务重启恢复
- 决策重启恢复
- Workspace 数据隔离
"""

import pytest, sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from applications.ceo_assistant.application import CEOAssistant
from applications.models import ApplicationRequest
from core.bus.bus import get_bus
from core.memory.manager import MemoryManager
from core.memory.models import MemoryType, MemoryQuery
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.memory.session import SessionMemory


class TestPersistence:
    """持久化与恢复测试。"""

    @pytest.mark.asyncio
    async def test_work_log_persists(self, tmp_path):
        """工作记录在关闭重开后仍然存在。"""
        db_dir = str(tmp_path / "sqlite")
        os.makedirs(db_dir, exist_ok=True)
        ep_path = os.path.join(db_dir, "episodic.db")

        # 第一次：创建记录
        bus1 = get_bus()
        await bus1.start()
        mem1 = MemoryManager(bus=bus1)
        mem1.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus1))
        es1 = SQLiteEpisodicStore(db_path=ep_path)
        await es1.initialize()
        mem1.register_store(MemoryType.EPISODIC, es1)

        app1 = CEOAssistant(memory_manager=mem1)
        await app1.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 测试持久化数据",
        ))
        await bus1.stop()
        await es1.close()

        # 第二次：重新打开，验证数据还在
        bus2 = get_bus()
        await bus2.start()
        mem2 = MemoryManager(bus=bus2)
        mem2.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus2))
        es2 = SQLiteEpisodicStore(db_path=ep_path)
        await es2.initialize()
        mem2.register_store(MemoryType.EPISODIC, es2)

        q = MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=10)
        items = await mem2.retrieve_memory(q)
        work_logs = [i for i in items if i.content.get("type") == "work_log"]
        assert len(work_logs) >= 1, f"持久化失败，应有数据: {len(items)} 条记录"
        assert "持久化" in str(work_logs[0].content)

        await bus2.stop()
        await es2.close()

    @pytest.mark.asyncio
    async def test_task_persists(self, tmp_path):
        """任务在关闭重开后仍然存在。"""
        db_dir = str(tmp_path / "sqlite")
        os.makedirs(db_dir, exist_ok=True)
        ds_path = os.path.join(db_dir, "decision.db")

        # 创建任务
        bus1 = get_bus()
        await bus1.start()
        mem1 = MemoryManager(bus=bus1)
        mem1.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus1))
        ds1 = SQLiteDecisionStore(db_path=ds_path)
        await ds1.initialize()
        mem1.register_store(MemoryType.DECISION, ds1)

        app1 = CEOAssistant(memory_manager=mem1)
        await app1.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="提醒我完成持久化测试任务",
        ))
        await bus1.stop()
        await ds1.close()

        # 重新打开
        bus2 = get_bus()
        await bus2.start()
        mem2 = MemoryManager(bus=bus2)
        mem2.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus2))
        ds2 = SQLiteDecisionStore(db_path=ds_path)
        await ds2.initialize()
        mem2.register_store(MemoryType.DECISION, ds2)

        q = MemoryQuery(memory_type=MemoryType.DECISION, top_k=20)
        items = await mem2.retrieve_memory(q)
        tasks = [i for i in items if i.content.get("type") == "task"]
        assert len(tasks) >= 1, f"任务持久化失败: {len(tasks)} 条"

        await bus2.stop()
        await ds2.close()

    @pytest.mark.asyncio
    async def test_decision_persists(self, tmp_path):
        """决策在关闭重开后仍然存在。"""
        db_dir = str(tmp_path / "sqlite")
        os.makedirs(db_dir, exist_ok=True)
        ds_path = os.path.join(db_dir, "decision.db")

        # 创建决策
        bus1 = get_bus()
        await bus1.start()
        mem1 = MemoryManager(bus=bus1)
        mem1.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus1))
        ds1 = SQLiteDecisionStore(db_path=ds_path)
        await ds1.initialize()
        mem1.register_store(MemoryType.DECISION, ds1)

        app1 = CEOAssistant(memory_manager=mem1)
        await app1.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="决定采用持久化方案A",
        ))
        await bus1.stop()
        await ds1.close()

        # 重新打开
        bus2 = get_bus()
        await bus2.start()
        mem2 = MemoryManager(bus=bus2)
        mem2.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus2))
        ds2 = SQLiteDecisionStore(db_path=ds_path)
        await ds2.initialize()
        mem2.register_store(MemoryType.DECISION, ds2)

        q = MemoryQuery(memory_type=MemoryType.DECISION, top_k=20)
        items = await mem2.retrieve_memory(q)
        decisions = [i for i in items if i.content.get("type") == "decision"]
        assert len(decisions) >= 1, f"决策持久化失败: {len(decisions)} 条"

        await bus2.stop()
        await ds2.close()

    @pytest.mark.asyncio
    async def test_workspace_isolation(self, tmp_path):
        """不同 db 路径应数据隔离。"""
        db_dir1 = str(tmp_path / "ws1")
        db_dir2 = str(tmp_path / "ws2")
        os.makedirs(db_dir1, exist_ok=True)
        os.makedirs(db_dir2, exist_ok=True)

        # Workspace 1
        bus1 = get_bus(); await bus1.start()
        mem1 = MemoryManager(bus=bus1)
        mem1.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus1))
        es1 = SQLiteEpisodicStore(db_path=os.path.join(db_dir1, "episodic.db"))
        await es1.initialize()
        mem1.register_store(MemoryType.EPISODIC, es1)
        app1 = CEOAssistant(memory_manager=mem1)
        await app1.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: Workspace1的数据",
        ))

        # Workspace 2
        bus2 = get_bus(); await bus2.start()
        mem2 = MemoryManager(bus=bus2)
        mem2.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus2))
        es2 = SQLiteEpisodicStore(db_path=os.path.join(db_dir2, "episodic.db"))
        await es2.initialize()
        mem2.register_store(MemoryType.EPISODIC, es2)

        q = MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=10)
        items2 = await mem2.retrieve_memory(q)
        work_logs2 = [i for i in items2 if i.content.get("type") == "work_log"]
        # Workspace 2 不应看到 Workspace 1 的数据
        assert len(work_logs2) == 0, f"Workspace 2 不应有 WS1 的数据: {len(work_logs2)}"

        await bus1.stop(); await es1.close()
        await bus2.stop(); await es2.close()
