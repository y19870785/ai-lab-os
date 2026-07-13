import pytest
from core.task.context import ContextManager

class TestContextManager:
    def test_create_and_get(self):
        mgr = ContextManager()
        ctx = mgr.create("t1", {"k": "v"})
        assert ctx.variables["k"] == "v"
        assert mgr.get("t1") is ctx

    def test_update_variables(self):
        mgr = ContextManager()
        mgr.create("t1", {"a": 1})
        mgr.update_variables("t1", {"b": 2})
        ctx = mgr.get("t1")
        assert ctx.variables == {"a": 1, "b": 2}

    def test_add_memory(self):
        mgr = ContextManager()
        mgr.create("t1")
        mgr.add_memory("t1", "m1")
        mgr.add_memory("t1", "m1")  # no duplicate
        assert mgr.get("t1").memory_ids == ["m1"]

    def test_add_workflow(self):
        mgr = ContextManager()
        mgr.create("t1")
        mgr.add_workflow("t1", "wf1")
        mgr.add_workflow("t1", "wf2")
        assert mgr.get("t1").workflow_ids == ["wf1", "wf2"]

    def test_remove(self):
        mgr = ContextManager()
        mgr.create("t1")
        mgr.remove("t1")
        assert mgr.get("t1") is None

    def test_nonexistent_operations_safe(self):
        mgr = ContextManager()
        mgr.update_variables("nope", {"x": 1})  # no crash
        mgr.add_memory("nope", "m1")  # no crash
