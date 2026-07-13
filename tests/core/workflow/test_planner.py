import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.workflow.planner import RulePlanner, get_planner
from core.workflow.models import WorkflowRequest, WorkflowStep, WorkflowPlan


class TestPlanner:
    async def test_rule_planner(self):
        planner = RulePlanner()
        steps = [WorkflowStep(name="s1"), WorkflowStep(name="s2"), WorkflowStep(name="s3")]
        req = WorkflowRequest(workflow_id="wf-1", user_input="test")
        plan = await planner.plan(req, steps)
        assert plan.workflow_id == "wf-1"
        assert len(plan.steps) == 3
        assert plan.estimated_steps == 3

    async def test_rule_planner_empty(self):
        planner = RulePlanner()
        req = WorkflowRequest(workflow_id="wf-empty")
        plan = await planner.plan(req, [])
        assert len(plan.steps) == 0

    def test_get_planner_rule(self):
        p = get_planner("rule")
        assert isinstance(p, RulePlanner)

    def test_get_planner_unknown(self):
        with pytest.raises(ValueError):
            get_planner("unknown")
