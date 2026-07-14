"""Agent Lifecycle Manager — state machine."""
from __future__ import annotations
from core.agents.models import AgentStatus, AgentInfo
from core.agents.exceptions import AgentNotReadyError

VALID_TRANSITIONS = {
    AgentStatus.CREATED:     {AgentStatus.INITIALIZED, AgentStatus.ERROR, AgentStatus.DESTROYED},
    AgentStatus.INITIALIZED: {AgentStatus.READY, AgentStatus.ERROR, AgentStatus.DESTROYED},
    AgentStatus.READY:       {AgentStatus.RUNNING, AgentStatus.STOPPED, AgentStatus.ERROR, AgentStatus.DESTROYED},
    AgentStatus.RUNNING:     {AgentStatus.IDLE, AgentStatus.DEGRADED, AgentStatus.ERROR, AgentStatus.STOPPED},
    AgentStatus.IDLE:        {AgentStatus.RUNNING, AgentStatus.STOPPED, AgentStatus.ERROR, AgentStatus.DESTROYED},
    AgentStatus.DEGRADED:    {AgentStatus.RUNNING, AgentStatus.STOPPED, AgentStatus.ERROR, AgentStatus.DESTROYED},
    AgentStatus.STOPPED:     {AgentStatus.DESTROYED},
    AgentStatus.ERROR:       {AgentStatus.STOPPED, AgentStatus.DESTROYED},
    AgentStatus.DESTROYED:   set(),
}

class AgentLifecycleManager:
    def __init__(self, info: AgentInfo):
        self._info = info
    def current(self) -> AgentStatus:
        return self._info.status
    def can_transition(self, target: AgentStatus) -> bool:
        return target in VALID_TRANSITIONS.get(self._info.status, set())
    def transition(self, target: AgentStatus) -> bool:
        if not self.can_transition(target):
            return False
        self._info.status = target
        return True
    def assert_ready(self) -> None:
        if self._info.status not in (AgentStatus.READY, AgentStatus.IDLE, AgentStatus.DEGRADED):
            raise AgentNotReadyError(f"Agent {self._info.name} is {self._info.status.value}, not ready")
    def assert_runnable(self) -> None:
        if self._info.status not in (AgentStatus.READY, AgentStatus.IDLE, AgentStatus.DEGRADED, AgentStatus.RUNNING):
            raise AgentNotReadyError(f"Agent {self._info.name} is {self._info.status.value}, cannot run")
