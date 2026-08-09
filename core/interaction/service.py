"""Application service for the canonical trusted interaction lifecycle."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from core.clock import Clock
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.interaction.models import (
    Approval,
    ApprovalAuthorizationRequest,
    AuditEvidence,
    CanonicalCommitEvidence,
    CanonicalCommitRequest,
    Confirmation,
    Execution,
    ExecutionRequest,
    ExecutionStatus,
    Interaction,
    InteractionStatus,
    InteractionView,
    LifecycleState,
    Preview,
    PreviewStatus,
    Recovery,
    RecoveryStatus,
    ResolutionPhase,
    VerificationRequest,
    VerificationStatus,
    VerifiedResult,
)
from core.interaction.ports import (
    ApprovalAuthority,
    CanonicalCommitAuthority,
    DisabledApprovalAuthority,
    DisabledCanonicalCommitAuthority,
    ExecutionPort,
    VerificationPort,
)
from core.interaction.repository import SQLiteInteractionRepository
from core.workspace.models import WorkspaceKey

TERMINAL_STATES = {
    LifecycleState.SUCCEEDED,
    LifecycleState.FAILED,
    LifecycleState.CANCELLED,
    LifecycleState.EXPIRED,
}


class InteractionService:
    """The only application boundary allowed to mutate canonical interactions."""

    def __init__(
        self,
        repository: SQLiteInteractionRepository,
        clock: Clock,
        execution_port: ExecutionPort,
        verification_port: VerificationPort,
        canonical_commit_authority: CanonicalCommitAuthority | None = None,
        approval_authority: ApprovalAuthority | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._execution_port = execution_port
        self._verification_port = verification_port
        self._canonical_commit_authority = (
            canonical_commit_authority or DisabledCanonicalCommitAuthority()
        )
        self._approval_authority = approval_authority or DisabledApprovalAuthority()

    async def initialize(self) -> None:
        await self._repository.initialize()

    async def close(self) -> None:
        """Connection lifecycle remains owned by DatabaseManager."""

    @staticmethod
    def _scope(workspace: WorkspaceKey, actor_id: str) -> tuple[str, str, str]:
        values = {
            "tenant_id": workspace.tenant_id.strip(),
            "workspace_id": workspace.workspace_id.strip(),
            "namespace": workspace.namespace.strip(),
            "workspace_actor": workspace.user_id.strip(),
            "actor_id": actor_id.strip(),
        }
        missing = [key for key, value in values.items() if not value]
        if missing:
            InteractionService._fail(
                "interaction.identity_workspace_unresolved",
                ErrorCategory.PERMISSION_DENIED,
                "identity_workspace",
                "Explicit WorkspaceKey and actor are required",
                trace_id=workspace.trace_id,
                details={"missing": missing},
            )
        if values["workspace_actor"] != values["actor_id"]:
            InteractionService._fail(
                "interaction.actor_mismatch",
                ErrorCategory.PERMISSION_DENIED,
                "identity_workspace",
                "Actor does not match the authoritative WorkspaceKey principal",
                trace_id=workspace.trace_id,
            )
        return values["tenant_id"], values["workspace_id"], values["namespace"]

    @staticmethod
    def _digest(payload: Any) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode()).hexdigest()

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _fail(
        code: str,
        category: ErrorCategory,
        operation: str,
        message: str,
        *,
        trace_id: str = "",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        raise FailureException(
            FailureInfo(
                code=code,
                category=category,
                message=message,
                component="trusted_interaction",
                operation=operation,
                retryable=retryable,
                trace_id=trace_id,
                details=details or {},
            )
        )

    def _audit(
        self,
        interaction: Interaction,
        *,
        event_type: str,
        from_state: LifecycleState | None,
        idempotency_key: str,
        references: dict[str, str] | None = None,
        failure: FailureInfo | None = None,
    ) -> AuditEvidence:
        return AuditEvidence(
            audit_id=self._id("aud"),
            interaction_id=interaction.interaction_id,
            tenant_id=interaction.tenant_id,
            workspace_id=interaction.workspace_id,
            namespace=interaction.namespace,
            actor_id=interaction.actor_id,
            request_id=interaction.request_id,
            trace_id=interaction.trace_id,
            operation=interaction.operation,
            risk_level=interaction.risk_level,
            event_type=event_type,
            from_state=from_state,
            to_state=interaction.lifecycle_state,
            revision=interaction.revision,
            idempotency_key=idempotency_key,
            references=references or {},
            failure=failure,
            occurred_at=self._clock.now(),
        )

    async def _idempotent(
        self,
        scope: tuple[str, str, str],
        operation: str,
        key: str,
        digest: str,
        trace_id: str,
    ) -> Interaction | None:
        if not key.strip():
            self._fail(
                "interaction.idempotency_key_missing", ErrorCategory.VALIDATION,
                operation, "Idempotency key is required", trace_id=trace_id,
            )
        try:
            return await self._repository.idempotent_result(scope, operation, key, digest)
        except ValueError as exc:
            self._fail(
                "interaction.idempotency_conflict", ErrorCategory.CONFLICT,
                operation, str(exc), trace_id=trace_id,
            )

    async def create_interaction(
        self,
        *,
        workspace: WorkspaceKey,
        actor_id: str,
        operation: str,
        risk_level: str,
        policy_reference: str,
        request_id: str,
        trace_id: str,
        idempotency_key: str,
        safe_summary: str = "",
        correlation: dict[str, str] | None = None,
    ) -> Interaction:
        scope = self._scope(workspace, actor_id)
        required = {"operation": operation, "policy_reference": policy_reference,
                    "request_id": request_id, "trace_id": trace_id}
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            self._fail(
                "interaction.request_invalid", ErrorCategory.VALIDATION, "create",
                "Canonical request correlations and policy are required",
                trace_id=trace_id, details={"missing": missing},
            )
        payload = {**required, "risk_level": risk_level, "actor_id": actor_id,
                   "scope": scope, "safe_summary": safe_summary,
                   "correlation": correlation or {}}
        digest = self._digest(payload)
        if not idempotency_key.strip():
            self._fail(
                "interaction.idempotency_key_missing", ErrorCategory.VALIDATION,
                "create", "Idempotency key is required", trace_id=trace_id,
            )
        now = self._clock.now()
        interaction = Interaction(
            interaction_id=self._id("int"), tenant_id=scope[0], workspace_id=scope[1],
            namespace=scope[2], actor_id=actor_id, request_id=request_id,
            trace_id=trace_id, operation=operation, risk_level=risk_level,
            policy_reference=policy_reference, safe_summary=safe_summary,
            correlation=correlation or {}, created_at=now, updated_at=now,
        )
        try:
            return await self._repository.create(
                interaction,
                self._audit(interaction, event_type="interaction.requested",
                            from_state=None, idempotency_key=idempotency_key),
                operation="create", idempotency_key=idempotency_key,
                payload_digest=digest,
            )
        except ValueError as exc:
            self._fail(
                "interaction.idempotency_conflict", ErrorCategory.CONFLICT,
                "create", str(exc), trace_id=trace_id,
            )

    async def preview(
        self,
        *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        expected_revision: int, normalized_parameters: dict[str, Any],
        mutation_summary: str, expires_in: timedelta, idempotency_key: str,
        target_object_id: str | None = None, target_revision: int | None = None,
        expected_external_effects: tuple[str, ...] = (),
        requires_confirmation: bool = True, requires_approval: bool = False,
        canonical_commit_required: bool = True,
    ) -> Preview:
        scope = self._scope(workspace, actor_id)
        digest = self._digest({"interaction_id": interaction_id,
                               "expected_revision": expected_revision,
                               "parameters": normalized_parameters,
                               "mutation_summary": mutation_summary,
                               "expires_in": expires_in.total_seconds(),
                               "target_object_id": target_object_id,
                               "target_revision": target_revision,
                               "effects": expected_external_effects,
                               "requires_confirmation": requires_confirmation,
                               "requires_approval": requires_approval,
                               "canonical_commit_required": canonical_commit_required})
        prior = await self._idempotent(scope, "preview", idempotency_key, digest, workspace.trace_id)
        if prior is not None:
            fact = await self._repository.fact(prior.interaction_id, Preview, prior.current_preview_id)
            assert fact is not None
            return fact
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.actor_id != actor_id:
            self._fail("interaction.actor_mismatch", ErrorCategory.PERMISSION_DENIED,
                       "preview", "Actor mismatch", trace_id=current.trace_id)
        if current.revision != expected_revision:
            self._fail("interaction.revision_conflict", ErrorCategory.CONFLICT,
                       "preview", "Interaction revision is stale", trace_id=current.trace_id)
        if current.lifecycle_state not in {
            LifecycleState.REQUESTED, LifecycleState.PREVIEWED,
            LifecycleState.AWAITING_CONFIRMATION,
        }:
            self._invalid_state(current, "preview")
        now = self._clock.now()
        if expires_in.total_seconds() <= 0:
            self._fail("interaction.preview_expiry_invalid", ErrorCategory.VALIDATION,
                       "preview", "Preview expiry must be in the future", trace_id=current.trace_id)
        old_preview = await self._repository.fact(interaction_id, Preview, current.current_preview_id)
        facts: list[Preview] = []
        if old_preview is not None:
            facts.append(old_preview.model_copy(update={"status": PreviewStatus.SUPERSEDED}))
        preview_revision = 1 if old_preview is None else old_preview.preview_revision + 1
        preview = Preview(
            preview_id=self._id("prv"), interaction_id=interaction_id,
            tenant_id=current.tenant_id, workspace_id=current.workspace_id,
            namespace=current.namespace, actor_id=actor_id, operation=current.operation,
            policy_reference=current.policy_reference, risk_level=current.risk_level,
            preview_revision=preview_revision,
            normalized_parameters=normalized_parameters,
            payload_digest=self._digest(normalized_parameters),
            target_object_id=target_object_id, target_revision=target_revision,
            mutation_summary=mutation_summary,
            expected_external_effects=expected_external_effects,
            requires_confirmation=requires_confirmation,
            requires_approval=requires_approval,
            canonical_commit_required=canonical_commit_required,
            created_at=now, expires_at=now + expires_in,
        )
        facts.append(preview)
        final_state = (
            LifecycleState.AWAITING_CONFIRMATION
            if requires_confirmation or requires_approval else LifecycleState.AUTHORIZED
        )
        updated = current.model_copy(update={
            "lifecycle_state": final_state,
            "resolution_phase": ResolutionPhase.RESOLVED,
            "revision": current.revision + 1,
            "current_preview_id": preview.preview_id,
            "current_confirmation_id": None,
            "current_approval_id": None,
            "canonical_object_id": target_object_id,
            "updated_at": now,
        })
        audits = [
            self._audit(
                updated.model_copy(update={
                    "lifecycle_state": current.lifecycle_state,
                    "resolution_phase": ResolutionPhase.RESOLVING,
                }),
                event_type="interaction.resolution_started",
                from_state=current.lifecycle_state,
                idempotency_key=idempotency_key,
                references={
                    "from_resolution": current.resolution_phase.value,
                    "to_resolution": ResolutionPhase.RESOLVING.value,
                },
            ),
            self._audit(
                updated.model_copy(update={"lifecycle_state": current.lifecycle_state}),
                event_type="interaction.resolved",
                from_state=current.lifecycle_state,
                idempotency_key=idempotency_key,
                references={
                    "from_resolution": ResolutionPhase.RESOLVING.value,
                    "to_resolution": ResolutionPhase.RESOLVED.value,
                },
            ),
            self._audit(updated.model_copy(update={"lifecycle_state": LifecycleState.PREVIEWED}),
                        event_type="interaction.previewed", from_state=current.lifecycle_state,
                        idempotency_key=idempotency_key,
                        references={"preview_id": preview.preview_id}),
            self._audit(updated, event_type="interaction.awaiting_confirmation"
                        if final_state == LifecycleState.AWAITING_CONFIRMATION
                        else "interaction.authorized",
                        from_state=LifecycleState.PREVIEWED,
                        idempotency_key=idempotency_key,
                        references={"preview_id": preview.preview_id}),
        ]
        await self._transition(updated, current.revision, facts, audits, "preview",
                               idempotency_key, digest)
        return preview

    async def confirm(
        self, *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        preview_id: str, preview_revision: int, expected_revision: int,
        idempotency_key: str, expires_in: timedelta = timedelta(minutes=15),
    ) -> Confirmation:
        scope = self._scope(workspace, actor_id)
        digest = self._digest({
            "interaction_id": interaction_id,
            "preview_id": preview_id,
            "preview_revision": preview_revision,
            "expected_revision": expected_revision,
            "actor_id": actor_id,
            "workspace": scope,
            "expires_in": expires_in.total_seconds(),
        })
        prior = await self._idempotent(scope, "confirm", idempotency_key, digest, workspace.trace_id)
        if prior is not None:
            fact = await self._repository.fact(prior.interaction_id, Confirmation, prior.current_confirmation_id)
            assert fact is not None
            return fact
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.revision != expected_revision:
            self._fail("interaction.confirmation_conflict", ErrorCategory.CONFLICT,
                       "confirm", "Interaction revision is stale", trace_id=current.trace_id)
        if current.lifecycle_state != LifecycleState.AWAITING_CONFIRMATION:
            self._invalid_state(current, "confirm")
        preview = await self._repository.fact(interaction_id, Preview, preview_id)
        now = self._clock.now()
        if (preview is None or preview.status != PreviewStatus.ACTIVE
                or preview.preview_revision != preview_revision
                or preview.preview_id != current.current_preview_id):
            self._fail("interaction.preview_stale", ErrorCategory.CONFLICT,
                       "confirm", "Preview is stale or superseded", trace_id=current.trace_id)
        if preview.actor_id != actor_id or preview.policy_reference != current.policy_reference:
            self._fail("interaction.confirmation_actor_mismatch", ErrorCategory.PERMISSION_DENIED,
                       "confirm", "Confirmation principal or policy does not match Preview",
                       trace_id=current.trace_id)
        if now >= preview.expires_at:
            self._fail("interaction.preview_expired", ErrorCategory.CONFLICT,
                       "confirm", "Preview has expired", trace_id=current.trace_id)
        if expires_in.total_seconds() <= 0:
            self._fail("interaction.confirmation_expiry_invalid", ErrorCategory.VALIDATION,
                       "confirm", "Confirmation expiry must be in the future",
                       trace_id=current.trace_id)
        confirmation = Confirmation(
            confirmation_id=self._id("cnf"), interaction_id=interaction_id,
            preview_id=preview_id, preview_revision=preview_revision,
            tenant_id=current.tenant_id, workspace_id=current.workspace_id,
            namespace=current.namespace, actor_id=actor_id,
            policy_reference=current.policy_reference, created_at=now,
            expires_at=min(preview.expires_at, now + expires_in),
        )
        updated_preview = preview.model_copy(update={"status": PreviewStatus.CONFIRMED})
        next_state = (LifecycleState.AWAITING_CONFIRMATION
                      if preview.requires_approval else LifecycleState.AUTHORIZED)
        updated = current.model_copy(update={
            "lifecycle_state": next_state,
            "revision": current.revision + 1,
            "current_confirmation_id": confirmation.confirmation_id,
            "updated_at": now,
        })
        audit = self._audit(updated, event_type="interaction.confirmed",
                            from_state=current.lifecycle_state,
                            idempotency_key=idempotency_key,
                            references={"preview_id": preview_id,
                                        "confirmation_id": confirmation.confirmation_id})
        await self._transition(updated, current.revision, [updated_preview, confirmation],
                               [audit], "confirm", idempotency_key, digest)
        return confirmation

    async def approve(
        self, *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        preview_id: str, preview_revision: int, expected_revision: int,
        approver_role: str, idempotency_key: str,
        authority_evidence: str | None = None,
        expires_in: timedelta = timedelta(minutes=15),
    ) -> Approval:
        scope = self._scope(workspace, actor_id)
        digest = self._digest({
            "interaction_id": interaction_id, "preview_id": preview_id,
            "preview_revision": preview_revision, "expected_revision": expected_revision,
            "approver_id": actor_id, "approver_role": approver_role,
            "authority_evidence_digest": self._digest(authority_evidence or ""),
            "expires_in": expires_in.total_seconds(),
        })
        prior = await self._idempotent(scope, "approve", idempotency_key, digest,
                                       workspace.trace_id)
        if prior is not None:
            fact = await self._repository.fact(prior.interaction_id, Approval,
                                               prior.current_approval_id)
            assert fact is not None
            return fact
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.revision != expected_revision:
            self._fail("interaction.approval_conflict", ErrorCategory.CONFLICT,
                       "approve", "Interaction revision is stale", trace_id=current.trace_id)
        if (current.lifecycle_state != LifecycleState.AWAITING_CONFIRMATION
                or current.current_confirmation_id is None):
            self._invalid_state(current, "approve")
        preview = await self._repository.fact(interaction_id, Preview, preview_id)
        confirmation = await self._repository.fact(
            interaction_id, Confirmation, current.current_confirmation_id
        )
        now = self._clock.now()
        if (preview is None or confirmation is None or not preview.requires_approval
                or preview.preview_id != current.current_preview_id
                or preview.preview_revision != preview_revision
                or now >= preview.expires_at or now >= confirmation.expires_at):
            self._fail("interaction.approval_conflict", ErrorCategory.CONFLICT,
                       "approve", "Approval does not match an active confirmed Preview",
                       trace_id=current.trace_id)
        if not approver_role.strip() or expires_in.total_seconds() <= 0:
            self._fail("interaction.approval_invalid", ErrorCategory.VALIDATION,
                       "approve", "Approver role and future expiry are required",
                       trace_id=current.trace_id)
        if not authority_evidence:
            self._fail(
                "interaction.approval_authority_missing",
                ErrorCategory.PERMISSION_DENIED,
                "approve",
                "AI-Lab-controlled approval authority evidence is required",
                trace_id=current.trace_id,
            )
        authority_request = ApprovalAuthorizationRequest(
            interaction_id=interaction_id,
            preview_id=preview_id,
            preview_revision=preview_revision,
            tenant_id=current.tenant_id,
            workspace_id=current.workspace_id,
            namespace=current.namespace,
            approver_id=actor_id,
            requested_role=approver_role,
            policy_reference=current.policy_reference,
            trace_id=current.trace_id,
        )
        try:
            authority = await self._approval_authority.authorize(
                authority_request, authority_evidence
            )
        except Exception as exc:  # noqa: BLE001 - trusted authority boundary
            self._fail(
                "interaction.approval_authority_invalid",
                ErrorCategory.PERMISSION_DENIED,
                "approve",
                f"Approval authority rejected the evidence: {exc}",
                trace_id=current.trace_id,
            )
        if authority is None or not self._approval_authority_matches(
            authority_request, authority, now
        ):
            self._fail(
                "interaction.approval_authority_invalid",
                ErrorCategory.PERMISSION_DENIED,
                "approve",
                "Approval authority evidence is invalid or does not match the Preview",
                trace_id=current.trace_id,
            )
        approval = Approval(
            approval_id=self._id("apr"), interaction_id=interaction_id,
            preview_id=preview_id, preview_revision=preview_revision,
            tenant_id=current.tenant_id, workspace_id=current.workspace_id,
            namespace=current.namespace, approver_id=actor_id,
            approver_role=authority.authorized_role,
            authority_evidence_id=authority.authority_evidence_id,
            authority_evidence_digest=authority.evidence_digest,
            policy_reference=current.policy_reference,
            created_at=now,
            expires_at=min(preview.expires_at, authority.expires_at, now + expires_in),
        )
        updated = current.model_copy(update={
            "lifecycle_state": LifecycleState.AUTHORIZED,
            "current_approval_id": approval.approval_id,
            "revision": current.revision + 1, "updated_at": now,
        })
        await self._transition(
            updated, current.revision, [approval],
            [self._audit(updated, event_type="interaction.approved",
                         from_state=current.lifecycle_state,
                         idempotency_key=idempotency_key,
                          references={"preview_id": preview_id,
                                      "approval_id": approval.approval_id,
                                      "authority_evidence_id":
                                          approval.authority_evidence_id})],
            "approve", idempotency_key, digest,
        )
        return approval

    @staticmethod
    def _approval_authority_matches(request, evidence, now) -> bool:
        return (
            evidence.interaction_id == request.interaction_id
            and evidence.preview_id == request.preview_id
            and evidence.preview_revision == request.preview_revision
            and evidence.tenant_id == request.tenant_id
            and evidence.workspace_id == request.workspace_id
            and evidence.namespace == request.namespace
            and evidence.approver_id == request.approver_id
            and evidence.authorized_role == request.requested_role
            and evidence.policy_reference == request.policy_reference
            and bool(evidence.evidence_digest)
            and now < evidence.expires_at
        )

    async def cancel(
        self, *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        expected_revision: int, idempotency_key: str,
    ) -> Interaction:
        scope = self._scope(workspace, actor_id)
        digest = self._digest({"interaction_id": interaction_id,
                               "expected_revision": expected_revision})
        prior = await self._idempotent(scope, "cancel", idempotency_key, digest, workspace.trace_id)
        if prior is not None:
            return prior
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.revision != expected_revision:
            self._fail("interaction.revision_conflict", ErrorCategory.CONFLICT,
                       "cancel", "Interaction revision is stale", trace_id=current.trace_id)
        if current.lifecycle_state in TERMINAL_STATES:
            self._invalid_state(current, "cancel")
        if current.lifecycle_state in {
            LifecycleState.EXECUTING, LifecycleState.VERIFYING,
            LifecycleState.RECOVERY_REQUIRED,
        } or current.execution_status in {
            ExecutionStatus.ATTEMPTED, ExecutionStatus.ACKNOWLEDGED,
            ExecutionStatus.COMPLETED, ExecutionStatus.UNCERTAIN,
        }:
            self._fail("interaction.cancel_outcome_uncertain", ErrorCategory.CONFLICT,
                       "cancel", "Execution may have side effects; verification or recovery is required",
                       trace_id=current.trace_id)
        now = self._clock.now()
        facts: list[Preview] = []
        preview = await self._repository.fact(interaction_id, Preview, current.current_preview_id)
        if preview is not None and preview.status == PreviewStatus.ACTIVE:
            facts.append(preview.model_copy(update={"status": PreviewStatus.SUPERSEDED}))
        updated = current.model_copy(update={"lifecycle_state": LifecycleState.CANCELLED,
                                             "revision": current.revision + 1,
                                             "updated_at": now})
        await self._transition(updated, current.revision, facts,
                               [self._audit(updated, event_type="interaction.cancelled",
                                            from_state=current.lifecycle_state,
                                            idempotency_key=idempotency_key)],
                               "cancel", idempotency_key, digest)
        return updated

    async def expire_preview(
        self, *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        expected_revision: int, idempotency_key: str,
    ) -> Interaction:
        scope = self._scope(workspace, actor_id)
        digest = self._digest({"interaction_id": interaction_id,
                               "expected_revision": expected_revision})
        prior = await self._idempotent(scope, "expire", idempotency_key, digest,
                                       workspace.trace_id)
        if prior is not None:
            return prior
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.revision != expected_revision:
            self._fail("interaction.revision_conflict", ErrorCategory.CONFLICT,
                       "expire", "Interaction revision is stale", trace_id=current.trace_id)
        if current.lifecycle_state not in {LifecycleState.PREVIEWED,
                                            LifecycleState.AWAITING_CONFIRMATION}:
            self._invalid_state(current, "expire")
        preview = await self._repository.fact(interaction_id, Preview,
                                               current.current_preview_id)
        now = self._clock.now()
        if preview is None or now < preview.expires_at:
            self._fail("interaction.preview_not_expired", ErrorCategory.CONFLICT,
                       "expire", "Preview has not expired", trace_id=current.trace_id)
        expired = preview.model_copy(update={"status": PreviewStatus.EXPIRED})
        updated = current.model_copy(update={
            "lifecycle_state": LifecycleState.EXPIRED,
            "revision": current.revision + 1,
            "updated_at": now,
        })
        await self._transition(updated, current.revision, [expired],
                               [self._audit(updated, event_type="interaction.expired",
                                            from_state=current.lifecycle_state,
                                            idempotency_key=idempotency_key,
                                            references={"preview_id": preview.preview_id})],
                               "expire", idempotency_key, digest)
        return updated

    async def start_execution(
        self, *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        expected_revision: int, idempotency_key: str,
    ) -> InteractionStatus:
        scope = self._scope(workspace, actor_id)
        digest = self._digest({"interaction_id": interaction_id,
                               "expected_revision": expected_revision})
        prior = await self._idempotent(scope, "execute", idempotency_key, digest, workspace.trace_id)
        if prior is not None:
            return await self.status(workspace=workspace, actor_id=actor_id,
                                     interaction_id=interaction_id)
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.revision != expected_revision:
            self._fail("interaction.revision_conflict", ErrorCategory.CONFLICT,
                       "execute", "Interaction revision is stale", trace_id=current.trace_id)
        if current.lifecycle_state != LifecycleState.AUTHORIZED:
            self._invalid_state(current, "execute")
        preview = await self._repository.fact(interaction_id, Preview, current.current_preview_id)
        if preview is None:
            self._fail("interaction.preview_missing", ErrorCategory.CONFLICT,
                       "execute", "Authorized interaction has no canonical Preview",
                       trace_id=current.trace_id)
        now = self._clock.now()
        confirmation = await self._repository.fact(
            interaction_id, Confirmation, current.current_confirmation_id
        )
        approval = await self._repository.fact(interaction_id, Approval,
                                               current.current_approval_id)
        if preview.requires_confirmation and (
            confirmation is None or self._clock.now() >= confirmation.expires_at
        ):
            self._fail("interaction.confirmation_expired", ErrorCategory.CONFLICT,
                       "execute", "Canonical Confirmation is missing or expired",
                       trace_id=current.trace_id)
        if preview.requires_approval and (
            approval is None or self._clock.now() >= approval.expires_at
        ):
            self._fail("interaction.approval_expired", ErrorCategory.CONFLICT,
                       "execute", "Canonical Approval is missing or expired",
                       trace_id=current.trace_id)
        execution = Execution(
            execution_id=self._id("exe"), interaction_id=interaction_id,
            tenant_id=current.tenant_id, workspace_id=current.workspace_id,
            namespace=current.namespace, actor_id=actor_id, attempt=1,
            idempotency_key=idempotency_key, executor_type="pending",
            status=ExecutionStatus.ATTEMPTED, started_at=now,
        )
        executing = current.model_copy(update={
            "lifecycle_state": LifecycleState.EXECUTING,
            "execution_status": ExecutionStatus.ATTEMPTED,
            "verification_status": VerificationStatus.PENDING,
            "revision": current.revision + 1,
            "current_execution_id": execution.execution_id,
            "updated_at": now,
        })
        await self._transition(executing, current.revision, [execution],
                               [self._audit(executing, event_type="interaction.execution_started",
                                            from_state=current.lifecycle_state,
                                            idempotency_key=idempotency_key,
                                            references={"execution_id": execution.execution_id})],
                               "execute", idempotency_key, digest)
        try:
            observation = await self._execution_port.execute(ExecutionRequest(
                interaction_id=interaction_id, execution_id=execution.execution_id,
                operation=current.operation, normalized_parameters=preview.normalized_parameters,
                idempotency_key=idempotency_key, trace_id=current.trace_id,
            ))
        except Exception as exc:  # noqa: BLE001 - port uncertainty boundary
            failure = FailureInfo(
                code="interaction.execution_outcome_uncertain",
                category=ErrorCategory.TIMEOUT, message=str(exc),
                component="trusted_interaction", operation="execute",
                retryable=False, trace_id=current.trace_id,
            )
            observation_status = ExecutionStatus.UNCERTAIN
            observation_executor = "unavailable"
            external_reference = None
            evidence_digest = None
        else:
            failure = observation.failure
            observation_status = observation.status
            observation_executor = observation.executor_type
            external_reference = observation.external_reference
            evidence_digest = observation.evidence_digest
        finished = self._clock.now()
        execution = execution.model_copy(update={
            "status": observation_status, "executor_type": observation_executor,
            "external_reference": external_reference,
            "evidence_digest": evidence_digest, "failure": failure,
            "finished_at": finished,
        })
        result_facts: list[Execution | Recovery] = [execution]
        recovery_id = current.recovery_id
        if observation_status in {ExecutionStatus.REJECTED, ExecutionStatus.FAILED}:
            final_state = LifecycleState.FAILED
            verification_status = VerificationStatus.NOT_REQUIRED
            recovery_status = RecoveryStatus.NOT_REQUIRED
        elif observation_status == ExecutionStatus.UNCERTAIN:
            final_state = LifecycleState.RECOVERY_REQUIRED
            verification_status = VerificationStatus.UNCERTAIN
            recovery_status = RecoveryStatus.PENDING
            recovery = Recovery(
                recovery_id=self._id("rcv"), interaction_id=interaction_id,
                tenant_id=current.tenant_id, workspace_id=current.workspace_id,
                namespace=current.namespace, actor_id=actor_id,
                status=RecoveryStatus.PENDING,
                reason="interaction.execution_outcome_uncertain",
                evidence_digest=evidence_digest, created_at=finished, updated_at=finished,
            )
            recovery_id = recovery.recovery_id
            result_facts.append(recovery)
        else:
            final_state = LifecycleState.VERIFYING
            verification_status = VerificationStatus.PENDING
            recovery_status = RecoveryStatus.NOT_REQUIRED
        final = executing.model_copy(update={
            "lifecycle_state": final_state, "execution_status": observation_status,
            "verification_status": verification_status,
            "recovery_status": recovery_status,
            "recovery_id": recovery_id,
            "failure": failure, "revision": executing.revision + 1,
            "updated_at": finished,
        })
        await self._transition(final, executing.revision, result_facts,
                               [self._audit(final, event_type="interaction.execution_observed",
                                            from_state=executing.lifecycle_state,
                                            idempotency_key=idempotency_key,
                                            references={"execution_id": execution.execution_id,
                                                        "external_reference": external_reference or ""},
                                            failure=failure)],
                               "execute", idempotency_key, digest)
        return await self.status(workspace=workspace, actor_id=actor_id,
                                 interaction_id=interaction_id)

    async def verify(
        self, *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        expected_revision: int, idempotency_key: str,
        _idempotency_operation: str = "verify",
        _idempotency_digest: str | None = None,
    ) -> InteractionStatus:
        scope = self._scope(workspace, actor_id)
        digest = _idempotency_digest or self._digest({
            "interaction_id": interaction_id,
            "expected_revision": expected_revision,
        })
        prior = await self._idempotent(
            scope, _idempotency_operation, idempotency_key, digest, workspace.trace_id
        )
        if prior is not None:
            return await self.status(workspace=workspace, actor_id=actor_id,
                                     interaction_id=interaction_id)
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.revision != expected_revision:
            self._fail("interaction.revision_conflict", ErrorCategory.CONFLICT,
                       "verify", "Interaction revision is stale", trace_id=current.trace_id)
        if current.lifecycle_state not in {LifecycleState.VERIFYING,
                                            LifecycleState.RECOVERY_REQUIRED}:
            self._invalid_state(current, "verify")
        execution = await self._repository.fact(interaction_id, Execution,
                                                 current.current_execution_id)
        if execution is None:
            self._fail("interaction.execution_missing", ErrorCategory.CONFLICT,
                       "verify", "Canonical Execution is missing", trace_id=current.trace_id)
        try:
            observation = await self._verification_port.verify(VerificationRequest(
                interaction_id=interaction_id, execution_id=execution.execution_id,
                external_reference=execution.external_reference, trace_id=current.trace_id,
            ))
        except Exception as exc:  # noqa: BLE001 - verifier availability boundary
            failure = FailureInfo(
                code="interaction.verification_unavailable",
                category=ErrorCategory.UNAVAILABLE, message=str(exc),
                component="trusted_interaction", operation="verify",
                retryable=True, trace_id=current.trace_id,
            )
            observation = None
        else:
            failure = observation.failure
        preview = await self._repository.fact(
            interaction_id, Preview, current.current_preview_id
        )
        if preview is None:
            self._fail(
                "interaction.preview_missing", ErrorCategory.CONFLICT,
                "verify", "Canonical Preview is missing", trace_id=current.trace_id,
            )
        now = self._clock.now()
        facts: list[VerifiedResult | CanonicalCommitEvidence | Recovery] = []
        references = {"execution_id": execution.execution_id}
        if (observation is not None
                and observation.status == VerificationStatus.VERIFIED
                and observation.evidence_digest):
            result = VerifiedResult(
                verified_result_id=self._id("vrs"), interaction_id=interaction_id,
                execution_id=execution.execution_id, tenant_id=current.tenant_id,
                workspace_id=current.workspace_id, namespace=current.namespace,
                verification_method=observation.method, outcome=observation.outcome,
                verified_at=now,
                external_reference=observation.external_reference,
                evidence_digest=observation.evidence_digest,
            )
            facts.append(result)
            try:
                commit_evidence = await self._canonical_commit(
                    current, preview, execution, now
                )
            except Exception as exc:  # noqa: BLE001 - canonical authority boundary
                commit_evidence = None
                failure = FailureInfo(
                    code="interaction.canonical_commit_failed",
                    category=ErrorCategory.PERSISTENCE_FAILURE,
                    message=f"AI-Lab canonical commit evidence unavailable: {exc}",
                    component="trusted_interaction", operation="verify",
                    retryable=False, trace_id=current.trace_id,
                )
            references["verified_result_id"] = result.verified_result_id
        else:
            result = None
            commit_evidence = None

        if result is not None and commit_evidence is not None:
            result = result.model_copy(update={
                "canonical_commit_evidence_id":
                    commit_evidence.canonical_commit_evidence_id,
            })
            facts[0] = result
            facts.append(commit_evidence)
            if current.recovery_id is not None:
                recovery = await self._repository.fact(
                    interaction_id, Recovery, current.recovery_id
                )
                if recovery is not None:
                    facts.append(recovery.model_copy(update={
                        "status": RecoveryStatus.RECOVERED,
                        "evidence_digest": commit_evidence.evidence_digest,
                        "updated_at": now,
                    }))
            references["canonical_commit_evidence_id"] = (
                commit_evidence.canonical_commit_evidence_id
            )
            final = current.model_copy(update={
                "lifecycle_state": LifecycleState.SUCCEEDED,
                "execution_status": ExecutionStatus.COMPLETED,
                "verification_status": VerificationStatus.VERIFIED,
                "recovery_status": RecoveryStatus.RECOVERED
                if current.recovery_status != RecoveryStatus.NOT_REQUIRED
                else RecoveryStatus.NOT_REQUIRED,
                "verified_result_id": result.verified_result_id,
                "canonical_commit_evidence_id":
                    commit_evidence.canonical_commit_evidence_id,
                "canonical_object_id": commit_evidence.canonical_object_id,
                "failure": None, "revision": current.revision + 1,
                "updated_at": now,
            })
        else:
            recovery = Recovery(
                recovery_id=current.recovery_id or self._id("rcv"),
                interaction_id=interaction_id, tenant_id=current.tenant_id,
                workspace_id=current.workspace_id, namespace=current.namespace,
                actor_id=actor_id, status=RecoveryStatus.PENDING,
                reason=failure.code if failure else "interaction.verification_failed",
                evidence_digest=observation.evidence_digest if observation else None,
                created_at=now, updated_at=now,
            )
            facts.append(recovery)
            references["recovery_id"] = recovery.recovery_id
            if result is not None:
                references["verified_result_id"] = result.verified_result_id
            final = current.model_copy(update={
                "lifecycle_state": LifecycleState.RECOVERY_REQUIRED,
                "verification_status": (
                    observation.status if observation else VerificationStatus.UNCERTAIN
                ),
                "recovery_status": RecoveryStatus.PENDING,
                "recovery_id": recovery.recovery_id,
                "verified_result_id": result.verified_result_id if result else None,
                "failure": failure,
                "revision": current.revision + 1, "updated_at": now,
            })
        await self._transition(final, current.revision, facts,
                               [self._audit(final, event_type="interaction.verified"
                                            if final.lifecycle_state == LifecycleState.SUCCEEDED
                                            else "interaction.recovery_required",
                                            from_state=current.lifecycle_state,
                                            idempotency_key=idempotency_key,
                                            references=references, failure=failure)],
                               _idempotency_operation, idempotency_key, digest)
        return await self.status(workspace=workspace, actor_id=actor_id,
                                 interaction_id=interaction_id)

    async def _canonical_commit(
        self, interaction: Interaction, preview: Preview, execution: Execution, now
    ) -> CanonicalCommitEvidence:
        if not preview.canonical_commit_required:
            return CanonicalCommitEvidence(
                canonical_commit_evidence_id=self._id("cce"),
                interaction_id=interaction.interaction_id,
                execution_id=execution.execution_id,
                preview_id=preview.preview_id,
                tenant_id=interaction.tenant_id,
                workspace_id=interaction.workspace_id,
                namespace=interaction.namespace,
                policy_reference=interaction.policy_reference,
                commit_required=False,
                outcome="NOT_REQUIRED",
                canonical_object_id=preview.target_object_id,
                canonical_revision=preview.target_revision,
                evidence_digest=self._digest({
                    "interaction_id": interaction.interaction_id,
                    "preview_id": preview.preview_id,
                    "policy_reference": interaction.policy_reference,
                    "outcome": "NOT_REQUIRED",
                }),
                committed_at=now,
            )
        request = CanonicalCommitRequest(
            interaction_id=interaction.interaction_id,
            execution_id=execution.execution_id,
            preview_id=preview.preview_id,
            tenant_id=interaction.tenant_id,
            workspace_id=interaction.workspace_id,
            namespace=interaction.namespace,
            operation=interaction.operation,
            policy_reference=interaction.policy_reference,
            normalized_parameters=preview.normalized_parameters,
            target_object_id=preview.target_object_id,
            target_revision=preview.target_revision,
            trace_id=interaction.trace_id,
        )
        evidence = await self._canonical_commit_authority.record(request)
        if not self._canonical_commit_matches(request, evidence):
            raise ValueError("canonical commit evidence does not match the request")
        return evidence

    @staticmethod
    def _canonical_commit_matches(request, evidence) -> bool:
        return (
            evidence.interaction_id == request.interaction_id
            and evidence.execution_id == request.execution_id
            and evidence.preview_id == request.preview_id
            and evidence.tenant_id == request.tenant_id
            and evidence.workspace_id == request.workspace_id
            and evidence.namespace == request.namespace
            and evidence.policy_reference == request.policy_reference
            and evidence.commit_required is True
            and evidence.outcome == "COMMITTED"
            and bool(evidence.canonical_object_id)
            and evidence.canonical_revision is not None
            and bool(evidence.evidence_digest)
        )

    async def recover(
        self, *, workspace: WorkspaceKey, actor_id: str, interaction_id: str,
        expected_revision: int, idempotency_key: str,
    ) -> InteractionStatus:
        """Reconcile a persisted execution gap, then verify without re-execution."""

        scope = self._scope(workspace, actor_id)
        digest = self._digest({
            "interaction_id": interaction_id,
            "expected_revision": expected_revision,
        })
        prior = await self._idempotent(
            scope, "recover", idempotency_key, digest, workspace.trace_id
        )
        if prior is not None:
            return await self.status(
                workspace=workspace, actor_id=actor_id, interaction_id=interaction_id
            )
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.revision != expected_revision:
            reconciled = await self._idempotent(
                scope, "reconcile_execution", f"{idempotency_key}:execution-gap",
                digest, workspace.trace_id,
            )
            if reconciled is None or reconciled.interaction_id != interaction_id:
                self._fail(
                    "interaction.revision_conflict", ErrorCategory.CONFLICT,
                    "recover", "Interaction revision is stale",
                    trace_id=current.trace_id,
                )
            current = await self._require(scope, interaction_id, workspace.trace_id)
        if (current.lifecycle_state == LifecycleState.EXECUTING
                and current.execution_status == ExecutionStatus.ATTEMPTED):
            current = await self._reconcile_execution_gap(
                current=current,
                actor_id=actor_id,
                idempotency_key=f"{idempotency_key}:execution-gap",
                payload_digest=digest,
            )
        return await self.verify(
            workspace=workspace,
            actor_id=actor_id,
            interaction_id=interaction_id,
            expected_revision=current.revision,
            idempotency_key=idempotency_key,
            _idempotency_operation="recover",
            _idempotency_digest=digest,
        )

    async def _reconcile_execution_gap(
        self, *, current: Interaction, actor_id: str,
        idempotency_key: str, payload_digest: str,
    ) -> Interaction:
        execution = await self._repository.fact(
            current.interaction_id, Execution, current.current_execution_id
        )
        if execution is None or execution.status != ExecutionStatus.ATTEMPTED:
            self._fail(
                "interaction.execution_missing", ErrorCategory.CONFLICT,
                "recover", "Persisted attempted Execution is missing",
                trace_id=current.trace_id,
            )
        now = self._clock.now()
        failure = FailureInfo(
            code="interaction.execution_outcome_uncertain_after_restart",
            category=ErrorCategory.EXECUTION_FAILURE,
            message="Execution intent exists without a persisted port outcome",
            component="trusted_interaction", operation="recover",
            retryable=False, trace_id=current.trace_id,
        )
        uncertain_execution = execution.model_copy(update={
            "status": ExecutionStatus.UNCERTAIN,
            "failure": failure,
            "finished_at": now,
        })
        recovery = Recovery(
            recovery_id=current.recovery_id or self._id("rcv"),
            interaction_id=current.interaction_id,
            tenant_id=current.tenant_id,
            workspace_id=current.workspace_id,
            namespace=current.namespace,
            actor_id=actor_id,
            status=RecoveryStatus.PENDING,
            reason=failure.code,
            created_at=now,
            updated_at=now,
        )
        reconciled = current.model_copy(update={
            "lifecycle_state": LifecycleState.RECOVERY_REQUIRED,
            "execution_status": ExecutionStatus.UNCERTAIN,
            "verification_status": VerificationStatus.UNCERTAIN,
            "recovery_status": RecoveryStatus.PENDING,
            "recovery_id": recovery.recovery_id,
            "failure": failure,
            "revision": current.revision + 1,
            "updated_at": now,
        })
        await self._transition(
            reconciled,
            current.revision,
            [uncertain_execution, recovery],
            [self._audit(
                reconciled,
                event_type="interaction.execution_gap_reconciled",
                from_state=current.lifecycle_state,
                idempotency_key=idempotency_key,
                references={"execution_id": execution.execution_id},
                failure=failure,
            )],
            "reconcile_execution",
            idempotency_key,
            payload_digest,
        )
        return reconciled

    async def status(self, *, workspace: WorkspaceKey, actor_id: str,
                     interaction_id: str) -> InteractionStatus:
        scope = self._scope(workspace, actor_id)
        current = await self._require(scope, interaction_id, workspace.trace_id)
        if current.actor_id != actor_id:
            self._fail("interaction.actor_mismatch", ErrorCategory.PERMISSION_DENIED,
                       "status", "Actor mismatch", trace_id=current.trace_id)
        return InteractionStatus(
            interaction=current,
            preview=await self._repository.fact(interaction_id, Preview, current.current_preview_id),
            confirmation=await self._repository.fact(interaction_id, Confirmation,
                                                     current.current_confirmation_id),
            approval=await self._repository.fact(interaction_id, Approval,
                                                 current.current_approval_id),
            execution=await self._repository.fact(interaction_id, Execution,
                                                  current.current_execution_id),
            verified_result=await self._repository.fact(interaction_id, VerifiedResult,
                                                        current.verified_result_id),
            canonical_commit_evidence=await self._repository.fact(
                interaction_id,
                CanonicalCommitEvidence,
                current.canonical_commit_evidence_id,
            ),
            recovery=await self._repository.fact(interaction_id, Recovery, current.recovery_id),
        )

    async def view(self, *, workspace: WorkspaceKey, actor_id: str,
                   interaction_id: str) -> InteractionView:
        status = await self.status(workspace=workspace, actor_id=actor_id,
                                   interaction_id=interaction_id)
        item = status.interaction
        available: list[str] = ["status", "view"]
        if item.lifecycle_state in {LifecycleState.REQUESTED, LifecycleState.PREVIEWED,
                                    LifecycleState.AWAITING_CONFIRMATION}:
            available.extend(["preview", "modify", "cancel"])
        if item.lifecycle_state == LifecycleState.AWAITING_CONFIRMATION:
            available.append("approve" if status.confirmation else "confirm")
        if item.lifecycle_state == LifecycleState.AUTHORIZED:
            available.extend(["execute", "cancel"])
        if item.lifecycle_state in {LifecycleState.VERIFYING,
                                    LifecycleState.RECOVERY_REQUIRED}:
            available.append("verify" if item.lifecycle_state == LifecycleState.VERIFYING else "recover")
        return InteractionView(
            interaction_id=item.interaction_id, lifecycle_state=item.lifecycle_state,
            revision=item.revision, canonical_object_id=item.canonical_object_id,
            safe_summary=item.safe_summary, available_operations=tuple(dict.fromkeys(available)),
            preview_status=status.preview.status if status.preview else None,
            confirmation_id=item.current_confirmation_id,
            execution_status=item.execution_status,
            verification_status=item.verification_status,
            verified_result_id=item.verified_result_id,
            recovery_status=item.recovery_status, failure=item.failure,
        )

    async def audit(self, *, workspace: WorkspaceKey, actor_id: str,
                    interaction_id: str) -> list[AuditEvidence]:
        scope = self._scope(workspace, actor_id)
        await self._require(scope, interaction_id, workspace.trace_id)
        return await self._repository.audits(scope, interaction_id)

    async def _require(self, scope: tuple[str, str, str], interaction_id: str,
                       trace_id: str) -> Interaction:
        current = await self._repository.get(scope, interaction_id)
        if current is None:
            self._fail("interaction.not_found", ErrorCategory.NOT_FOUND,
                       "get", "Interaction was not found in this Workspace",
                       trace_id=trace_id)
        return current

    async def _transition(
        self, interaction: Interaction, expected_revision: int, facts: list[Any],
        audits: list[AuditEvidence], operation: str, idempotency_key: str,
        digest: str,
    ) -> None:
        try:
            await self._repository.transition(
                interaction, expected_revision, facts, audits, operation=operation,
                idempotency_key=idempotency_key, payload_digest=digest,
            )
        except ValueError as exc:
            self._fail("interaction.revision_conflict", ErrorCategory.CONFLICT,
                       operation, str(exc), trace_id=interaction.trace_id)

    def _invalid_state(self, interaction: Interaction, operation: str) -> None:
        self._fail(
            "interaction.invalid_state_transition", ErrorCategory.CONFLICT,
            operation,
            f"Operation {operation} is not legal from {interaction.lifecycle_state.value}",
            trace_id=interaction.trace_id,
            details={"state": interaction.lifecycle_state.value,
                     "revision": interaction.revision},
        )
