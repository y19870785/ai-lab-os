"""AgentRegistry — agent registration and discovery."""
from __future__ import annotations
from typing import Callable
from core.agents.models import AgentInfo
from core.agents.exceptions import AgentNotFoundError

AgentFactory = Callable[[], object]  # Returns an AgentRuntime-like instance

class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentInfo] = {}
        self._factories: dict[str, AgentFactory] = {}
    def register(self, info: AgentInfo, factory: AgentFactory | None = None) -> None:
        self._agents[info.id] = info
        if factory:
            self._factories[info.id] = factory
    def unregister(self, agent_id: str) -> bool:
        self._factories.pop(agent_id, None)
        return self._agents.pop(agent_id, None) is not None
    def get(self, agent_id: str) -> AgentInfo:
        info = self._agents.get(agent_id)
        if info is None: raise AgentNotFoundError(f"Agent {agent_id} not found")
        return info
    def get_factory(self, agent_id: str) -> AgentFactory | None:
        return self._factories.get(agent_id)
    def list(self) -> list[AgentInfo]:
        return list(self._agents.values())
    def find_by_capability(self, capability: str) -> list[AgentInfo]:
        return [i for i in self._agents.values() if capability in i.capabilities]
    def find_by_name(self, name: str) -> list[AgentInfo]:
        return [i for i in self._agents.values() if i.name == name]
    def exists(self, agent_id: str) -> bool:
        return agent_id in self._agents
    @property
    def count(self) -> int:
        return len(self._agents)