import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.task.planner import RuleTaskPlanner, get_task_planner
from core.task.models import TaskRequest

class TestTaskPlanner:
    async def test_simple_order(self):
        p = RuleTaskPlanner()
        req = TaskRequest(workflow_names=["wf1", "wf2", "wf3"])
        plan = await p.plan(req)
        assert plan == ["wf1", "wf2", "wf3"]

    async def test_empty(self):
        p = RuleTaskPlanner()
        plan = await p.plan(TaskRequest(workflow_names=[]))
        assert plan == []

    def test_get_planner_rule(self):
        p = get_task_planner("rule")
        assert isinstance(p, RuleTaskPlanner)

    def test_get_planner_unknown(self):
        with pytest.raises(ValueError):
            get_task_planner("unknown")
