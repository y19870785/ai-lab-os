"""Deterministic reference ports for trusted interaction tests."""

from __future__ import annotations

from collections import deque
from datetime import timedelta

from core.interaction import (
    ApprovalAuthorizationEvidence,
    ApprovalAuthorizationRequest,
    CanonicalCommitEvidence,
    CanonicalCommitRequest,
    ExecutionObservation,
    ExecutionRequest,
    ExecutionStatus,
    VerificationObservation,
    VerificationRequest,
    VerificationStatus,
)
from tests.helpers.clock import MutableClock


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


class ReferenceCanonicalCommitAuthority:
    def __init__(self, clock: MutableClock) -> None:
        self._clock = clock
        self.requests: list[CanonicalCommitRequest] = []

    async def record(self, request: CanonicalCommitRequest) -> CanonicalCommitEvidence:
        self.requests.append(request)
        return CanonicalCommitEvidence(
            canonical_commit_evidence_id=f"cce_{len(self.requests)}",
            interaction_id=request.interaction_id,
            execution_id=request.execution_id,
            preview_id=request.preview_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            namespace=request.namespace,
            policy_reference=request.policy_reference,
            commit_required=True,
            outcome="COMMITTED",
            canonical_object_id=request.target_object_id or "object-1",
            canonical_revision=(request.target_revision or 1) + 1,
            evidence_digest=f"canonical-digest-{len(self.requests)}",
            committed_at=self._clock.now(),
        )


class ReferenceApprovalAuthority:
    def __init__(
        self,
        clock: MutableClock,
        valid_evidence: str = "trusted-approval",
        authorized_role: str = "owner",
    ) -> None:
        self._clock = clock
        self._valid_evidence = valid_evidence
        self._authorized_role = authorized_role
        self.requests: list[ApprovalAuthorizationRequest] = []

    async def authorize(
        self, request: ApprovalAuthorizationRequest, presented_evidence: str
    ) -> ApprovalAuthorizationEvidence | None:
        self.requests.append(request)
        if presented_evidence != self._valid_evidence:
            return None
        return ApprovalAuthorizationEvidence(
            authority_evidence_id=f"aae_{len(self.requests)}",
            interaction_id=request.interaction_id,
            preview_id=request.preview_id,
            preview_revision=request.preview_revision,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            namespace=request.namespace,
            approver_id=request.approver_id,
            authorized_role=self._authorized_role,
            policy_reference=request.policy_reference,
            evidence_digest=f"approval-digest-{len(self.requests)}",
            expires_at=self._clock.now() + timedelta(days=1),
        )


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
        external_reference=reference,
    )
