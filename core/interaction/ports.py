"""Minimal execution and verification ports for trusted interactions."""

from __future__ import annotations

from typing import Protocol

from core.interaction.models import (
    ApprovalAuthorizationEvidence,
    ApprovalAuthorizationRequest,
    CanonicalCommitEvidence,
    CanonicalCommitRequest,
    ExecutionObservation,
    ExecutionRequest,
    VerificationObservation,
    VerificationRequest,
)


class ExecutionPort(Protocol):
    async def execute(self, request: ExecutionRequest) -> ExecutionObservation: ...


class VerificationPort(Protocol):
    async def verify(self, request: VerificationRequest) -> VerificationObservation: ...


class CanonicalCommitAuthority(Protocol):
    async def record(self, request: CanonicalCommitRequest) -> CanonicalCommitEvidence: ...


class ApprovalAuthority(Protocol):
    async def authorize(
        self, request: ApprovalAuthorizationRequest, presented_evidence: str
    ) -> ApprovalAuthorizationEvidence | None: ...


class DisabledExecutionPort:
    """Production-safe default: never performs an external side effect."""

    async def execute(self, request: ExecutionRequest) -> ExecutionObservation:
        raise RuntimeError("Trusted interaction execution adapter is not configured")


class DisabledVerificationPort:
    """Production-safe default: never fabricates verification evidence."""

    async def verify(self, request: VerificationRequest) -> VerificationObservation:
        raise RuntimeError("Trusted interaction verification adapter is not configured")


class DisabledCanonicalCommitAuthority:
    """Fail closed until an AI-Lab-controlled canonical committer is injected."""

    async def record(self, request: CanonicalCommitRequest) -> CanonicalCommitEvidence:
        raise RuntimeError("Canonical commit authority is not configured")


class DisabledApprovalAuthority:
    """Caller-supplied roles never authorize approval without trusted evidence."""

    async def authorize(
        self, request: ApprovalAuthorizationRequest, presented_evidence: str
    ) -> ApprovalAuthorizationEvidence | None:
        return None
