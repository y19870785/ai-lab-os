"""PILOT-001 P1A internal trusted-host confirmation acceptance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from applications.pilot_001_ingress_bridge.crypto import PilotIngressKeys
from applications.pilot_001_ingress_bridge.launcher import (
    build_gateway_command,
    enforce_model_tool_profile,
    prepare_temporary_project,
)
from applications.pilot_001_ingress_bridge.mcp_server import (
    PILOT_TOOL_NAMES,
    build_p1a_mcp_server,
)
from applications.pilot_001_ingress_bridge.models import ENVELOPE_FIELDS
from applications.pilot_001_ingress_bridge.service import (
    Pilot001IngressConfirmationService,
    PilotIngressAuthority,
)
from applications.trusted_interaction_adapter.pilot_001_mcp_server import (
    build_pilot_001_adapter,
)
from core.errors import FailureException
from core.system import create_system, make_test_settings
from core.user_tasks.models import UserTaskQuery

pytestmark = pytest.mark.asyncio(loop_scope="function")

OWNER = "owner-secret"
ACCOUNT = "bot-secret"
CONVERSATION = "owner-dm-secret"


def environment(data_dir) -> dict[str, str]:
    return {
        "AI_LAB_PILOT_001_MODE": "internal_trusted_ingress_confirmation",
        "AI_LAB_PILOT_001_EXPECTED_SHELL": "hermes",
        "AI_LAB_PILOT_001_EXPECTED_CHANNEL": "wecom",
        "AI_LAB_PILOT_001_OWNER_CHANNEL_IDENTITY": OWNER,
        "AI_LAB_PILOT_001_ACTOR_ID": "pilot-owner",
        "AI_LAB_PILOT_001_TENANT_ID": "tenant",
        "AI_LAB_PILOT_001_WORKSPACE_ID": "workspace",
        "AI_LAB_PILOT_001_NAMESPACE": "business",
        "AI_LAB_PILOT_001_CHANNEL_ACCOUNT_ID": ACCOUNT,
        "AI_LAB_PILOT_001_CONVERSATION_ID": CONVERSATION,
        "AI_LAB_DATA_DIR": str(data_dir),
    }


def parameters() -> dict[str, object]:
    return {
        "title": "跟进测试客户的 5000 盒护发精油报价",
        "description": "内部可信入站确认 Pilot",
        "priority": "high",
        "due_at": "2026-08-14T15:00:00+08:00",
        "timezone": "Asia/Shanghai",
    }


async def composition(tmp_path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    env = environment(tmp_path)
    keys = PilotIngressKeys.bootstrap(tmp_path)
    service = Pilot001IngressConfirmationService(
        adapter=build_pilot_001_adapter(system.interaction_service, env),
        interactions=system.interaction_service,
        keys=keys,
        authority=PilotIngressAuthority(ACCOUNT, OWNER, CONVERSATION),
    )
    return system, service, keys


async def test_p1a_a_default_plugin_absent(tmp_path):
    from pathlib import Path

    assert not Path(".hermes/plugins/platforms/wecom").exists()


async def test_p1a_b_exact_mcp_tools(tmp_path):
    system, service, _ = await composition(tmp_path)
    try:
        tools = await build_p1a_mcp_server(service).list_tools()
        assert tuple(tool.name for tool in tools) == PILOT_TOOL_NAMES
        assert PILOT_TOOL_NAMES == (
            "ai_lab_interaction_preview",
            "ai_lab_interaction_status",
            "ai_lab_interaction_view",
            "ai_lab_interaction_confirm",
        )
    finally:
        await system.shutdown()


async def test_p1a_b_c_actual_hermes_names_are_exact_and_process_free():
    enforce_model_tool_profile(
        [f"mcp__ai_lab_p1a__{name}" for name in PILOT_TOOL_NAMES]
    )
    with pytest.raises(RuntimeError, match="TOOL_ISOLATION_UNPROVEN"):
        enforce_model_tool_profile(
            [f"mcp__ai_lab_p1a__{name}" for name in PILOT_TOOL_NAMES] + ["terminal"]
        )


async def test_p1a_c_temporary_nested_plugin_is_explicitly_enabled(tmp_path):
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    (source_home / "config.yaml").write_text(
        "platforms:\n  wecom:\n    enabled: true\n",
        encoding="utf-8",
    )
    project = prepare_temporary_project(
        source_hermes_home=source_home,
        mcp_command=["python", "-m", "pilot_mcp"],
        root=tmp_path / "ai-lab-pilot-001-p1a-profile",
    )
    config = __import__("yaml").safe_load(
        (project / ".hermes-home" / "config.yaml").read_text(encoding="utf-8")
    )
    assert config["plugins"]["enabled"] == ["platforms/wecom"]
    assert (project / ".hermes/plugins/platforms/wecom/plugin.yaml").is_file()


async def test_p1a_c_temporary_gateway_bypasses_service_refresh():
    assert build_gateway_command("/opt/hermes/venv/bin/python") == [
        "/opt/hermes/venv/bin/python",
        "-m",
        "gateway.run",
    ]
    assert "hermes" not in build_gateway_command("/opt/hermes/venv/bin/python")[1:]


async def test_p1a_d_body_msgid_only_and_stable_identity(tmp_path):
    _, _, keys = await composition(tmp_path)
    with pytest.raises(ValueError, match="channel_event_id_unavailable"):
        keys.issue(
            raw_account_id=ACCOUNT,
            raw_owner_id=OWNER,
            raw_conversation_id=CONVERSATION,
            raw_wecom_msgid="",
            text="确认 X",
        )
    first = keys.issue(
        raw_account_id=ACCOUNT,
        raw_owner_id=OWNER,
        raw_conversation_id=CONVERSATION,
        raw_wecom_msgid="msg-a",
        text="first",
    )
    second = keys.issue(
        raw_account_id=ACCOUNT,
        raw_owner_id=OWNER,
        raw_conversation_id=CONVERSATION,
        raw_wecom_msgid="msg-a",
        text="different",
        received_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert first.evidence_id == second.evidence_id
    assert tuple(type(first).model_fields) == ENVELOPE_FIELDS


async def test_p1a_e_to_m_confirmation_is_fresh_atomic_single_use_and_no_mutation(tmp_path):
    system, service, keys = await composition(tmp_path)
    try:
        context = await service._adapter._resolve(service.assertion())
        before = await system.user_task_service.list(
            workspace_key=context.workspace, query=UserTaskQuery()
        )
        preview = await service.preview(parameters=parameters(), idempotency_key="message-a")
        challenge = preview["preview_confirmation_challenge"]
        confirmation_text = f"确认 {challenge}"
        no_evidence = await build_p1a_mcp_server(service).call_tool(
            "ai_lab_interaction_confirm",
            {
                "interaction_id": preview["interaction_id"],
                "expected_revision": preview["revision"],
                "evidence_id": "tie_model_forged",
                "confirmation_text": confirmation_text,
                "idempotency_key": "no-evidence",
            },
        )
        assert no_evidence.structured_content["failure"]["code"] == (
            "trusted_confirmation.evidence_missing"
        )
        envelope = keys.issue(
            raw_account_id=ACCOUNT,
            raw_owner_id=OWNER,
            raw_conversation_id=CONVERSATION,
            raw_wecom_msgid="message-b-msgid",
            text=confirmation_text,
        )
        await service.accept_evidence(envelope)
        confirmed = await service.confirm(
            interaction_id=preview["interaction_id"],
            expected_revision=preview["revision"],
            evidence_id=envelope.evidence_id,
            confirmation_text=confirmation_text,
            idempotency_key="message-b",
        )
        assert confirmed["lifecycle_state"] == "AUTHORIZED"
        assert confirmed["execution_status"] == "NOT_STARTED"
        record = await system.interaction_repository.trusted_ingress_evidence(
            envelope.evidence_id
        )
        assert record["consumption_status"] == "CONSUMED"
        replay = await build_p1a_mcp_server(service).call_tool(
            "ai_lab_interaction_confirm",
            {
                "interaction_id": preview["interaction_id"],
                "expected_revision": preview["revision"],
                "evidence_id": envelope.evidence_id,
                "confirmation_text": confirmation_text,
                "idempotency_key": "replay",
            },
        )
        assert replay.structured_content["failure"] is not None
        after = await system.user_task_service.list(
            workspace_key=context.workspace, query=UserTaskQuery()
        )
        assert before == after == []
    finally:
        await system.shutdown()


@pytest.mark.parametrize(
    "changed",
    ["owner", "conversation", "text"],
)
async def test_p1a_i_wrong_binding_or_challenge_denied(tmp_path, changed):
    system, service, keys = await composition(tmp_path)
    try:
        preview = await service.preview(parameters=parameters(), idempotency_key="preview")
        expected_text = f"确认 {preview['preview_confirmation_challenge']}"
        owner = "wrong" if changed == "owner" else OWNER
        conversation = "wrong" if changed == "conversation" else CONVERSATION
        text = "确认 WRONG" if changed == "text" else expected_text
        envelope = keys.issue(
            raw_account_id=ACCOUNT,
            raw_owner_id=owner,
            raw_conversation_id=conversation,
            raw_wecom_msgid=f"msg-{changed}",
            text=text,
        )
        if changed in {"owner", "conversation"}:
            with pytest.raises(FailureException):
                await service.accept_evidence(envelope)
        else:
            await service.accept_evidence(envelope)
            with pytest.raises(FailureException):
                await service.confirm(
                    interaction_id=preview["interaction_id"],
                    expected_revision=preview["revision"],
                    evidence_id=envelope.evidence_id,
                    confirmation_text=expected_text,
                    idempotency_key="wrong",
                )
    finally:
        await system.shutdown()


async def test_p1a_k_consumption_survives_ai_lab_restart(tmp_path):
    system, service, keys = await composition(tmp_path)
    preview = await service.preview(parameters=parameters(), idempotency_key="restart-a")
    confirmation_text = f"确认 {preview['preview_confirmation_challenge']}"
    envelope = keys.issue(
        raw_account_id=ACCOUNT,
        raw_owner_id=OWNER,
        raw_conversation_id=CONVERSATION,
        raw_wecom_msgid="restart-message-b",
        text=confirmation_text,
    )
    await service.accept_evidence(envelope)
    await service.confirm(
        interaction_id=preview["interaction_id"],
        expected_revision=preview["revision"],
        evidence_id=envelope.evidence_id,
        confirmation_text=confirmation_text,
        idempotency_key="restart-b",
    )
    await system.shutdown()

    restarted, _, _ = await composition(tmp_path)
    try:
        record = await restarted.interaction_repository.trusted_ingress_evidence(
            envelope.evidence_id
        )
        assert record["consumption_status"] == "CONSUMED"
        assert record["consumed_interaction_id"] == preview["interaction_id"]
    finally:
        await restarted.shutdown()


async def test_p1a_d_plugin_has_no_msgid_fallback():
    from pathlib import Path

    source = Path(
        "applications/pilot_001_ingress_bridge/plugin_template/platforms/wecom/adapter.py"
    ).read_text(encoding="utf-8")
    assert 'body.get("msgid")' in source
    assert "req_id" not in source
    assert "uuid" not in source
