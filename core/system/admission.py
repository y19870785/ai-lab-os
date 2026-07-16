"""Internal work admission contract backed by the system lifecycle."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from typing import Iterator, Protocol

from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.lifecycle import LifecycleStateMachine, SystemLifecycleState


class WorkAdmission(Protocol):
    """Narrow dependency used by canonical work entrypoints."""

    def ensure_accepting_work(self) -> None:
        """Reject work unless the shared lifecycle permits admission."""

    def admit(self) -> AbstractContextManager[None]:
        """Accept one outer work item while allowing nested downstream calls."""


class WorkAdmissionGate:
    """Synchronous admission gate with accepted-work context propagation."""

    def __init__(self, lifecycle: LifecycleStateMachine) -> None:
        self._lifecycle = lifecycle
        self._accepted_depth: ContextVar[int] = ContextVar(
            f"ai_lab_accepted_work_{id(self)}", default=0
        )

    def ensure_accepting_work(self) -> None:
        """Apply SP-007 FailureInfo semantics to new work admission."""
        if self._accepted_depth.get() > 0:
            return
        self._check_lifecycle()

    @contextmanager
    def admit(self) -> Iterator[None]:
        """Check once at the outer boundary and preserve accepted work downstream."""
        depth = self._accepted_depth.get()
        if depth > 0:
            token = self._accepted_depth.set(depth + 1)
            try:
                yield
            finally:
                self._accepted_depth.reset(token)
            return

        self._check_lifecycle()
        token = self._accepted_depth.set(1)
        try:
            yield
        finally:
            self._accepted_depth.reset(token)

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
