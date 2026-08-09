"""Deterministic reference ports for trusted interaction tests."""

from __future__ import annotations

from collections import deque

from core.interaction import (
    ExecutionObservation,
    ExecutionRequest,
    ExecutionStatus,
    VerificationObservation,
    VerificationRequest,
    VerificationStatus,
)


class ReferenceExecutionPort:
    def __init__(self, *observations: ExecutionObservation | Exception) -> None:
        self._observations = deque(observations)
        self.requests: list[ExecutionRequest] = []

    async def execute(self, request: ExecutionRequest) -> ExecutionObservation:
        self.requests.append(request)
        observation = self._observations.popleft()
        if isinstance(observation, Exception):
            raise observation
        return observation


class ReferenceVerificationPort:
    def __init__(self, *observations: VerificationObservation | Exception) -> None:
        self._observations = deque(observations)
        self.requests: list[VerificationRequest] = []

    async def verify(self, request: VerificationRequest) -> VerificationObservation:
        self.requests.append(request)
        observation = self._observations.popleft()
        if isinstance(observation, Exception):
            raise observation
        return observation


def acknowledged(reference: str = "external-1") -> ExecutionObservation:
    return ExecutionObservation(
        status=ExecutionStatus.ACKNOWLEDGED,
        executor_type="reference",
        external_reference=reference,
        evidence_digest="ack-digest",
    )


def uncertain() -> ExecutionObservation:
    return ExecutionObservation(
        status=ExecutionStatus.UNCERTAIN,
        executor_type="reference",
        evidence_digest="uncertain-digest",
    )


def verified(reference: str = "external-1") -> VerificationObservation:
    return VerificationObservation(
        status=VerificationStatus.VERIFIED,
        method="read-after-write",
        outcome="business mutation observed",
        evidence_digest="verified-digest",
        canonical_object_id="object-1",
        canonical_revision=2,
        canonical_commit_succeeded=True,
        external_reference=reference,
    )
