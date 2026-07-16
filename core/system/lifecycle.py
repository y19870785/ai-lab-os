"""System lifecycle state machine -- single source of truth."""

from __future__ import annotations

import asyncio
from enum import Enum


class SystemLifecycleState(str, Enum):
    """Canonical lifecycle states.

    CREATED  -> STARTING -> READY -> DRAINING -> STOPPED.
    STARTING can also go directly to DRAINING (startup rollback).
    STARTING -> FAILED only when cleanup is impossible.
    STOPPED -> STARTING is forbidden (no restart).
    """

    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[SystemLifecycleState, set[SystemLifecycleState]] = {
    SystemLifecycleState.CREATED:  {SystemLifecycleState.STARTING, SystemLifecycleState.STOPPED},
    SystemLifecycleState.STARTING: {SystemLifecycleState.READY,
                                     SystemLifecycleState.DRAINING,
                                     SystemLifecycleState.FAILED},
    SystemLifecycleState.READY:    {SystemLifecycleState.DRAINING},
    SystemLifecycleState.DRAINING: {SystemLifecycleState.STOPPED, SystemLifecycleState.FAILED},
    SystemLifecycleState.STOPPED:  set(),
    SystemLifecycleState.FAILED:   set(),
}


class InvalidLifecycleTransitionError(Exception):
    """Raised when a state transition is not allowed."""


class LifecycleStateMachine:
    """Thread-safe, single-owner lifecycle state with concurrency protection."""

    def __init__(self) -> None:
        self._state: SystemLifecycleState = SystemLifecycleState.CREATED
        self._lock = asyncio.Lock()

    @property
    def state(self) -> SystemLifecycleState:
        return self._state

    @property
    def accepting_work(self) -> bool:
        return self._state == SystemLifecycleState.READY

    async def transition(
        self, target: SystemLifecycleState
    ) -> SystemLifecycleState:
        """Atomically transition to *target* if the move is valid."""
        async with self._lock:
            current = self._state
            if current == target:
                return current
            allowed = _VALID_TRANSITIONS.get(current, set())
            if target not in allowed:
                raise InvalidLifecycleTransitionError(
                    f"Transition {current.value} -> {target.value} is not allowed"
                )
            self._state = target
            return current

    async def try_transition(
        self, target: SystemLifecycleState
    ) -> SystemLifecycleState | None:
        """Attempt to transition; return previous state or None."""
        try:
            return await self.transition(target)
        except InvalidLifecycleTransitionError:
            return None
