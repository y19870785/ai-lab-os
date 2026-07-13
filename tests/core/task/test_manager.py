import pytest
from core.task.manager import TaskManager
from core.task.models import TaskInfo, TaskStatus

class TestTaskManager:
    def test_register_and_get(self):
        mgr = TaskManager()
        info = TaskInfo(name="m1")
        mgr.register(info)
        assert mgr.exists(info.id)
        assert mgr.get(info.id).name == "m1"

    def test_status_management(self):
        mgr = TaskManager()
        info = TaskInfo(name="m2")
        mgr.register(info, TaskStatus.RUNNING)
        assert mgr.get_status(info.id) == TaskStatus.RUNNING
        mgr.set_status(info.id, TaskStatus.COMPLETED)
        assert mgr.get_status(info.id) == TaskStatus.COMPLETED

    def test_statistics(self):
        mgr = TaskManager()
        for i in range(3):
            mgr.register(TaskInfo(name=f"t{i}"), TaskStatus.RUNNING)
        mgr.register(TaskInfo(name="done"), TaskStatus.COMPLETED)
        stats = mgr.statistics()
        assert stats.total == 4
        assert stats.active == 3
        assert stats.completed == 1

    def test_search(self):
        mgr = TaskManager()
        mgr.register(TaskInfo(name="hello", tags=["greeting"]))
        mgr.register(TaskInfo(name="world", tags=["greeting"]))
        assert len(mgr.search(tag="greeting")) == 2

    def test_unregister(self):
        mgr = TaskManager()
        info = TaskInfo(name="tmp")
        mgr.register(info)
        assert mgr.unregister(info.id) is True
        assert mgr.exists(info.id) is False
