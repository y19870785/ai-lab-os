"""Persistence Recovery Tests —— 持久化恢复验证。"""
import os
import tempfile
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestPersistenceRecovery:

    async def test_memory_persistence(self):
        """SQLite Memory 重启后数据保留。"""
        from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
        from core.memory.models import MemoryType, MemoryItem

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "test_recover.db")

        store = SQLiteEpisodicStore(db_path=db_path)
        await store.initialize()
        item = MemoryItem(memory_type=MemoryType.EPISODIC, content={"text": "persist test"})
        await store.save(item)
        saved_id = item.id
        count1 = await store.count()
        await store.close()

        store2 = SQLiteEpisodicStore(db_path=db_path)
        await store2.initialize()
        retrieved = await store2.get(saved_id)
        count2 = await store2.count()

        assert retrieved is not None
        assert retrieved.content.get("text") == "persist test"
        assert count2 >= count1
        await store2.close()

    async def test_multiple_writes_persist(self):
        """多次写入后重启，数据全部保留。"""
        from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
        from core.memory.models import MemoryType, MemoryItem

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "test_batch.db")

        store = SQLiteEpisodicStore(db_path=db_path)
        await store.initialize()
        ids = []
        for i in range(50):
            item = MemoryItem(memory_type=MemoryType.EPISODIC, content={"index": i})
            await store.save(item)
            ids.append(item.id)
        assert await store.count() == 50
        await store.close()

        store2 = SQLiteEpisodicStore(db_path=db_path)
        await store2.initialize()
        assert await store2.count() == 50
        for mid in ids[:5]:
            assert await store2.get(mid) is not None
        await store2.close()

    async def test_task_checkpoint_persist(self):
        """Task Checkpoint 可保存和恢复（内存实现）。"""
        from core.task.checkpoint import CheckpointManager
        from core.task.models import TaskCheckpoint, TaskStatus, TaskContext

        cpm = CheckpointManager()
        cp = TaskCheckpoint(
            task_id="task-1", status=TaskStatus.RUNNING,
            current_workflow_index=2,
            context=TaskContext(task_id="task-1", variables={"key": "val"}),
        )
        cpm.save(cp)
        loaded = cpm.load("task-1")
        assert loaded is not None
        assert loaded.task_id == "task-1"
        assert loaded.current_workflow_index == 2

    async def test_close_and_reopen_idempotent(self):
        """重复关闭/重开应该安全。"""
        from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "idem.db")

        store = SQLiteEpisodicStore(db_path=db_path)
        await store.initialize()
        await store.close()
        await store.close()  # double close

        await store.initialize()
        await store.close()
