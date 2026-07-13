"""Agent Team Registry —— 管理 Agent Team 和 Agent Role 注册。

支持：
- Team 注册 / 查找 / 删除
- Role 注册 / 查找
- Agent → Role 映射
"""

from __future__ import annotations

from core.coordination.models import AgentRole, AgentRoleType, TeamConfig
from core.coordination.exceptions import TeamNotFoundError, RoleNotFoundError


class AgentTeamRegistry:
    """Agent Team 注册中心。"""

    def __init__(self):
        self._teams: dict[str, TeamConfig] = {}
        self._roles: dict[str, AgentRole] = {}  # role_name -> role
        self._agent_roles: dict[str, str] = {}  # agent_id -> role_name

    # ---- Team ----

    def register_team(self, config: TeamConfig) -> None:
        self._teams[config.team_id] = config

    def unregister_team(self, team_id: str) -> bool:
        return self._teams.pop(team_id, None) is not None

    def get_team(self, team_id: str) -> TeamConfig:
        if team_id not in self._teams:
            raise TeamNotFoundError(team_id)
        return self._teams[team_id]

    def list_teams(self) -> list[TeamConfig]:
        return list(self._teams.values())

    def find_team_by_name(self, name: str) -> list[TeamConfig]:
        return [t for t in self._teams.values() if t.name == name]

    @property
    def team_count(self) -> int:
        return len(self._teams)

    # ---- Role ----

    def register_role(self, role: AgentRole) -> None:
        self._roles[role.name] = role

    def get_role(self, name: str) -> AgentRole:
        if name not in self._roles:
            raise RoleNotFoundError(name)
        return self._roles[name]

    def list_roles(self) -> list[AgentRole]:
        return list(self._roles.values())

    def find_roles_by_capability(self, capability: str) -> list[AgentRole]:
        return [r for r in self._roles.values()
                if any(c.name == capability for c in r.capabilities)]

    def find_agents_for_capability(self, capability: str, team_id: str = "") -> list[str]:
        """在指定 Team 中查找具备某能力的 Agent。"""
        agents = []
        for agent_id, role_name in self._agent_roles.items():
            if team_id and team_id not in [t.team_id for t in self._teams.values()
                                            if agent_id in t.agents]:
                continue
            role = self._roles.get(role_name)
            if role and any(c.name == capability for c in role.capabilities):
                agents.append(agent_id)
        return agents

    def assign_role(self, agent_id: str, role_name: str) -> None:
        self._agent_roles[agent_id] = role_name

    def get_agent_role(self, agent_id: str) -> AgentRole | None:
        role_name = self._agent_roles.get(agent_id)
        if role_name:
            return self._roles.get(role_name)
        return None

    @property
    def role_count(self) -> int:
        return len(self._roles)
