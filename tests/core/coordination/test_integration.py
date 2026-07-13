"""Coordination Integration Tests —— 跨模块协作验证。"""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.coordination.orchestrator import AgentOrchestrator
from core.coordination.models import TeamConfig, AgentRole, AgentRoleType, CoordinationStatus


class TestCoordinationIntegration:

    async def test_full_orchestration_flow(self):
        """完整的 Orchestrator 流程：Team → Plan → Execute → Merge。"""
        orch = AgentOrchestrator()
        await orch.initialize()

        team = TeamConfig(
            name="full-team",
            agents=["planner", "researcher", "reviewer"],
            roles={
                "planner": AgentRole(role_type=AgentRoleType.PLANNER, name="planner"),
                "researcher": AgentRole(role_type=AgentRoleType.RESEARCHER, name="researcher"),
                "reviewer": AgentRole(role_type=AgentRoleType.REVIEWER, name="reviewer"),
            },
        )
        await orch.create_team(team)
        assert orch._registry.team_count == 1

        result = await orch.coordinate(goal="Design and implement a caching layer")
        assert result.status == CoordinationStatus.COMPLETED
        assert result.agent_count == 3
        assert len(result.agent_results) == 3
        assert result.merged_result != ""
        await orch.shutdown()

    async def test_event_bus_silent_no_crash(self):
        """验证 bus=None 时事件发布不崩溃。"""
        orch = AgentOrchestrator()  # bus=None
        await orch.initialize()
        team = TeamConfig(
            name="event-team", agents=["a1"],
            roles={"a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="executor")},
        )
        await orch.create_team(team)
        result = await orch.coordinate(goal="Event test", context={"session_id": "event-session"})
        assert result.status == CoordinationStatus.COMPLETED
        await orch.shutdown()

    async def test_empty_team_returns_zero_agents(self):
        """空 Team 产生合理结果。"""
        orch = AgentOrchestrator()
        await orch.initialize()
        team = TeamConfig(name="empty", agents=[], roles={})
        await orch.create_team(team)
        result = await orch.coordinate(goal="Should handle empty")
        assert result.agent_count == 0
        await orch.shutdown()

    async def test_multiple_coordination_sessions(self):
        """多个协调会话。"""
        orch = AgentOrchestrator()
        await orch.initialize()
        team = TeamConfig(
            name="mt", agents=["a1", "a2"],
            roles={
                "a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e"),
                "a2": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e2"),
            },
        )
        await orch.create_team(team)

        r1 = await orch.coordinate(goal="Task 1", context={"session_id": "s1"})
        r2 = await orch.coordinate(goal="Task 2", context={"session_id": "s2"})
        r3 = await orch.coordinate(goal="Task 3", context={"session_id": "s3"})

        assert r1.status == CoordinationStatus.COMPLETED
        assert r2.status == CoordinationStatus.COMPLETED
        assert r3.status == CoordinationStatus.COMPLETED
        assert orch.context_count == 3
        await orch.shutdown()
