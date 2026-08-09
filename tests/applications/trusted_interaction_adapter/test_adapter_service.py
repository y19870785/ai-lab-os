"""Application tests for the Shell-neutral trusted interaction facade."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from applications.trusted_interaction_adapter import TrustedInteractionAdapter
from core.database import DatabaseManager
from core.interaction import (
    DisabledExecutionPort,
    DisabledVerificationPort,
    InteractionService,
    LifecycleState,
    SQLiteInteractionRepository,
)
from tests.helpers.clock import MutableClock
from tests.helpers.interaction import ReferenceCanonicalCommitAuthority
from tests.helpers.interaction_adapter import (
    ReferenceOperationPolicyResolver,
    ReferenceShellBindingResolver,
    shell_assertion,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")
NOW = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)


async def adapter(tmp_path, *, binding=None, policy=None):
    clock = MutableClock(NOW)
    manager = DatabaseManager(tmp_path)
    repository = SQLiteInteractionRepository(manager, tmp_path / "interactions.db")
    interactions = InteractionService(
        repository,
        clock,
        DisabledExecutionPort(),
        DisabledVerificationPort(),
        ReferenceCanonicalCommitAuthority(clock),
    )
    await interactions.initialize()
    return (
        TrustedInteractionAdapter(interactions, binding, policy),
        interactions,
        manager,
    )


async def test_default_identity_authority_fails_closed_before_domain_call(tmp_path):
    result, _, manager = await adapter(tmp_path)
    response = await result.preview(
        assertion=shell_assertion(),
        requested_operation="anything",
        parameters={},
        idempotency_key="preview-1",
    )
    assert response.failure is not None
    assert response.failure.code == "interaction_adapter.identity_binding_unavailable"
    assert response.authoritative is False
    assert response.interaction_id is None
    manager.close_all()


async def test_default_policy_authority_fails_closed(tmp_path):
    result, _, manager = await adapter(
        tmp_path, binding=ReferenceShellBindingResolver()
    )
    response = await result.preview(
        assertion=shell_assertion(),
        requested_operation="anything",
        parameters={},
        idempotency_key="preview-1",
    )
    assert response.failure is not None
    assert response.failure.code == "interaction_adapter.operation_policy_unavailable"
    assert response.authoritative is False
    manager.close_all()


async def test_preview_is_canonical_zero_effect_and_composite_idempotent(tmp_path):
    bindings = ReferenceShellBindingResolver()
    policies = ReferenceOperationPolicyResolver()
    result, interactions, manager = await adapter(
        tmp_path, binding=bindings, policy=policies
    )
    first = await result.preview(
        assertion=shell_assertion(shell="shell-a"),
        requested_operation="reference.noop",
        parameters={"value": 1},
        idempotency_key="request-1",
    )
    second = await result.preview(
        assertion=shell_assertion(shell="shell-a"),
        requested_operation="reference.noop",
        parameters={"value": 1},
        idempotency_key="request-1",
    )
    assert first.interaction_id == second.interaction_id
    assert first.preview is not None
    assert first.preview.expected_external_effects == ()
    assert first.lifecycle_state == LifecycleState.AWAITING_CONFIRMATION.value
    assert first.authoritative is True
    assert first.final is False
    audits = await interactions.audit(
        workspace=bindings.context.workspace,
        actor_id=bindings.context.actor_id,
        interaction_id=first.interaction_id,
    )
    assert [item.event_type for item in audits].count("interaction.requested") == 1
    assert [item.event_type for item in audits].count("interaction.previewed") == 1
    manager.close_all()


async def test_same_idempotency_key_with_different_payload_conflicts(tmp_path):
    result, _, manager = await adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    first = await result.preview(
        assertion=shell_assertion(),
        requested_operation="reference.noop",
        parameters={"value": 1},
        idempotency_key="request-1",
    )
    conflict = await result.preview(
        assertion=shell_assertion(),
        requested_operation="reference.noop",
        parameters={"value": 2},
        idempotency_key="request-1",
    )
    assert first.failure is None
    assert conflict.failure is not None
    assert conflict.failure.code == "interaction.idempotency_conflict"
    assert conflict.authoritative is True
    manager.close_all()


async def test_modify_supersedes_old_preview_and_old_confirmation_fails(tmp_path):
    result, _, manager = await adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    first = await result.preview(
        assertion=shell_assertion(),
        requested_operation="reference.noop",
        parameters={"value": 1},
        idempotency_key="request-1",
    )
    modified = await result.modify(
        assertion=shell_assertion(),
        interaction_id=first.interaction_id,
        expected_revision=first.revision,
        requested_operation="reference.noop",
        parameters={"value": 2},
        idempotency_key="modify-1",
    )
    assert modified.preview.preview_revision == 2
    stale = await result.confirm(
        assertion=shell_assertion(),
        interaction_id=first.interaction_id,
        preview_id=first.preview.preview_id,
        preview_revision=first.preview.preview_revision,
        expected_revision=modified.revision,
        idempotency_key="confirm-old",
    )
    assert stale.failure is not None
    assert stale.failure.code == "interaction.preview_stale"
    manager.close_all()


async def test_confirm_cancel_status_and_view_are_canonical(tmp_path):
    result, _, manager = await adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    previewed = await result.preview(
        assertion=shell_assertion(),
        requested_operation="reference.noop",
        parameters={},
        idempotency_key="request-1",
    )
    confirmed = await result.confirm(
        assertion=shell_assertion(),
        interaction_id=previewed.interaction_id,
        preview_id=previewed.preview.preview_id,
        preview_revision=previewed.preview.preview_revision,
        expected_revision=previewed.revision,
        idempotency_key="confirm-1",
    )
    assert confirmed.lifecycle_state == LifecycleState.AUTHORIZED.value
    assert confirmed.final is False
    viewed = await result.view(
        assertion=shell_assertion(), interaction_id=previewed.interaction_id
    )
    assert viewed.available_operations == confirmed.available_operations
    cancelled = await result.cancel(
        assertion=shell_assertion(),
        interaction_id=previewed.interaction_id,
        expected_revision=confirmed.revision,
        idempotency_key="cancel-1",
    )
    assert cancelled.lifecycle_state == LifecycleState.CANCELLED.value
    assert cancelled.authoritative is True
    assert cancelled.final is False
    manager.close_all()


@pytest.mark.parametrize("method", ["modify", "confirm", "cancel", "recover"])
async def test_every_mutating_operation_requires_authoritative_binding(tmp_path, method):
    result, _, manager = await adapter(tmp_path)
    common = {
        "assertion": shell_assertion(),
        "interaction_id": "int-untrusted",
        "expected_revision": 1,
        "idempotency_key": "key-1",
    }
    if method == "modify":
        common.update(requested_operation="x", parameters={})
    if method == "confirm":
        common.update(preview_id="preview-1", preview_revision=1)
    response = await getattr(result, method)(**common)
    assert response.failure.code == "interaction_adapter.identity_binding_unavailable"
    manager.close_all()
