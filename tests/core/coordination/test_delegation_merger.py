"""Delegation + Merger + Planner Tests."""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.coordination.delegation import TaskDelegator
from core.coordination.merger import RuleBasedMerger, PriorityMerger
from core.coordination.planner import MultiAgentPlanner
from core.coordination.models import (
    AgentTask, AgentRoleType, AgentRole, TeamConfig,
    CollaborationContext, DelegationStatus,
)
from core.coordination.registry import AgentTeamRegistry


class TestTaskDelegator:

    async def test_delegate_without_runtime(self):
        delegator = TaskDelegator()
        task = AgentTask(
            assigned_agent="agent-1",
            title="Test",
            description="Test task",
        )
        task_id = await delegator.delegate(task)
        assert task_id == task.task_id
        assert task.status == DelegationStatus.COMPLETED

    async def test_delegate_and_get_status(self):
        delegator = TaskDelegator()
        task = AgentTask(assigned_agent="a1", title="T")
        await delegator.delegate(task)
        status = await delegator.get_status(task.task_id)
        assert status == DelegationStatus.COMPLETED

    async def test_delegate_and_get_result(self):
        delegator = TaskDelegator()
        task = AgentTask(assigned_agent="a1", title="T")
        await delegator.delegate(task)
        result = await delegator.get_result(task.task_id)
        assert result.get("status") == "ok"

    async def test_cancel_task(self):
        delegator = TaskDelegator()
        task = AgentTask(assigned_agent="a1", title="T")
        task_id = await delegator.delegate(task)
        assert await delegator.cancel(task_id)

    async def test_list_tasks_by_agent(self):
        delegator = TaskDelegator()
        await delegator.delegate(AgentTask(assigned_agent="a1", title="T1"))
        await delegator.delegate(AgentTask(assigned_agent="a2", title="T2"))
        await delegator.delegate(AgentTask(assigned_agent="a1", title="T3"))
        a1_tasks = await delegator.list_tasks("a1")
        assert len(a1_tasks) == 2
        all_tasks = await delegator.list_tasks()
        assert len(all_tasks) == 3


class TestMerger:

    async def test_rule_based_merger(self):
        merger = RuleBasedMerger()
        assert merger.strategy() == "rule"
        results = {
            "agent-1": {"answer": "Result from agent 1"},
            "agent-2": {"answer": "Result from agent 2"},
        }
        ctx = CollaborationContext(session_id="s1", goal="test")
        merged = await merger.merge(results, ctx)
        assert "agent-1" in merged
        assert "agent-2" in merged
        assert "Result from agent 1" in merged

    async def test_rule_based_merger_empty(self):
        merger = RuleBasedMerger()
        ctx = CollaborationContext(session_id="s1", goal="test")
        merged = await merger.merge({}, ctx)
        assert "(no results)" in merged

    async def test_priority_merger(self):
        merger = PriorityMerger()
        assert merger.strategy() == "priority"
        ctx = CollaborationContext(
            session_id="s1", goal="test",
            plan=[{"agent_id": "agent-2"}, {"agent_id": "agent-1"}],
        )
        results = {"agent-1": {"answer": "A1"}, "agent-2": {"answer": "A2"}}
        merged = await merger.merge(results, ctx)
        # agent-2 should come first per plan order
        assert merged.index("[agent-2]") < merged.index("[agent-1]")


class TestMultiAgentPlanner:

    async def test_plan_with_team(self):
        registry = AgentTeamRegistry()
        planner = MultiAgentPlanner(registry)
        team = TeamConfig(
            name="dev-team",
            agents=["a1", "a2"],
            roles={
                "a1": AgentRole(role_type=AgentRoleType.DEVELOPER, name="developer"),
                "a2": AgentRole(role_type=AgentRoleType.REVIEWER, name="reviewer"),
            },
        )
        tasks = await planner.plan("Build feature X", team)
        assert len(tasks) == 2
        assert tasks[0].assigned_agent == "a1"
        assert tasks[1].assigned_agent == "a2"
        assert "Build feature X" in tasks[0].description

    async def test_plan_empty_team(self):
        planner = MultiAgentPlanner()
        team = TeamConfig(name="empty", agents=[])
        tasks = await planner.plan("Some goal", team)
        assert len(tasks) == 0
