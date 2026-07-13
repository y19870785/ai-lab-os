"""Agent Orchestrator Integration Tests."""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.coordination.orchestrator import AgentOrchestrator
from core.coordination.registry import AgentTeamRegistry
from core.coordination.models import (
    TeamConfig, AgentRole, AgentRoleType,
    CoordinationStatus,
)


class TestAgentOrchestrator:

    async def test_initialize_and_shutdown(self):
        orch = AgentOrchestrator()
        await orch.initialize()
        assert orch._initialized
        await orch.shutdown()
        assert not orch._initialized

    async def test_create_team(self):
        orch = AgentOrchestrator()
        await orch.initialize()
        team = TeamConfig(
            name="test-team",
            agents=["a1", "a2"],
            roles={
                "a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="executor"),
                "a2": AgentRole(role_type=AgentRoleType.REVIEWER, name="reviewer"),
            },
        )
        await orch.create_team(team)
        assert orch._registry.team_count == 1
        assert orch._registry.role_count == 2
        await orch.shutdown()

    async def test_coordinate_basic(self):
        orch = AgentOrchestrator()
        await orch.initialize()

        team = TeamConfig(
            name="dev-team",
            agents=["a1", "a2"],
            roles={
                "a1": AgentRole(role_type=AgentRoleType.DEVELOPER, name="developer"),
                "a2": AgentRole(role_type=AgentRoleType.REVIEWER, name="reviewer"),
            },
        )
        await orch.create_team(team)

        result = await orch.coordinate(
            goal="Build hello world",
            context={"team_id": team.team_id},
        )

        assert result.status == CoordinationStatus.COMPLETED
        assert result.agent_count == 2
        assert result.merged_result != ""
        assert "a1" in result.agent_results or "a2" in result.agent_results
        await orch.shutdown()

    async def test_coordinate_no_team_uses_first(self):
        orch = AgentOrchestrator()
        await orch.initialize()

        team = TeamConfig(
            name="solo-team", agents=["a1"],
            roles={"a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="executor")},
        )
        await orch.create_team(team)

        result = await orch.coordinate(goal="Simple task")
        assert result.status == CoordinationStatus.COMPLETED
        await orch.shutdown()

    async def test_coordinate_single_agent(self):
        orch = AgentOrchestrator()
        await orch.initialize()

        team = TeamConfig(
            name="solo", agents=["solo-agent"],
            roles={"solo-agent": AgentRole(role_type=AgentRoleType.RESEARCHER, name="researcher")},
        )
        await orch.create_team(team)

        result = await orch.coordinate(goal="Research AI trends")
        assert result.agent_count == 1
        await orch.shutdown()

    async def test_get_context(self):
        orch = AgentOrchestrator()
        await orch.initialize()
        team = TeamConfig(name="t", agents=["a1"], roles={"a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e")})
        await orch.create_team(team)
        await orch.coordinate(goal="Test", context={"session_id": "ctx-session"})
        ctx = await orch.get_context("ctx-session")
        assert ctx is not None
        assert ctx.goal == "Test"
        await orch.shutdown()

    async def test_status_tracking(self):
        orch = AgentOrchestrator()
        await orch.initialize()
        team = TeamConfig(name="t", agents=["a1"], roles={"a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e")})
        await orch.create_team(team)
        await orch.coordinate(goal="Status test", context={"session_id": "status-session"})
        assert orch.status("status-session") == CoordinationStatus.COMPLETED
        await orch.shutdown()

    async def test_cancel(self):
        orch = AgentOrchestrator()
        await orch.initialize()
        team = TeamConfig(name="t", agents=["a1"], roles={"a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e")})
        await orch.create_team(team)
        await orch.coordinate(goal="Cancel test", context={"session_id": "cancel-session"})
        # Cancel after completion (should succeed, state is finalized)
        assert await orch.cancel("cancel-session")
        await orch.shutdown()

    async def test_multiple_teams(self):
        orch = AgentOrchestrator()
        await orch.initialize()
        team1 = TeamConfig(name="team-a", agents=["a1"], roles={"a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e")})
        team2 = TeamConfig(name="team-b", agents=["b1"], roles={"b1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e")})
        await orch.create_team(team1)
        await orch.create_team(team2)
        assert orch._registry.team_count == 2

        result = await orch.coordinate(goal="Team B task", context={"team_id": team2.team_id})
        assert result.status == CoordinationStatus.COMPLETED
        await orch.shutdown()

    async def test_events_fired(self):
        """Verify events fire without error (no bus = silent)."""
        orch = AgentOrchestrator()
        await orch.initialize()
        team = TeamConfig(name="t", agents=["a1"], roles={"a1": AgentRole(role_type=AgentRoleType.EXECUTOR, name="e")})
        await orch.create_team(team)
        result = await orch.coordinate(goal="Event test")
        assert result.status == CoordinationStatus.COMPLETED
        await orch.shutdown()
