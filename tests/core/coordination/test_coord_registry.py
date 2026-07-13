"""Coordination Registry Tests."""
import pytest
from core.coordination.models import AgentRole, AgentRoleType, AgentCapability, TeamConfig
from core.coordination.registry import AgentTeamRegistry
from core.coordination.exceptions import TeamNotFoundError, RoleNotFoundError


class TestAgentTeamRegistry:

    def test_register_and_get_team(self):
        reg = AgentTeamRegistry()
        config = TeamConfig(name="test-team", agents=["a1"])
        reg.register_team(config)
        assert reg.team_count == 1
        fetched = reg.get_team(config.team_id)
        assert fetched.name == "test-team"

    def test_get_nonexistent_team_raises(self):
        reg = AgentTeamRegistry()
        with pytest.raises(TeamNotFoundError):
            reg.get_team("nonexistent")

    def test_unregister_team(self):
        reg = AgentTeamRegistry()
        config = TeamConfig(name="test-team", agents=["a1"])
        reg.register_team(config)
        assert reg.unregister_team(config.team_id)
        assert reg.team_count == 0

    def test_list_teams(self):
        reg = AgentTeamRegistry()
        reg.register_team(TeamConfig(name="t1", agents=["a1"]))
        reg.register_team(TeamConfig(name="t2", agents=["a2"]))
        assert len(reg.list_teams()) == 2

    def test_find_team_by_name(self):
        reg = AgentTeamRegistry()
        reg.register_team(TeamConfig(name="dev", agents=["a1"]))
        reg.register_team(TeamConfig(name="qa", agents=["a2"]))
        result = reg.find_team_by_name("dev")
        assert len(result) == 1
        assert result[0].name == "dev"


class TestRoleRegistry:

    def test_register_and_get_role(self):
        reg = AgentTeamRegistry()
        role = AgentRole(role_type=AgentRoleType.RESEARCHER, name="researcher")
        reg.register_role(role)
        fetched = reg.get_role("researcher")
        assert fetched.role_type == AgentRoleType.RESEARCHER

    def test_get_nonexistent_role_raises(self):
        reg = AgentTeamRegistry()
        with pytest.raises(RoleNotFoundError):
            reg.get_role("unknown")

    def test_find_roles_by_capability(self):
        reg = AgentTeamRegistry()
        role1 = AgentRole(name="r1", capabilities=[AgentCapability(name="search")])
        role2 = AgentRole(name="r2", capabilities=[AgentCapability(name="code")])
        reg.register_role(role1)
        reg.register_role(role2)
        result = reg.find_roles_by_capability("search")
        assert len(result) == 1
        assert result[0].name == "r1"

    def test_assign_and_get_agent_role(self):
        reg = AgentTeamRegistry()
        role = AgentRole(role_type=AgentRoleType.DEVELOPER, name="developer")
        reg.register_role(role)
        reg.assign_role("agent-1", "developer")
        fetched = reg.get_agent_role("agent-1")
        assert fetched is not None
        assert fetched.name == "developer"

    def test_find_agents_for_capability(self):
        reg = AgentTeamRegistry()
        role = AgentRole(name="dev", capabilities=[AgentCapability(name="code")])
        reg.register_role(role)
        reg.assign_role("agent-1", "dev")
        agents = reg.find_agents_for_capability("code")
        assert "agent-1" in agents
