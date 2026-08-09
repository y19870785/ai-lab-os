"""Unit/application tests for canonical interaction rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.database import DatabaseManager
from core.errors import FailureException
from core.interaction import (
    DisabledExecutionPort,
    DisabledVerificationPort,
    ExecutionStatus,
    InteractionService,
    LifecycleState,
    PreviewStatus,
    RecoveryStatus,
    ResolutionPhase,
    SQLiteInteractionRepository,
    VerificationStatus,
)
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock

pytestmark = pytest.mark.asyncio(loop_scope="function")
NOW = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)


def workspace(name: str = "workspace-a", actor: str = "owner-a") -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id="tenant-a", workspace_id=name, namespace="business",
        user_id=actor, trace_id="trace-1",
    )


async def service(tmp_path: Path, *, execution=None, verification=None, clock=None):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteInteractionRepository(manager, tmp_path / "interactions.db")
    result = InteractionService(
        repository, clock or MutableClock(NOW),
        execution or DisabledExecutionPort(),
        verification or DisabledVerificationPort(),
    )
    await result.initialize()
    return result, manager


async def create(result: InteractionService, key: WorkspaceKey | None = None):
    return await result.create_interaction(
        workspace=key or workspace(), actor_id=(key or workspace()).user_id,
        operation="customer.follow_up", risk_level="medium",
        policy_reference="policy-1", request_id="request-1", trace_id="trace-1",
        idempotency_key="create-1", safe_summary="Follow up with customer",
    )


async def test_creation_is_canonical_idempotent_and_audited(tmp_path: Path):
    result, manager = await service(tmp_path)
    first = await create(result)
    second = await create(result)
    assert first == second
    assert first.interaction_id.startswith("int_")
    assert first.lifecycle_state == LifecycleState.REQUESTED
    assert first.revision == 1
    assert len(await result.audit(workspace=workspace(), actor_id="owner-a",
                                  interaction_id=first.interaction_id)) == 1
    manager.close_all()


@pytest.mark.parametrize(
    ("key", "actor"),
    [
        (WorkspaceKey(tenant_id="", workspace_id="a", namespace="n", user_id="u"), "u"),
        (WorkspaceKey(tenant_id="t", workspace_id="", namespace="n", user_id="u"), "u"),
        (WorkspaceKey(tenant_id="t", workspace_id="a", namespace="", user_id="u"), "u"),
        (WorkspaceKey(tenant_id="t", workspace_id="a", namespace="n", user_id=""), "u"),
        (WorkspaceKey(tenant_id="t", workspace_id="a", namespace="n", user_id="u"), "other"),
    ],
)
async def test_identity_and_workspace_fail_closed(tmp_path: Path, key, actor):
    result, manager = await service(tmp_path)
    with pytest.raises(FailureException) as caught:
        await result.create_interaction(
            workspace=key, actor_id=actor, operation="x", risk_level="low",
            policy_reference="p", request_id="r", trace_id="t",
            idempotency_key="k",
        )
    assert caught.value.failure.category.value == "permission_denied"
    manager.close_all()


async def test_preview_modify_supersedes_and_stale_confirm_fails(tmp_path: Path):
    result, manager = await service(tmp_path)
    interaction = await create(result)
    v1 = await result.preview(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=1, normalized_parameters={"message": "one"},
        mutation_summary="send one", expires_in=timedelta(hours=1),
        idempotency_key="preview-1",
    )
    current = await result.status(workspace=workspace(), actor_id="owner-a",
                                  interaction_id=interaction.interaction_id)
    v2 = await result.preview(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=current.interaction.revision,
        normalized_parameters={"message": "two"}, mutation_summary="send two",
        expires_in=timedelta(hours=1), idempotency_key="preview-2",
    )
    assert v2.preview_revision == 2
    old = await result._repository.fact(interaction.interaction_id, type(v1), v1.preview_id)
    assert old.status == PreviewStatus.SUPERSEDED
    current = await result.status(workspace=workspace(), actor_id="owner-a",
                                  interaction_id=interaction.interaction_id)
    with pytest.raises(FailureException) as caught:
        await result.confirm(
            workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
            preview_id=v1.preview_id, preview_revision=1,
            expected_revision=current.interaction.revision, idempotency_key="confirm-old",
        )
    assert caught.value.failure.code == "interaction.preview_stale"
    manager.close_all()


async def test_confirmation_cas_idempotency_and_cancel(tmp_path: Path):
    result, manager = await service(tmp_path)
    interaction = await create(result)
    preview = await result.preview(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=1, normalized_parameters={}, mutation_summary="mutate",
        expires_in=timedelta(hours=1), idempotency_key="preview",
    )
    current = await result.status(workspace=workspace(), actor_id="owner-a",
                                  interaction_id=interaction.interaction_id)
    confirmation = await result.confirm(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        preview_id=preview.preview_id, preview_revision=preview.preview_revision,
        expected_revision=current.interaction.revision, idempotency_key="confirm",
    )
    duplicate = await result.confirm(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        preview_id=preview.preview_id, preview_revision=preview.preview_revision,
        expected_revision=current.interaction.revision, idempotency_key="confirm",
    )
    assert duplicate.confirmation_id == confirmation.confirmation_id
    status = await result.status(workspace=workspace(), actor_id="owner-a",
                                 interaction_id=interaction.interaction_id)
    cancelled = await result.cancel(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=status.interaction.revision, idempotency_key="cancel",
    )
    assert cancelled.lifecycle_state == LifecycleState.CANCELLED
    manager.close_all()


async def test_expiry_uses_injected_clock(tmp_path: Path):
    clock = MutableClock(NOW)
    result, manager = await service(tmp_path, clock=clock)
    interaction = await create(result)
    await result.preview(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=1, normalized_parameters={}, mutation_summary="mutate",
        expires_in=timedelta(minutes=5), idempotency_key="preview",
    )
    clock.advance(timedelta(minutes=6))
    status = await result.status(workspace=workspace(), actor_id="owner-a",
                                 interaction_id=interaction.interaction_id)
    expired = await result.expire_preview(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=status.interaction.revision, idempotency_key="expire",
    )
    assert expired.lifecycle_state == LifecycleState.EXPIRED
    manager.close_all()


async def test_high_risk_approval_is_distinct_from_confirmation(tmp_path: Path):
    result, manager = await service(tmp_path)
    interaction = await create(result)
    preview = await result.preview(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=1, normalized_parameters={}, mutation_summary="high risk mutation",
        expires_in=timedelta(hours=1), idempotency_key="preview",
        requires_approval=True,
    )
    current = await result.status(workspace=workspace(), actor_id="owner-a",
                                  interaction_id=interaction.interaction_id)
    await result.confirm(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        preview_id=preview.preview_id, preview_revision=preview.preview_revision,
        expected_revision=current.interaction.revision, idempotency_key="confirm",
    )
    current = await result.status(workspace=workspace(), actor_id="owner-a",
                                  interaction_id=interaction.interaction_id)
    assert current.interaction.lifecycle_state == LifecycleState.AWAITING_CONFIRMATION
    assert current.confirmation is not None and current.approval is None
    approval = await result.approve(
        workspace=workspace(), actor_id="owner-a", interaction_id=interaction.interaction_id,
        preview_id=preview.preview_id, preview_revision=preview.preview_revision,
        expected_revision=current.interaction.revision, approver_role="owner",
        idempotency_key="approve",
    )
    current = await result.status(workspace=workspace(), actor_id="owner-a",
                                  interaction_id=interaction.interaction_id)
    assert approval.approval_id == current.approval.approval_id
    assert current.interaction.lifecycle_state == LifecycleState.AUTHORIZED
    manager.close_all()


async def test_cross_workspace_read_is_rejected(tmp_path: Path):
    result, manager = await service(tmp_path)
    interaction = await create(result)
    with pytest.raises(FailureException) as caught:
        await result.status(workspace=workspace("workspace-b"), actor_id="owner-a",
                            interaction_id=interaction.interaction_id)
    assert caught.value.failure.code == "interaction.not_found"
    manager.close_all()


async def test_arch001_state_vocabularies_are_implemented_exactly():
    assert {state.value for state in LifecycleState} == {
        "REQUESTED", "PREVIEWED", "AWAITING_CONFIRMATION", "AUTHORIZED",
        "EXECUTING", "VERIFYING", "SUCCEEDED", "FAILED", "CANCELLED",
        "EXPIRED", "RECOVERY_REQUIRED",
    }
    assert {state.value for state in ResolutionPhase} == {
        "UNRESOLVED", "RESOLVING", "RESOLVED",
    }
    assert {state.value for state in ExecutionStatus} == {
        "NOT_STARTED", "ACCEPTED", "ATTEMPTED", "ACKNOWLEDGED", "COMPLETED",
        "REJECTED", "FAILED", "UNCERTAIN",
    }
    assert {state.value for state in VerificationStatus} == {
        "NOT_REQUIRED", "PENDING", "VERIFIED", "FAILED", "UNCERTAIN",
    }
    assert {state.value for state in RecoveryStatus} == {
        "NOT_REQUIRED", "PENDING", "IN_PROGRESS", "RECOVERED", "FAILED",
    }
