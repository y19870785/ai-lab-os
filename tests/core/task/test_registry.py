import pytest
from core.task.registry import TaskRegistry
from core.task.models import TaskInfo, TaskStatus
from core.task.exceptions import TaskNotFoundError

class TestTaskRegistry:
    def test_register_and_get(self):
        reg = TaskRegistry()
        info = TaskInfo(name="t1")
        reg.register(info)
        assert reg.exists(info.id)
        assert reg.get(info.id).name == "t1"

    def test_unregister(self):
        reg = TaskRegistry()
        info = TaskInfo(name="temp")
        reg.register(info)
        assert reg.unregister(info.id) is True
        assert reg.unregister(info.id) is False

    def test_get_nonexistent(self):
        with pytest.raises(TaskNotFoundError):
            TaskRegistry().get("nope")

    def test_status_tracking(self):
        reg = TaskRegistry()
        info = TaskInfo(name="t1")
        reg.register(info, TaskStatus.RUNNING)
        assert reg.get_status(info.id) == TaskStatus.RUNNING
        reg.set_status(info.id, TaskStatus.COMPLETED)
        assert reg.get_status(info.id) == TaskStatus.COMPLETED

    def test_search_by_tag(self):
        reg = TaskRegistry()
        reg.register(TaskInfo(name="a", tags=["fast"]))
        reg.register(TaskInfo(name="b", tags=["slow"]))
        assert len(reg.search(tag="fast")) == 1

    def test_search_by_name(self):
        reg = TaskRegistry()
        reg.register(TaskInfo(name="daily-report"))
        reg.register(TaskInfo(name="weekly-digest"))
        assert len(reg.search(name_pattern="daily")) == 1

    def test_statistics(self):
        reg = TaskRegistry()
        reg.register(TaskInfo(name="a"), TaskStatus.RUNNING)
        reg.register(TaskInfo(name="b"), TaskStatus.COMPLETED)
        reg.register(TaskInfo(name="c"), TaskStatus.FAILED)
        stats = reg.statistics()
        assert stats["total"] == 3
        assert stats["active"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 1
