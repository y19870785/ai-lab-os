"""ACC-021 A-R canonical trusted interaction acceptance evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.database import DatabaseManager
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.interaction import (
    DisabledCanonicalCommitAuthority,
    InteractionService,
    LifecycleState,
    RecoveryStatus,
    SQLiteInteractionRepository,
    VerificationObservation,
    VerificationStatus,
)
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock
from tests.helpers.interaction import (
    ReferenceApprovalAuthority,
    ReferenceCanonicalCommitAuthority,
    ReferenceExecutionPort,
    ReferenceVerificationPort,
    acknowledged,
    uncertain,
    verified,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")
NOW = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)
WS = WorkspaceKey(tenant_id="tenant", workspace_id="workspace", namespace="business",
                  user_id="owner", trace_id="trace")


async def make_service(
    tmp_path: Path, execution=None, verification=None, clock=None,
    canonical_commit=None, approval_authority=None,
):
    active_clock = clock or MutableClock(NOW)
    manager = DatabaseManager(tmp_path)
    repository = SQLiteInteractionRepository(manager, tmp_path / "interactions.db")
    service = InteractionService(
        repository, active_clock,
        execution or ReferenceExecutionPort(acknowledged()),
        verification or ReferenceVerificationPort(verified()),
        canonical_commit or ReferenceCanonicalCommitAuthority(active_clock),
        approval_authority or ReferenceApprovalAuthority(active_clock),
    )
    await service.initialize()
    return service, manager


async def authorize(service: InteractionService, *, suffix: str = ""):
    item = await service.create_interaction(
        workspace=WS, actor_id="owner", operation="quote.create", risk_level="high",
        policy_reference="policy", request_id=f"request{suffix}", trace_id="trace",
        idempotency_key=f"create{suffix}",
    )
    preview = await service.preview(
        workspace=WS, actor_id="owner", interaction_id=item.interaction_id,
        expected_revision=1, normalized_parameters={"amount": 10},
        mutation_summary="create quotation", expires_in=timedelta(hours=1),
        idempotency_key=f"preview{suffix}",
    )
    status = await service.status(workspace=WS, actor_id="owner",
                                  interaction_id=item.interaction_id)
    await service.confirm(
        workspace=WS, actor_id="owner", interaction_id=item.interaction_id,
        preview_id=preview.preview_id, preview_revision=preview.preview_revision,
        expected_revision=status.interaction.revision, idempotency_key=f"confirm{suffix}",
    )
    return await service.status(workspace=WS, actor_id="owner",
                                interaction_id=item.interaction_id)


async def test_acc_021_a_c_h_i_j_canonical_happy_path(tmp_path: Path):
    service, manager = await make_service(tmp_path)
    authorized = await authorize(service)
    assert authorized.interaction.interaction_id.startswith("int_")  # A
    assert authorized.preview is not None and authorized.confirmation is not None  # C
    executing = await service.start_execution(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=authorized.interaction.revision, idempotency_key="execute",
    )
    assert executing.execution is not None and executing.execution.execution_id.startswith("exe_")  # H
    assert executing.interaction.lifecycle_state == LifecycleState.VERIFYING  # I
    final = await service.verify(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=executing.interaction.revision, idempotency_key="verify",
    )
    assert final.interaction.lifecycle_state == LifecycleState.SUCCEEDED  # J
    assert final.verified_result and final.verified_result.evidence_digest
    assert len(await service.audit(workspace=WS, actor_id="owner",
                                   interaction_id=final.interaction.interaction_id)) >= 7
    manager.close_all()


async def test_acc_021_f_idempotency_and_conflict(tmp_path: Path):
    service, manager = await make_service(tmp_path)
    first = await service.create_interaction(
        workspace=WS, actor_id="owner", operation="x", risk_level="low",
        policy_reference="p", request_id="r", trace_id="trace", idempotency_key="same",
    )
    duplicate = await service.create_interaction(
        workspace=WS, actor_id="owner", operation="x", risk_level="low",
        policy_reference="p", request_id="r", trace_id="trace", idempotency_key="same",
    )
    assert duplicate.interaction_id == first.interaction_id
    with pytest.raises(FailureException) as caught:
        await service.create_interaction(
            workspace=WS, actor_id="owner", operation="different", risk_level="low",
            policy_reference="p", request_id="r", trace_id="trace", idempotency_key="same",
        )
    assert caught.value.failure.code == "interaction.idempotency_conflict"
    manager.close_all()


async def test_acc_021_g_l_m_n_uncertain_is_persisted_and_never_blind_retried(tmp_path: Path):
    executor = ReferenceExecutionPort(uncertain())
    service, manager = await make_service(tmp_path, execution=executor)
    authorized = await authorize(service)
    uncertain_status = await service.start_execution(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=authorized.interaction.revision, idempotency_key="execute",
    )
    assert uncertain_status.interaction.lifecycle_state == LifecycleState.RECOVERY_REQUIRED  # L
    assert uncertain_status.interaction.recovery_status == RecoveryStatus.PENDING
    duplicate = await service.start_execution(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=authorized.interaction.revision, idempotency_key="execute",
    )
    assert duplicate.interaction.lifecycle_state == LifecycleState.RECOVERY_REQUIRED  # M
    assert len(executor.requests) == 1
    with pytest.raises(FailureException):
        await service.cancel(
            workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
            expected_revision=uncertain_status.interaction.revision, idempotency_key="cancel",
        )  # G
    interaction_id = authorized.interaction.interaction_id
    manager.close_all()
    restarted, restarted_manager = await make_service(tmp_path)
    restored = await restarted.status(workspace=WS, actor_id="owner",
                                      interaction_id=interaction_id)
    assert restored.interaction.lifecycle_state == LifecycleState.RECOVERY_REQUIRED  # N
    restarted_manager.close_all()


async def test_acc_021_k_verification_failure_requires_recovery(tmp_path: Path):
    failure = FailureInfo(
        code="external.verification_failed", category=ErrorCategory.EXECUTION_FAILURE,
        message="verification rejected token=super-secret-value",
        component="reference", operation="verify", details={"api_key": "secret-value"},
    )
    verifier = ReferenceVerificationPort(VerificationObservation(
        status=VerificationStatus.FAILED, method="read-after-write",
        outcome="not observed", evidence_digest="failed-digest", failure=failure,
    ))
    service, manager = await make_service(tmp_path, verification=verifier)
    authorized = await authorize(service)
    executing = await service.start_execution(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=authorized.interaction.revision, idempotency_key="execute",
    )
    result = await service.verify(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=executing.interaction.revision, idempotency_key="verify",
    )
    assert result.interaction.lifecycle_state == LifecycleState.RECOVERY_REQUIRED
    assert result.interaction.failure.details["api_key"] == "<REDACTED>"  # P
    manager.close_all()


async def test_acc_021_j_verified_external_result_without_canonical_commit_cannot_succeed(
    tmp_path: Path,
):
    verifier = ReferenceVerificationPort(VerificationObservation(
        status=VerificationStatus.VERIFIED, method="read-after-write",
        outcome="external mutation observed", evidence_digest="verified-digest",
    ))
    service, manager = await make_service(
        tmp_path,
        verification=verifier,
        canonical_commit=DisabledCanonicalCommitAuthority(),
    )
    authorized = await authorize(service)
    executing = await service.start_execution(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=authorized.interaction.revision, idempotency_key="execute",
    )
    result = await service.verify(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=executing.interaction.revision, idempotency_key="verify",
    )
    assert result.interaction.lifecycle_state == LifecycleState.RECOVERY_REQUIRED
    assert result.verified_result is not None
    assert result.verified_result.canonical_commit_evidence_id is None
    assert result.canonical_commit_evidence is None
    assert result.interaction.failure.code == "interaction.canonical_commit_failed"
    manager.close_all()


async def test_acc_021_o_r_late_and_cross_workspace_commands_fail(tmp_path: Path):
    service, manager = await make_service(tmp_path)
    authorized = await authorize(service)
    with pytest.raises(FailureException) as late:
        await service.confirm(
            workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
            preview_id=authorized.preview.preview_id,
            preview_revision=authorized.preview.preview_revision,
            expected_revision=2, idempotency_key="late",
        )
    assert late.value.failure.category == ErrorCategory.CONFLICT  # O
    other = WS.model_copy(update={"workspace_id": "other"})
    with pytest.raises(FailureException):
        await service.status(workspace=other, actor_id="owner",
                             interaction_id=authorized.interaction.interaction_id)  # R
    manager.close_all()


async def test_acc_021_q_atomic_verified_result_transition(tmp_path: Path, monkeypatch):
    service, manager = await make_service(tmp_path)
    authorized = await authorize(service)
    executing = await service.start_execution(
        workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
        expected_revision=authorized.interaction.revision, idempotency_key="execute",
    )
    original = service._repository._insert_audit

    def fail_audit(conn, audit):
        if audit.event_type == "interaction.verified":
            raise RuntimeError("injected audit failure")
        original(conn, audit)

    monkeypatch.setattr(service._repository, "_insert_audit", fail_audit)
    with pytest.raises(RuntimeError, match="injected audit failure"):
        await service.verify(
            workspace=WS, actor_id="owner", interaction_id=authorized.interaction.interaction_id,
            expected_revision=executing.interaction.revision, idempotency_key="verify",
        )
    restored = await service.status(workspace=WS, actor_id="owner",
                                    interaction_id=authorized.interaction.interaction_id)
    assert restored.interaction.lifecycle_state == LifecycleState.VERIFYING
    assert restored.verified_result is None
    manager.close_all()
