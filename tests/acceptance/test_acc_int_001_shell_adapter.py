"""ACC-INT-001 A-Q evidence for the Shell-neutral adapter boundary."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from applications.trusted_interaction_adapter import (
    AdapterResponse,
    ShellAssertion,
    TrustedInteractionAdapter,
)
from applications.trusted_interaction_adapter.mcp_server import (
    TOOL_NAMES,
    build_mcp_server,
)
from core.database import DatabaseManager
from core.errors import FailureInfo
from core.interaction import (
    DisabledExecutionPort,
    DisabledVerificationPort,
    InteractionService,
    LifecycleState,
    SQLiteInteractionRepository,
)
from tests.helpers.clock import MutableClock
from tests.helpers.interaction import (
    ReferenceCanonicalCommitAuthority,
    ReferenceExecutionPort,
    ReferenceVerificationPort,
    uncertain,
    verified,
)
from tests.helpers.interaction_adapter import (
    ReferenceOperationPolicyResolver,
    ReferenceShellBindingResolver,
    shell_assertion,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")
NOW = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)


async def _adapter(tmp_path, *, binding=None, policy=None):
    clock = MutableClock(NOW)
    manager = DatabaseManager(tmp_path)
    interactions = InteractionService(
        SQLiteInteractionRepository(manager, tmp_path / "interactions.db"),
        clock,
        DisabledExecutionPort(),
        DisabledVerificationPort(),
        ReferenceCanonicalCommitAuthority(clock),
    )
    await interactions.initialize()
    return TrustedInteractionAdapter(interactions, binding, policy), manager


async def _recovery_adapter(tmp_path):
    clock = MutableClock(NOW)
    manager = DatabaseManager(tmp_path)
    execution = ReferenceExecutionPort(uncertain())
    verification = ReferenceVerificationPort(verified())
    interactions = InteractionService(
        SQLiteInteractionRepository(manager, tmp_path / "interactions.db"),
        clock,
        execution,
        verification,
        ReferenceCanonicalCommitAuthority(clock),
    )
    await interactions.initialize()
    binding = ReferenceShellBindingResolver()
    adapter = TrustedInteractionAdapter(
        interactions, binding, ReferenceOperationPolicyResolver()
    )
    return adapter, interactions, binding, execution, manager


async def _recovery_required(adapter, interactions, binding):
    previewed = await _preview(adapter)
    confirmed = await adapter.confirm(
        assertion=shell_assertion(),
        interaction_id=previewed.interaction_id,
        preview_id=previewed.preview.preview_id,
        preview_revision=previewed.preview.preview_revision,
        expected_revision=previewed.revision,
        idempotency_key="confirm-1",
    )
    status = await interactions.start_execution(
        workspace=binding.context.workspace,
        actor_id=binding.context.actor_id,
        interaction_id=previewed.interaction_id,
        expected_revision=confirmed.revision,
        idempotency_key="execute-1",
    )
    assert status.interaction.lifecycle_state == LifecycleState.RECOVERY_REQUIRED
    return status


async def _preview(result, *, assertion=None, key="request-1", value=1):
    return await result.preview(
        assertion=assertion or shell_assertion(),
        requested_operation="reference.noop",
        parameters={"value": value},
        idempotency_key=key,
    )


async def test_acc_int_001_a_shell_neutral_ownership_boundary():
    from applications.trusted_interaction_adapter import service

    source = inspect.getsource(service).lower()
    assert "interactionservice" in source
    assert "repository" not in source
    assert "databasemanager" not in source
    assert "sqlite" not in source
    assert "hermes" not in source


async def test_acc_int_001_b_identity_binding_fails_closed(tmp_path):
    result, manager = await _adapter(tmp_path)
    response = await _preview(result)
    assert response.failure.code == "interaction_adapter.identity_binding_unavailable"
    manager.close_all()


async def test_acc_int_001_c_operation_policy_fails_closed(tmp_path):
    result, manager = await _adapter(
        tmp_path, binding=ReferenceShellBindingResolver()
    )
    response = await _preview(result)
    assert response.failure.code == "interaction_adapter.operation_policy_unavailable"
    manager.close_all()


async def test_acc_int_001_d_preview_has_zero_external_side_effect(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    response = await _preview(result)
    assert response.preview.expected_external_effects == ()
    assert response.execution_status == "NOT_STARTED"
    assert response.final is False
    manager.close_all()


async def test_acc_int_001_e_composite_idempotency(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    first = await _preview(result)
    duplicate = await _preview(result)
    conflict = await _preview(result, value=2)
    assert duplicate.interaction_id == first.interaction_id
    assert duplicate.preview.preview_id == first.preview.preview_id
    assert conflict.failure.code == "interaction.idempotency_conflict"
    manager.close_all()


async def test_acc_int_001_f_confirmation_is_bound_to_canonical_preview(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    previewed = await _preview(result)
    response = await result.confirm(
        assertion=shell_assertion(),
        interaction_id=previewed.interaction_id,
        preview_id=previewed.preview.preview_id,
        preview_revision=previewed.preview.preview_revision,
        expected_revision=previewed.revision,
        idempotency_key="confirm-1",
    )
    assert response.lifecycle_state == LifecycleState.AUTHORIZED.value
    manager.close_all()


async def test_acc_int_001_g_modify_invalidates_old_consent(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    first = await _preview(result)
    second = await result.modify(
        assertion=shell_assertion(),
        interaction_id=first.interaction_id,
        expected_revision=first.revision,
        requested_operation="reference.noop",
        parameters={"value": 2},
        idempotency_key="modify-1",
    )
    stale = await result.confirm(
        assertion=shell_assertion(),
        interaction_id=first.interaction_id,
        preview_id=first.preview.preview_id,
        preview_revision=first.preview.preview_revision,
        expected_revision=second.revision,
        idempotency_key="confirm-old",
    )
    assert stale.failure.code == "interaction.preview_stale"
    manager.close_all()


async def test_acc_int_001_h_cancel_uses_canonical_safety_rules(tmp_path):
    result, interactions, binding, _, manager = await _recovery_adapter(tmp_path)
    recovery_required = await _recovery_required(result, interactions, binding)
    audits_before = await interactions.audit(
        workspace=binding.context.workspace,
        actor_id=binding.context.actor_id,
        interaction_id=recovery_required.interaction.interaction_id,
    )
    rejected = await result.cancel(
        assertion=shell_assertion(),
        interaction_id=recovery_required.interaction.interaction_id,
        expected_revision=recovery_required.interaction.revision,
        idempotency_key="cancel-1",
    )
    canonical = await interactions.status(
        workspace=binding.context.workspace,
        actor_id=binding.context.actor_id,
        interaction_id=recovery_required.interaction.interaction_id,
    )
    audits_after = await interactions.audit(
        workspace=binding.context.workspace,
        actor_id=binding.context.actor_id,
        interaction_id=recovery_required.interaction.interaction_id,
    )
    assert rejected.failure.code == "interaction.cancel_outcome_uncertain"
    assert canonical.interaction.lifecycle_state == LifecycleState.RECOVERY_REQUIRED
    assert audits_after == audits_before
    assert not any(item.event_type == "interaction.cancelled" for item in audits_after)
    manager.close_all()


async def test_acc_int_001_i_status_is_canonical(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    previewed = await _preview(result)
    direct = await result.status(
        assertion=shell_assertion(), interaction_id=previewed.interaction_id
    )
    server = build_mcp_server(result)
    mcp_result = await server.call_tool(
        "ai_lab_interaction_status",
        {
            "assertion": shell_assertion().model_dump(mode="json"),
            "interaction_id": previewed.interaction_id,
        },
    )
    mcp = mcp_result.structured_content
    fields = (
        "interaction_id",
        "revision",
        "lifecycle_state",
        "execution_status",
        "verification_status",
        "recovery_status",
        "available_operations",
        "authoritative",
        "final",
    )
    assert direct.authoritative is True
    assert direct.revision == previewed.revision
    assert {field: getattr(direct, field) for field in fields} == {
        field: tuple(mcp[field]) if field == "available_operations" else mcp[field]
        for field in fields
    }
    assert direct.transport == "direct"
    assert mcp["transport"] == "mcp-stdio"
    manager.close_all()


async def test_acc_int_001_j_view_uses_canonical_available_operations(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    previewed = await _preview(result)
    view = await result.view(
        assertion=shell_assertion(), interaction_id=previewed.interaction_id
    )
    assert {"status", "view", "modify", "cancel", "confirm"}.issubset(
        view.available_operations
    )
    manager.close_all()


async def test_acc_int_001_k_mcp_allowlist_is_exact():
    assert TOOL_NAMES == (
        "ai_lab_interaction_preview",
        "ai_lab_interaction_modify",
        "ai_lab_interaction_confirm",
        "ai_lab_interaction_cancel",
        "ai_lab_interaction_status",
        "ai_lab_interaction_view",
        "ai_lab_interaction_recover",
    )


async def test_acc_int_001_l_transport_success_is_not_business_success(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    response = await _preview(result)
    assert response.failure is None
    assert response.final is False
    manager.close_all()


async def test_acc_int_001_m_failure_info_redacts_secrets():
    failure = FailureInfo(
        code="adapter.failure",
        category="internal",
        message="Bearer abcdefghijklmnop",
        component="trusted_interaction_adapter",
        operation="preview",
        details={"token": "secret-value", "safe": "visible"},
    )
    assert failure.message == "<REDACTED>"
    assert failure.details["token"] == "<REDACTED>"


async def test_acc_int_001_n_contract_carries_restart_stable_canonical_id(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    response = await _preview(result)
    assert response.interaction_id.startswith("int_")
    assert response.contract_version == "trusted-interaction/v1"
    manager.close_all()


async def test_acc_int_001_o_mcp_recovery_never_reexecutes(tmp_path):
    result, interactions, binding, execution, manager = await _recovery_adapter(
        tmp_path
    )
    recovery_required = await _recovery_required(result, interactions, binding)
    execution_calls_before = len(execution.requests)
    server = build_mcp_server(result)
    recovered = await server.call_tool(
        "ai_lab_interaction_recover",
        {
            "assertion": shell_assertion().model_dump(mode="json"),
            "interaction_id": recovery_required.interaction.interaction_id,
            "expected_revision": recovery_required.interaction.revision,
            "idempotency_key": "recover-1",
        },
    )
    execution_calls_after = len(execution.requests)
    canonical = await interactions.status(
        workspace=binding.context.workspace,
        actor_id=binding.context.actor_id,
        interaction_id=recovery_required.interaction.interaction_id,
    )
    assert execution_calls_before == execution_calls_after == 1
    assert recovered.structured_content["lifecycle_state"] == "SUCCEEDED"
    assert canonical.interaction.lifecycle_state == LifecycleState.SUCCEEDED
    assert canonical.recovery is not None
    assert canonical.recovery.status.value == "RECOVERED"
    manager.close_all()


async def test_acc_int_001_p_shell_is_replaceable(tmp_path):
    result, manager = await _adapter(
        tmp_path,
        binding=ReferenceShellBindingResolver(),
        policy=ReferenceOperationPolicyResolver(),
    )
    previewed = await _preview(result, assertion=shell_assertion(shell="shell-a"))
    observed = await result.status(
        assertion=shell_assertion(shell="shell-b"),
        interaction_id=previewed.interaction_id,
    )
    assert observed.interaction_id == previewed.interaction_id
    manager.close_all()


async def test_acc_int_001_q_response_contract_is_transport_neutral():
    fields = set(AdapterResponse.model_fields)
    assert {
        "contract_version",
        "adapter",
        "transport",
        "interaction_id",
        "authoritative",
        "lifecycle_state",
        "available_operations",
        "failure",
        "final",
    }.issubset(fields)
    assert "transport_success" not in fields
    assert ShellAssertion.model_fields["asserted_workspace"].is_required() is False
