import pytest
from core.workflow.registry import WorkflowRegistry
from core.workflow.models import WorkflowInfo
from core.workflow.exceptions import WorkflowNotFoundError


class TestWorkflowRegistry:
    def test_register_and_get(self):
        reg = WorkflowRegistry()
        info = WorkflowInfo(name="test-wf")
        reg.register(info, lambda: None)
        assert reg.exists("test-wf")
        assert reg.get_info("test-wf").name == "test-wf"

    def test_unregister(self):
        reg = WorkflowRegistry()
        reg.register(WorkflowInfo(name="temp"), lambda: None)
        assert reg.unregister("temp") is True
        assert reg.unregister("temp") is False

    def test_get_nonexistent(self):
        reg = WorkflowRegistry()
        with pytest.raises(WorkflowNotFoundError):
            reg.get_info("nope")

    def test_list(self):
        reg = WorkflowRegistry()
        reg.register(WorkflowInfo(name="a"), lambda: None)
        reg.register(WorkflowInfo(name="b"), lambda: None)
        assert reg.count == 2
        assert len(reg.list()) == 2

    def test_search_by_tag(self):
        reg = WorkflowRegistry()
        reg.register(WorkflowInfo(name="a", tags=["fast", "test"]), lambda: None)
        reg.register(WorkflowInfo(name="b", tags=["slow"]), lambda: None)
        results = reg.search(tag="fast")
        assert len(results) == 1
        assert results[0].name == "a"

    def test_search_by_capability(self):
        reg = WorkflowRegistry()
        reg.register(WorkflowInfo(name="a", capabilities=["research"]), lambda: None)
        reg.register(WorkflowInfo(name="b", capabilities=["quote"]), lambda: None)
        results = reg.search(capability="research")
        assert len(results) == 1

    def test_search_by_name_pattern(self):
        reg = WorkflowRegistry()
        reg.register(WorkflowInfo(name="investment-research"), lambda: None)
        reg.register(WorkflowInfo(name="quote-generator"), lambda: None)
        results = reg.search(name_pattern="research")
        assert len(results) == 1
        assert results[0].name == "investment-research"
