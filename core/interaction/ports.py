"""Minimal execution and verification ports for trusted interactions."""

from __future__ import annotations

from typing import Protocol

from core.interaction.models import (
    ExecutionObservation,
    ExecutionRequest,
    VerificationObservation,
    VerificationRequest,
)


class ExecutionPort(Protocol):
    async def execute(self, request: ExecutionRequest) -> ExecutionObservation: ...


class VerificationPort(Protocol):
    async def verify(self, request: VerificationRequest) -> VerificationObservation: ...


class DisabledExecutionPort:
    """Production-safe default: never performs an external side effect."""

    async def execute(self, request: ExecutionRequest) -> ExecutionObservation:
        raise RuntimeError("Trusted interaction execution adapter is not configured")


class DisabledVerificationPort:
    """Production-safe default: never fabricates verification evidence."""

    async def verify(self, request: VerificationRequest) -> VerificationObservation:
        raise RuntimeError("Trusted interaction verification adapter is not configured")
