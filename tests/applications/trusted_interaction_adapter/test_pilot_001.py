"""PILOT-001 Phase-0 authority and preview-only acceptance evidence."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from applications.trusted_interaction_adapter.mcp_server import (
    TOOL_NAMES,
    build_mcp_server,
)
from applications.trusted_interaction_adapter.models import ShellAssertion
from applications.trusted_interaction_adapter.pilot_001 import (
    ALLOWED_OPERATION,
    BINDING_TYPE,
    FIXED_SOURCE,
    POLICY_REFERENCE,
    PREVIEW_TTL_SECONDS,
    RISK_LEVEL,
    Pilot001AuthorityConfig,
    Pilot001OperationPolicyResolver,
    Pilot001OwnerBindingResolver,
)
from applications.trusted_interaction_adapter.pilot_001_mcp_server import (
    build_pilot_001_adapter,
)
from applications.trusted_interaction_adapter.service import TrustedInteractionAdapter
from core.errors import ErrorCategory, FailureException
from core.interaction import (
    DisabledApprovalAuthority,
    DisabledCanonicalCommitAuthority,
    DisabledExecutionPort,
    DisabledVerificationPort,
)
from core.system import create_system, make_test_settings
from core.user_tasks.models import UserTaskQuery

pytestmark = pytest.mark.asyncio(loop_scope="function")

OWNER_ID = "synthetic-wecom-owner"
ACTOR_ID = "pilot-owner-a"


def pilot_environment() -> dict[str, str]:
    return {
        "AI_LAB_PILOT_001_MODE": "phase0_preview_only",
        "AI_LAB_PILOT_001_EXPECTED_SHELL": "hermes",
        "AI_LAB_PILOT_001_EXPECTED_CHANNEL": "wecom",
        "AI_LAB_PILOT_001_OWNER_CHANNEL_IDENTITY": OWNER_ID,
        "AI_LAB_PILOT_001_ACTOR_ID": ACTOR_ID,
        "AI_LAB_PILOT_001_TENANT_ID": "tenant-a",
        "AI_LAB_PILOT_001_WORKSPACE_ID": "workspace-a",
        "AI_LAB_PILOT_001_NAMESPACE": "business",
    }


def config() -> Pilot001AuthorityConfig:
    return Pilot001AuthorityConfig.from_environment(pilot_environment())


def assertion(**changes: object) -> ShellAssertion:
    values = {
        "channel": "wecom",
        "shell": "hermes",
        "shell_session_id": "session-a",
        "channel_identity": OWNER_ID,
        "asserted_workspace": "caller-controlled",
        "message_id": "message-a",
        "correlation": {"request_id": "request-a", "trace_id": "trace-a"},
    }
    values.update(changes)
    return ShellAssertion(**values)


def parameters(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "title": " 跟进测试客户护发精油报价 ",
        "description": "跟进 5000 盒护发精油报价",
        "priority": "high",
        "due_at": "2026-08-13T15:00:00+08:00",
        "timezone": "Asia/Shanghai",
    }
    values.update(changes)
    return values


async def resolved_context():
    return await Pilot001OwnerBindingResolver(config()).resolve(assertion())


async def test_p0r_a_owner_binding_returns_authoritative_actor_and_workspace():
    context = await resolved_context()

    assert context.actor_id == ACTOR_ID
    assert context.workspace.tenant_id == "tenant-a"
    assert context.workspace.workspace_id == "workspace-a"
    assert context.workspace.namespace == "business"
    assert context.workspace.user_id == context.actor_id
    assert context.binding_type == BINDING_TYPE


@pytest.mark.parametrize(
    "changes",
    [
        {"channel_identity": "wrong-owner"},
        {"channel": "telegram"},
        {"shell": "other-shell"},
        {"channel_identity": ""},
    ],
)
async def test_p0r_bcd_binding_mismatch_fails_closed(changes):
    resolver = Pilot001OwnerBindingResolver(config())

    with pytest.raises(FailureException) as caught:
        await resolver.resolve(assertion(**changes))

    assert caught.value.failure.code == "pilot_001.binding_denied"
    assert caught.value.failure.category == ErrorCategory.PERMISSION_DENIED
    assert OWNER_ID not in caught.value.failure.message


async def test_p0r_e_missing_or_unsafe_binding_config_fails_closed():
    with pytest.raises(FailureException) as missing:
        Pilot001AuthorityConfig.from_environment({})
    assert missing.value.failure.code == "pilot_001.binding_config_missing"

    unsafe = pilot_environment()
    unsafe["AI_LAB_PILOT_001_ACTOR_ID"] = OWNER_ID
    with pytest.raises(FailureException) as raw_actor:
        Pilot001AuthorityConfig.from_environment(unsafe)
    assert raw_actor.value.failure.code == "pilot_001.raw_owner_actor_denied"


async def test_p0r_f_binding_evidence_is_deterministic_and_redacted():
    first = config()
    second = Pilot001AuthorityConfig.from_environment(pilot_environment())

    assert first.binding_evidence_id == second.binding_evidence_id
    assert first.binding_evidence_id.startswith("pilot001_binding_")
    assert OWNER_ID not in first.binding_evidence_id
    assert OWNER_ID not in repr(first)


async def test_p0r_gk_policy_is_exact_and_ai_lab_authoritative():
    plan = await Pilot001OperationPolicyResolver().resolve(
        context=await resolved_context(),
        requested_operation=ALLOWED_OPERATION,
        parameters=parameters(),
        trace_id="trace-a",
    )

    assert plan.canonical_operation == ALLOWED_OPERATION
    assert plan.policy_reference == POLICY_REFERENCE
    assert plan.risk_level == RISK_LEVEL
    assert plan.requires_confirmation is True
    assert plan.requires_approval is False
    assert plan.canonical_commit_required is True
    assert plan.expected_external_effects == ()
    assert plan.preview_ttl_seconds == PREVIEW_TTL_SECONDS
    assert plan.normalized_parameters == {
        "title": "跟进测试客户护发精油报价",
        "description": "跟进 5000 盒护发精油报价",
        "priority": "high",
        "due_at": "2026-08-13T07:00:00+00:00",
        "timezone": "Asia/Shanghai",
        "source": FIXED_SOURCE,
    }


@pytest.mark.parametrize("operation", ["user_task.update", "quote.create", ""])
async def test_p0r_h_all_other_operations_are_denied(operation):
    with pytest.raises(FailureException) as caught:
        await Pilot001OperationPolicyResolver().resolve(
            context=await resolved_context(),
            requested_operation=operation,
            parameters=parameters(),
            trace_id="trace-a",
        )
    assert caught.value.failure.code == "pilot_001.operation_denied"


@pytest.mark.parametrize(
    "field",
    [
        "task_id",
        "source",
        "actor_id",
        "workspace",
        "tenant_id",
        "policy_reference",
        "risk_level",
        "requires_confirmation",
        "requires_approval",
        "canonical_commit_required",
        "status",
        "revision",
        "metadata.interaction_id",
    ],
)
async def test_p0r_i_authority_field_injection_is_denied(field):
    injected = parameters()
    injected[field] = "caller-value"

    with pytest.raises(FailureException) as caught:
        await Pilot001OperationPolicyResolver().resolve(
            context=await resolved_context(),
            requested_operation=ALLOWED_OPERATION,
            parameters=injected,
            trace_id="trace-a",
        )
    assert caught.value.failure.code == "pilot_001.authority_field_denied"


@pytest.mark.parametrize(
    "invalid",
    [
        {"title": "   "},
        {"priority": "normal"},
        {"due_at": "2026-08-13T15:00:00"},
        {"due_at": "明天下午三点"},
        {"timezone": "Mars/Olympus"},
        {"description": None},
    ],
)
async def test_p0r_j_canonical_parameter_validation(invalid):
    with pytest.raises(FailureException) as caught:
        await Pilot001OperationPolicyResolver().resolve(
            context=await resolved_context(),
            requested_operation=ALLOWED_OPERATION,
            parameters=parameters(**invalid),
            trace_id="trace-a",
        )
    assert caught.value.failure.code == "pilot_001.parameters_invalid"
    assert caught.value.failure.category == ErrorCategory.VALIDATION


async def test_p0r_j_missing_strict_parameter_is_denied():
    incomplete = parameters()
    incomplete.pop("description")

    with pytest.raises(FailureException) as caught:
        await Pilot001OperationPolicyResolver().resolve(
            context=await resolved_context(),
            requested_operation=ALLOWED_OPERATION,
            parameters=incomplete,
            trace_id="trace-a",
        )
    assert caught.value.failure.code == "pilot_001.parameters_incomplete"


async def test_p0r_l_generic_mcp_default_remains_fail_closed(tmp_path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    try:
        server = build_mcp_server(TrustedInteractionAdapter(system.interaction_service))
        result = await server.call_tool(
            "ai_lab_interaction_preview",
            {
                "assertion": assertion().model_dump(mode="json"),
                "requested_operation": ALLOWED_OPERATION,
                "parameters": parameters(),
                "idempotency_key": "generic-fail-closed",
            },
        )
        assert result.structured_content["failure"]["code"] == (
            "interaction_adapter.identity_binding_unavailable"
        )
    finally:
        await system.shutdown()


async def test_p0r_mnq_pilot_composition_injects_only_authorities(tmp_path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    try:
        adapter = build_pilot_001_adapter(
            system.interaction_service, pilot_environment()
        )
        assert isinstance(adapter._bindings, Pilot001OwnerBindingResolver)
        assert isinstance(adapter._policies, Pilot001OperationPolicyResolver)
        assert isinstance(system.interaction_service._execution_port, DisabledExecutionPort)
        assert isinstance(
            system.interaction_service._verification_port, DisabledVerificationPort
        )
        assert isinstance(
            system.interaction_service._canonical_commit_authority,
            DisabledCanonicalCommitAuthority,
        )
        assert isinstance(
            system.interaction_service._approval_authority, DisabledApprovalAuthority
        )
        assert system.coordination_runtime is None
        server = build_mcp_server(adapter)
        assert tuple(tool.name for tool in await server.list_tools()) == TOOL_NAMES
    finally:
        await system.shutdown()


async def test_p0r_op_preview_writes_canonical_facts_but_no_user_task(tmp_path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    try:
        adapter = build_pilot_001_adapter(
            system.interaction_service, pilot_environment()
        )
        context = await resolved_context()
        before = await system.user_task_service.list(
            workspace_key=context.workspace, query=UserTaskQuery()
        )
        response = await adapter.preview(
            assertion=assertion(),
            requested_operation=ALLOWED_OPERATION,
            parameters=parameters(),
            idempotency_key="pilot-preview-a",
        )
        after = await system.user_task_service.list(
            workspace_key=context.workspace, query=UserTaskQuery()
        )
        audit = await system.interaction_service.audit(
            workspace=context.workspace,
            actor_id=context.actor_id,
            interaction_id=response.interaction_id,
        )

        assert response.failure is None
        assert response.authoritative is True
        assert response.lifecycle_state == "AWAITING_CONFIRMATION"
        assert response.preview.normalized_parameters["source"] == FIXED_SOURCE
        assert response.preview.expected_external_effects == ()
        assert len(audit) >= 3
        assert before == after == []
    finally:
        await system.shutdown()


async def test_no_new_event_replay_is_not_distinguishable_from_fresh_ingress(tmp_path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    try:
        adapter = build_pilot_001_adapter(
            system.interaction_service, pilot_environment()
        )
        first = await adapter.preview(
            assertion=assertion(),
            requested_operation=ALLOWED_OPERATION,
            parameters=parameters(),
            idempotency_key="controlled-replay-a",
        )
        replay = await adapter.preview(
            assertion=assertion(),
            requested_operation=ALLOWED_OPERATION,
            parameters=parameters(),
            idempotency_key="controlled-replay-b",
        )

        assert first.failure is None
        assert replay.failure is None
        assert replay.interaction_id != first.interaction_id
        assert replay.preview.normalized_parameters == first.preview.normalized_parameters
    finally:
        await system.shutdown()


async def test_p0r_real_stdio_entrypoint_negotiates_and_previews(tmp_path):
    environment = os.environ.copy()
    environment.update(pilot_environment())
    environment.update(
        {
            "AI_LAB_PROVIDER_MODE": "mock",
            "AI_LAB_DATA_DIR": str(tmp_path / "data"),
            "AI_LAB_SQLITE_DIR": str(tmp_path / "data" / "sqlite"),
            "OPENAI_API_KEY": "DISABLED",
            "AI_LAB_LLM_API_KEY": "DISABLED",
            "DEEPSEEK_API_KEY": "DISABLED",
        }
    )
    environment.pop("AI_LAB_ALLOW_REAL_PROVIDER_TESTS", None)
    server = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "applications.trusted_interaction_adapter.pilot_001_mcp_server",
        ],
        env=environment,
        cwd=str(Path(__file__).resolve().parents[3]),
    )

    async with (
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert tuple(tool.name for tool in tools.tools) == TOOL_NAMES
        result = await session.call_tool(
            "ai_lab_interaction_preview",
            {
                "assertion": assertion().model_dump(mode="json"),
                "requested_operation": ALLOWED_OPERATION,
                "parameters": parameters(),
                "idempotency_key": "stdio-preview-a",
            },
        )
        assert result.is_error is False
        assert result.structured_content["authoritative"] is True
        assert result.structured_content["preview"]["normalized_parameters"]["source"] == (
            FIXED_SOURCE
        )
