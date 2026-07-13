import pytest
from core.task.checkpoint import CheckpointManager
from core.task.models import TaskCheckpoint

class TestCheckpointManager:
    def test_save_and_load(self):
        mgr = CheckpointManager()
        cp = TaskCheckpoint(task_id="t1", current_workflow_index=2)
        mgr.save(cp)
        loaded = mgr.load("t1")
        assert loaded is not None
        assert loaded.current_workflow_index == 2

    def test_delete(self):
        mgr = CheckpointManager()
        mgr.save(TaskCheckpoint(task_id="td"))
        assert mgr.delete("td") is True
        assert mgr.delete("td") is False

    def test_exists(self):
        mgr = CheckpointManager()
        mgr.save(TaskCheckpoint(task_id="tx"))
        assert mgr.exists("tx")

    def test_list_ids(self):
        mgr = CheckpointManager()
        mgr.save(TaskCheckpoint(task_id="a"))
        mgr.save(TaskCheckpoint(task_id="b"))
        assert set(mgr.list_ids()) == {"a", "b"}
