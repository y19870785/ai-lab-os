"""Canonical interaction projections shared by every Shell transport."""

from __future__ import annotations

from applications.trusted_interaction_adapter.models import (
    AdapterResponse,
    PreviewPayload,
)
from core.errors import FailureInfo
from core.interaction import InteractionStatus, InteractionView, LifecycleState


def project_failure(
    failure: FailureInfo,
    *,
    request_id: str,
    trace_id: str,
    authoritative: bool = False,
) -> AdapterResponse:
    return AdapterResponse(
        request_id=request_id,
        trace_id=trace_id or failure.trace_id,
        authoritative=authoritative,
        failure=failure,
        final=False,
    )


def project_status(
    status: InteractionStatus,
    view: InteractionView,
    *,
    request_id: str,
    trace_id: str,
) -> AdapterResponse:
    item = status.interaction
    preview = status.preview
    preview_payload = None
    if preview is not None:
        preview_payload = PreviewPayload(
            preview_id=preview.preview_id,
            preview_revision=preview.preview_revision,
            status=preview.status.value,
            operation=preview.operation,
            policy_reference=preview.policy_reference,
            risk_level=preview.risk_level,
            normalized_parameters=preview.normalized_parameters,
            mutation_summary=preview.mutation_summary,
            expected_external_effects=preview.expected_external_effects,
            requires_confirmation=preview.requires_confirmation,
            requires_approval=preview.requires_approval,
            canonical_commit_required=preview.canonical_commit_required,
            expires_at=preview.expires_at.isoformat(),
        )
    return AdapterResponse(
        request_id=request_id,
        trace_id=trace_id,
        interaction_id=item.interaction_id,
        revision=item.revision,
        authoritative=True,
        lifecycle_state=item.lifecycle_state.value,
        execution_status=item.execution_status.value,
        verification_status=item.verification_status.value,
        recovery_status=item.recovery_status.value,
        available_operations=view.available_operations,
        preview=preview_payload,
        failure=item.failure,
        final=(
            item.lifecycle_state == LifecycleState.SUCCEEDED
            and status.verified_result is not None
            and (
                preview is None
                or not preview.canonical_commit_required
                or status.canonical_commit_evidence is not None
            )
        ),
    )
