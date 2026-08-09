"""Canonical, transport-neutral trusted interaction domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.errors import FailureInfo


class LifecycleState(StrEnum):
    REQUESTED = "REQUESTED"
    PREVIEWED = "PREVIEWED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class ResolutionPhase(StrEnum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVING = "RESOLVING"
    RESOLVED = "RESOLVED"


class ExecutionStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ACCEPTED = "ACCEPTED"
    ATTEMPTED = "ATTEMPTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"


class VerificationStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"


class RecoveryStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"


class PreviewStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    CONFIRMED = "CONFIRMED"


class Interaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    interaction_id: str
    tenant_id: str
    workspace_id: str
    namespace: str
    actor_id: str
    request_id: str
    trace_id: str
    operation: str
    risk_level: str
    policy_reference: str
    lifecycle_state: LifecycleState = LifecycleState.REQUESTED
    resolution_phase: ResolutionPhase = ResolutionPhase.UNRESOLVED
    execution_status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED
    recovery_status: RecoveryStatus = RecoveryStatus.NOT_REQUIRED
    revision: int = 1
    current_preview_id: str | None = None
    current_confirmation_id: str | None = None
    current_approval_id: str | None = None
    current_execution_id: str | None = None
    verified_result_id: str | None = None
    recovery_id: str | None = None
    canonical_object_id: str | None = None
    safe_summary: str = ""
    failure: FailureInfo | None = None
    correlation: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Preview(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_id: str
    interaction_id: str
    tenant_id: str
    workspace_id: str
    namespace: str
    actor_id: str
    operation: str
    policy_reference: str
    risk_level: str
    preview_revision: int
    normalized_parameters: dict[str, Any]
    payload_digest: str
    target_object_id: str | None = None
    target_revision: int | None = None
    mutation_summary: str
    expected_external_effects: tuple[str, ...] = ()
    requires_confirmation: bool = True
    requires_approval: bool = False
    canonical_commit_required: bool = True
    status: PreviewStatus = PreviewStatus.ACTIVE
    created_at: datetime
    expires_at: datetime


class Confirmation(BaseModel):
    model_config = ConfigDict(frozen=True)

    confirmation_id: str
    interaction_id: str
    preview_id: str
    preview_revision: int
    tenant_id: str
    workspace_id: str
    namespace: str
    actor_id: str
    policy_reference: str
    created_at: datetime
    expires_at: datetime


class Approval(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval_id: str
    interaction_id: str
    preview_id: str
    preview_revision: int
    tenant_id: str
    workspace_id: str
    namespace: str
    approver_id: str
    approver_role: str
    policy_reference: str
    created_at: datetime
    expires_at: datetime


class Execution(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    interaction_id: str
    tenant_id: str
    workspace_id: str
    namespace: str
    actor_id: str
    attempt: int
    idempotency_key: str
    executor_type: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime | None = None
    external_reference: str | None = None
    evidence_digest: str | None = None
    failure: FailureInfo | None = None


class VerifiedResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verified_result_id: str
    interaction_id: str
    execution_id: str
    tenant_id: str
    workspace_id: str
    namespace: str
    verification_method: str
    outcome: str
    verified_at: datetime
    canonical_object_id: str | None = None
    canonical_revision: int | None = None
    canonical_commit_succeeded: bool = False
    external_reference: str | None = None
    evidence_digest: str


class Recovery(BaseModel):
    model_config = ConfigDict(frozen=True)

    recovery_id: str
    interaction_id: str
    tenant_id: str
    workspace_id: str
    namespace: str
    actor_id: str
    status: RecoveryStatus
    reason: str
    evidence_digest: str | None = None
    created_at: datetime
    updated_at: datetime


class AuditEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    audit_id: str
    interaction_id: str
    tenant_id: str
    workspace_id: str
    namespace: str
    actor_id: str
    request_id: str
    trace_id: str
    operation: str
    risk_level: str
    event_type: str
    from_state: LifecycleState | None = None
    to_state: LifecycleState
    revision: int
    idempotency_key: str
    references: dict[str, str] = Field(default_factory=dict)
    failure: FailureInfo | None = None
    occurred_at: datetime


class InteractionStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    interaction: Interaction
    preview: Preview | None = None
    confirmation: Confirmation | None = None
    approval: Approval | None = None
    execution: Execution | None = None
    verified_result: VerifiedResult | None = None
    recovery: Recovery | None = None


class InteractionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    interaction_id: str
    lifecycle_state: LifecycleState
    revision: int
    canonical_object_id: str | None
    safe_summary: str
    available_operations: tuple[str, ...]
    preview_status: PreviewStatus | None
    confirmation_id: str | None
    execution_status: ExecutionStatus
    verification_status: VerificationStatus
    verified_result_id: str | None
    recovery_status: RecoveryStatus
    failure: FailureInfo | None


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    interaction_id: str
    execution_id: str
    operation: str
    normalized_parameters: dict[str, Any]
    idempotency_key: str
    trace_id: str


class ExecutionObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ExecutionStatus
    executor_type: str = "reference"
    external_reference: str | None = None
    evidence_digest: str | None = None
    failure: FailureInfo | None = None


class VerificationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    interaction_id: str
    execution_id: str
    external_reference: str | None
    trace_id: str


class VerificationObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: VerificationStatus
    method: str = "reference"
    outcome: str = ""
    evidence_digest: str = ""
    canonical_object_id: str | None = None
    canonical_revision: int | None = None
    canonical_commit_succeeded: bool = False
    external_reference: str | None = None
    failure: FailureInfo | None = None
