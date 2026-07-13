import pytest
from core.workflow.checkpoint import CheckpointManager
from core.workflow.models import WorkflowCheckpoint, WorkflowStatus


class TestCheckpointManager:
    def test_save_and_load(self):
        mgr = CheckpointManager()
        cp = WorkflowCheckpoint(workflow_id="wf-1", current_step_index=2,
                                variables={"x": 1})
        mgr.save(cp)
        loaded = mgr.load("wf-1")
        assert loaded is not None
        assert loaded.current_step_index == 2
        assert loaded.variables["x"] == 1

    def test_load_nonexistent(self):
        mgr = CheckpointManager()
        assert mgr.load("nope") is None

    def test_delete(self):
        mgr = CheckpointManager()
        mgr.save(WorkflowCheckpoint(workflow_id="wf-del"))
        assert mgr.delete("wf-del") is True
        assert mgr.delete("wf-del") is False
        assert mgr.load("wf-del") is None

    def test_exists(self):
        mgr = CheckpointManager()
        mgr.save(WorkflowCheckpoint(workflow_id="wf-exists"))
        assert mgr.exists("wf-exists") is True
        assert mgr.exists("no") is False

    def test_list_ids(self):
        mgr = CheckpointManager()
        mgr.save(WorkflowCheckpoint(workflow_id="a"))
        mgr.save(WorkflowCheckpoint(workflow_id="b"))
        ids = mgr.list_ids()
        assert set(ids) == {"a", "b"}

    def test_count(self):
        mgr = CheckpointManager()
        assert mgr.count == 0
        mgr.save(WorkflowCheckpoint(workflow_id="x"))
        assert mgr.count == 1
