"""Internal work admission contract backed by the system lifecycle."""

from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Coroutine, Iterator, Protocol, TypeVar

from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.lifecycle import LifecycleStateMachine, SystemLifecycleState


T = TypeVar("T")


@dataclass(frozen=True)
class _AcceptedWorkScope:
    owner: asyncio.Task[Any]


class WorkAdmission(Protocol):
    """Narrow dependency used by canonical work entrypoints."""

    def ensure_accepting_work(self) -> None:
        """Reject work unless the shared lifecycle permits admission."""

    def admit(self) -> AbstractContextManager[None]:
        """Accept one outer work item while allowing nested downstream calls."""

    def spawn_accepted_task(
        self,
        coroutine: Coroutine[Any, Any, T],
        *,
        name: str | None = None,
    ) -> asyncio.Task[T]:
        """Explicitly continue accepted work in a Scheduler-owned task."""


class WorkAdmissionGate:
    """Synchronous admission gate with accepted-work context propagation."""

    def __init__(self, lifecycle: LifecycleStateMachine) -> None:
        self._lifecycle = lifecycle
        self._accepted_scope: ContextVar[_AcceptedWorkScope | None] = ContextVar(
            f"ai_lab_accepted_work_{id(self)}", default=None
        )

    def ensure_accepting_work(self) -> None:
        """Apply SP-007 FailureInfo semantics to new work admission."""
        if self._owns_current_scope():
            return
        self._check_lifecycle()

    @contextmanager
    def admit(self) -> Iterator[None]:
        """Check once at the outer boundary and preserve accepted work downstream."""
        if self._owns_current_scope():
            yield
            return

        self._check_lifecycle()
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("Work admission requires a running asyncio task")
        token = self._accepted_scope.set(_AcceptedWorkScope(owner=task))
        try:
            yield
        finally:
            self._accepted_scope.reset(token)

    def spawn_accepted_task(
        self,
        coroutine: Coroutine[Any, Any, T],
        *,
        name: str | None = None,
    ) -> asyncio.Task[T]:
        """Propagate capability only to an explicitly owned continuation task."""
        if not self._owns_current_scope():
            coroutine.close()
            raise RuntimeError("Accepted task spawning requires an active work scope")

        async def run_in_accepted_scope() -> T:
            task = asyncio.current_task()
            if task is None:
                raise RuntimeError("Accepted work continuation requires an asyncio task")
            token = self._accepted_scope.set(_AcceptedWorkScope(owner=task))
            try:
                return await coroutine
            finally:
                self._accepted_scope.reset(token)

        return asyncio.create_task(run_in_accepted_scope(), name=name)

    def _owns_current_scope(self) -> bool:
        scope = self._accepted_scope.get()
        if scope is None:
            return False
        try:
            return scope.owner is asyncio.current_task()
        except RuntimeError:
            return False

    def _check_lifecycle(self) -> None:
        state = self._lifecycle.state
        if state == SystemLifecycleState.READY:
            return
        code_map = {
            SystemLifecycleState.CREATED: "system.not_ready",
            SystemLifecycleState.STARTING: "system.not_ready",
            SystemLifecycleState.DRAINING: "system.draining",
            SystemLifecycleState.STOPPED: "system.stopped",
            SystemLifecycleState.FAILED: "system.failed",
        }
        raise FailureException(FailureInfo(
            code=code_map.get(state, "system.not_ready"),
            category=ErrorCategory.UNAVAILABLE,
            message="AI-Lab system is not accepting new work",
            component="system.lifecycle",
            operation="admit_request",
            retryable=True,
        ))
