"""PILOT-001 P1A internal trusted-host confirmation acceptance."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from applications.pilot_001_ingress_bridge.crypto import (
    PilotIngressBindings,
    PilotIngressIssuerKeys,
    PilotIngressVerifierKeys,
)
from applications.pilot_001_ingress_bridge.launcher import (
    EXPECTED_MODEL_TOOL_NAMES,
    RUNTIME_EVIDENCE_ENV,
    build_gateway_command,
    enforce_model_tool_profile,
    prepare_temporary_project,
    run_pilot_gateway,
)
from applications.pilot_001_ingress_bridge.mcp_server import (
    PILOT_TOOL_NAMES,
    build_p1a_mcp_server,
    build_p1a_service,
)
from applications.pilot_001_ingress_bridge.models import (
    ENVELOPE_FIELDS,
    parse_envelope_json,
)
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
    verifier_root = data_dir / "pilot-001" / "trusted-ingress-verifier"
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
        "AI_LAB_PILOT_001_VERIFIER_ROOT": str(verifier_root),
    }


def key_roots(data_dir):
    return (
        data_dir / "pilot-001" / "trusted-ingress-issuer",
        data_dir / "pilot-001" / "trusted-ingress-verifier",
    )


def bootstrap_keys(data_dir):
    issuer_root, verifier_root = key_roots(data_dir)
    issuer = PilotIngressIssuerKeys.bootstrap(
        issuer_root=issuer_root,
        verifier_root=verifier_root,
    )
    return issuer, PilotIngressVerifierKeys(verifier_root)


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
    issuer_keys, verifier_keys = bootstrap_keys(tmp_path)
    service = Pilot001IngressConfirmationService(
        adapter=build_pilot_001_adapter(system.interaction_service, env),
        interactions=system.interaction_service,
        keys=verifier_keys,
        authority=PilotIngressAuthority(ACCOUNT, OWNER, CONVERSATION),
    )
    return system, service, issuer_keys, verifier_keys


async def test_p1a_a_default_plugin_absent(tmp_path):
    from pathlib import Path

    assert not Path(".hermes/plugins/platforms/wecom").exists()


async def test_p1a_b_exact_mcp_tools(tmp_path):
    system, service, _, _ = await composition(tmp_path)
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
    enforce_model_tool_profile(list(EXPECTED_MODEL_TOOL_NAMES))
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
    # P1B: the final Hermes Python process must harden itself via the
    # bootstrap module and only then enter gateway.run (no parent-only
    # hardening that would be reset across an exec boundary).
    command = build_gateway_command("/opt/hermes/venv/bin/python")
    assert command[0] == "/opt/hermes/venv/bin/python"
    assert command[1].endswith("process_isolation.py")
    assert command[2:] == ["--module", "gateway.run"]
    # The temporary gateway must still bypass the installed service unit path.
    assert "hermes" not in command[1:]


async def test_p1a_d_body_msgid_only_and_stable_identity(tmp_path):
    system, _, keys, _ = await composition(tmp_path)
    with pytest.raises(ValueError, match="channel_event_id_unavailable"):
        keys.issue(
            raw_wecom_msgid="",
            text="确认 X",
        )
    first = keys.issue(
        raw_wecom_msgid="msg-a",
        text="first",
    )
    second = keys.issue(
        raw_wecom_msgid="msg-b",
        text="first",
        received_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert first.evidence_id != second.evidence_id
    assert tuple(type(first).model_fields) == ENVELOPE_FIELDS
    assert first.evidence_version == "trusted-ingress-evidence/v1"
    assert first.channel_account_binding_id.startswith("acct_")
    assert first.owner_binding_id.startswith("owner_")
    assert first.conversation_binding_id.startswith("conv_")
    assert first.message_content_digest.startswith("hmac-sha256:")
    assert first.signature.startswith("ed25519:")
    await system.shutdown()


async def test_p1a_e_to_m_confirmation_is_fresh_atomic_single_use_and_no_mutation(tmp_path):
    system, service, keys, _ = await composition(tmp_path)
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
            raw_wecom_msgid="message-b-msgid",
            text=confirmation_text,
        )
        await service.accept_evidence(envelope.model_dump_json())
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
    system, service, keys, _ = await composition(tmp_path)
    try:
        preview = await service.preview(parameters=parameters(), idempotency_key="preview")
        expected_text = f"确认 {preview['preview_confirmation_challenge']}"
        text = "确认 WRONG" if changed == "text" else expected_text
        bindings = keys.bindings
        if changed == "owner":
            bindings = PilotIngressBindings(
                bindings.channel_account_binding_id,
                "owner_wrong",
                bindings.conversation_binding_id,
            )
        elif changed == "conversation":
            bindings = PilotIngressBindings(
                bindings.channel_account_binding_id,
                bindings.owner_binding_id,
                "conv_wrong",
            )
        envelope = keys.issue(
            raw_wecom_msgid=f"msg-{changed}",
            text=text,
            bindings=bindings,
        )
        if changed in {"owner", "conversation"}:
            with pytest.raises(FailureException):
                await service.accept_evidence(envelope.model_dump_json())
        else:
            await service.accept_evidence(envelope.model_dump_json())
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
    system, service, keys, _ = await composition(tmp_path)
    preview = await service.preview(parameters=parameters(), idempotency_key="restart-a")
    confirmation_text = f"确认 {preview['preview_confirmation_challenge']}"
    envelope = keys.issue(
        raw_wecom_msgid="restart-message-b",
        text=confirmation_text,
    )
    await service.accept_evidence(envelope.model_dump_json())
    await service.confirm(
        interaction_id=preview["interaction_id"],
        expected_revision=preview["revision"],
        evidence_id=envelope.evidence_id,
        confirmation_text=confirmation_text,
        idempotency_key="restart-b",
    )
    await system.shutdown()

    restarted, _, _, _ = await composition(tmp_path)
    try:
        record = await restarted.interaction_repository.trusted_ingress_evidence(
            envelope.evidence_id
        )
        assert record["consumption_status"] == "CONSUMED"
        assert record["consumed_interaction_id"] == preview["interaction_id"]
    finally:
        await restarted.shutdown()


async def test_p1a_n_verifier_cannot_mint_or_load_issuer_secrets(tmp_path):
    issuer, verifier = bootstrap_keys(tmp_path)
    issuer_root, verifier_root = key_roots(tmp_path)
    assert issuer.root == issuer_root
    assert verifier.root == verifier_root
    assert issuer.root != verifier.root
    assert {path.name for path in verifier.root.iterdir()} == {
        "bindings.json",
        "content_binding.key",
        "public_keys",
        "trusted_issuers.json",
    }
    assert not (verifier.root / "signing_private.key").exists()
    assert not (verifier.root / "event_identity.key").exists()
    assert not (verifier.root / "issuance.sqlite3").exists()
    assert not hasattr(verifier, "issue")
    assert not hasattr(verifier, "private_key")
    assert not hasattr(verifier, "event_identity_key")
    assert verifier.active_issuer_key_id == issuer.issuer_key_id
    assert ACCOUNT not in verifier.bindings.channel_account_binding_id
    assert OWNER not in verifier.bindings.owner_binding_id
    assert CONVERSATION not in verifier.bindings.conversation_binding_id
    mcp_source = __import__("pathlib").Path(
        "applications/pilot_001_ingress_bridge/mcp_server.py"
    ).read_text(encoding="utf-8")
    assert "PilotIngressIssuerKeys" not in mcp_source
    assert "signing_private.key" not in mcp_source
    assert "event_identity.key" not in mcp_source
    assert "AI_LAB_PILOT_001_VERIFIER_ROOT" in mcp_source
    assert "trusted-ingress\"" not in mcp_source
    runtime_source = __import__("pathlib").Path(
        "applications/pilot_001_ingress_bridge/runtime.py"
    ).read_text(encoding="utf-8")
    module_imports = runtime_source.split("def main()", 1)[0]
    assert "PilotIngressIssuerKeys" not in module_imports
    assert "pilot_001_ingress_bridge.issuer" not in module_imports
    assert runtime_source.index("if args.command == \"init-keys\":") < runtime_source.index(
        "PilotIngressIssuerKeys"
    )

    system = await create_system(make_test_settings(tmp_path / "runtime"))
    await system.start()
    try:
        runtime = build_p1a_service(system, environment(tmp_path))
        assert runtime._keys.root == verifier_root
        assert runtime._keys.root != issuer_root
        assert not hasattr(runtime._keys, "issue")
    finally:
        await system.shutdown()


async def test_p1a_v1_exact_wire_contract_rejects_noncanonical_inputs(tmp_path):
    issuer, _ = bootstrap_keys(tmp_path)
    envelope = issuer.issue(raw_wecom_msgid="wire-1", text="确认 A1B2-C3D4")
    wire = envelope.model_dump_json()
    assert parse_envelope_json(wire) == envelope

    decoded = json.loads(wire)
    invalid_values = (
        ("evidence_version", "1"),
        ("channel", "telegram"),
        ("event_type", "message"),
        ("received_at", decoded["received_at"].replace("Z", "+00:00")),
        ("message_content_digest", "tmc_not-v1"),
        ("signature", decoded["signature"].removeprefix("ed25519:")),
    )
    for field, value in invalid_values:
        changed = {**decoded, field: value}
        with pytest.raises(ValueError):
            parse_envelope_json(json.dumps(changed, separators=(",", ":")))

    with pytest.raises(ValueError, match="duplicate JSON field"):
        parse_envelope_json(wire[:-1] + ',"channel":"wecom"}')
    with pytest.raises(ValueError):
        parse_envelope_json(wire[:-1] + ',"unknown":"denied"}')
    missing = dict(decoded)
    missing.pop("event_type")
    with pytest.raises(ValueError):
        parse_envelope_json(json.dumps(missing, separators=(",", ":")))


async def test_p1a_o_duplicate_event_returns_original_envelope(tmp_path):
    issuer, _ = bootstrap_keys(tmp_path)
    first = issuer.issue(
        raw_wecom_msgid="redelivery", text="确认 A1B2-C3D4", received_at=datetime.now(UTC)
    )
    second = issuer.issue(
        raw_wecom_msgid="redelivery",
        text="确认 A1B2-C3D4",
        received_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    assert first.model_dump_json() == second.model_dump_json()
    with pytest.raises(ValueError, match="issuance identity conflict"):
        issuer.issue(raw_wecom_msgid="redelivery", text="确认 WRONG")


async def test_p1a_p_issuance_journal_restart_safe(tmp_path):
    first_issuer, _ = bootstrap_keys(tmp_path)
    first = first_issuer.issue(raw_wecom_msgid="journal-restart", text="确认 E5F6-A7B8")
    restarted_issuer = PilotIngressIssuerKeys(first_issuer.root)
    restarted = restarted_issuer.issue(
        raw_wecom_msgid="journal-restart",
        text="确认 E5F6-A7B8",
        received_at=datetime.now(UTC) + timedelta(minutes=2),
    )
    assert restarted.model_dump_json() == first.model_dump_json()


async def test_p1a_q_signing_key_rotation_returns_original_envelope(tmp_path):
    issuer_a, verifier = bootstrap_keys(tmp_path)
    issuer_root, verifier_root = key_roots(tmp_path)
    first = issuer_a.issue(raw_wecom_msgid="rotation-old", text="确认 A1B2-C3D4")
    verifier.verify(first)

    identity_before = (issuer_root / "event_identity.key").read_bytes()
    content_before = (issuer_root / "content_binding.key").read_bytes()
    bindings_before = (issuer_root / "bindings.json").read_bytes()
    journal_before = issuer_a._journal_path
    issuer_b = issuer_a.rotate_signing_key(verifier_root)

    assert issuer_b.issuer_key_id != issuer_a.issuer_key_id
    assert (issuer_root / "event_identity.key").read_bytes() == identity_before
    assert (issuer_root / "content_binding.key").read_bytes() == content_before
    assert (issuer_root / "bindings.json").read_bytes() == bindings_before
    assert issuer_b._journal_path == journal_before

    redelivery = issuer_b.issue(
        raw_wecom_msgid="rotation-old",
        text="确认 A1B2-C3D4",
        received_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    assert redelivery.model_dump_json() == first.model_dump_json()
    assert redelivery.issuer_key_id == issuer_a.issuer_key_id

    verifier.verify(first)
    new = issuer_b.issue(raw_wecom_msgid="rotation-new", text="确认 E5F6-A7B8")
    assert new.issuer_key_id == issuer_b.issuer_key_id
    verifier.verify(new)
    assert set(verifier.public_keys) == {
        issuer_a.issuer_key_id,
        issuer_b.issuer_key_id,
    }


async def test_p1a_runtime_startup_resolves_then_gates_before_gateway(
    tmp_path, monkeypatch
):
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    (source_home / "config.yaml").write_text(
        "platforms:\n  wecom:\n    enabled: true\n", encoding="utf-8"
    )
    calls: list[list[str]] = []
    gateway_pid = 4242

    class FakePopen:
        def __init__(self, command, **kwargs):
            self.command = list(command)
            self.pid = gateway_pid
            self.returncode = 0
            self._terminated = False
            calls.append(self.command)
            # Simulate evidence from the first target-module frame.
            evidence_path = kwargs.get("env", {}).get(RUNTIME_EVIDENCE_ENV)
            if evidence_path:
                evidence = {
                    "pid": gateway_pid,
                    "dumpable": 0,
                    "pr_get_dumpable": 0,
                    "stage": "module_started",
                    "module": "gateway.run",
                    "filename": str(tmp_path / "gateway" / "run.py"),
                }
                Path(evidence_path).write_text(
                    json.dumps(evidence, sort_keys=True), encoding="utf-8"
                )

        def wait(self, timeout=None):
            return self.returncode

        def poll(self):
            return None if not self._terminated else 0

        def terminate(self):
            self._terminated = True

        def kill(self):
            self._terminated = True

    def fake_run(command, **kwargs):
        calls.append(list(command))
        if command[-1].endswith("hermes_tool_probe.py"):
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps(EXPECTED_MODEL_TOOL_NAMES) + "\n"
            )
        if "--check" in command and any(
            part.endswith("process_isolation.py") for part in command
        ):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="PILOT_PROCESS_ISOLATION_EFFECTIVE PR_GET_DUMPABLE=0\n",
            )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        "applications.pilot_001_ingress_bridge.launcher.observe_kernel_dumpable",
        lambda pid: 0,
    )
    monkeypatch.setattr(
        "applications.pilot_001_ingress_bridge.launcher.validate_runtime_module_filename",
        lambda *args, **kwargs: tmp_path / "gateway" / "run.py",
    )
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    run_pilot_gateway(
        source_hermes_home=source_home,
        hermes_python="/opt/hermes/python",
        mcp_command=["python", "-m", "pilot_mcp"],
    )
    assert calls[0][-1].endswith("hermes_tool_probe.py")
    # P1B startup order: tool resolution -> exact-four gate -> hardening
    # link self-check -> hardened bootstrap gateway (final process hardens
    # itself before entering gateway.run; no parent-only hardening).
    assert "--check" in calls[1]
    assert any(part.endswith("process_isolation.py") for part in calls[1])
    # Actual runtime evidence: the final gateway command enters gateway.run
    # through the bootstrap, and the recorded PID matches the spawned one.
    assert calls[2][-1] == "gateway.run"
    assert calls[2][0] == "/opt/hermes/python"


async def test_p1a_runtime_startup_denies_namespace_drift(tmp_path, monkeypatch):
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    (source_home / "config.yaml").write_text("platforms: {}\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps([*EXPECTED_MODEL_TOOL_NAMES, "terminal"]) + "\n",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    with pytest.raises(RuntimeError, match="TOOL_ISOLATION_UNPROVEN"):
        run_pilot_gateway(
            source_hermes_home=source_home,
            hermes_python="/opt/hermes/python",
            mcp_command=["python", "-m", "pilot_mcp"],
        )
    assert len(calls) == 1


async def test_p1a_d_plugin_has_no_msgid_fallback():
    from pathlib import Path

    source = Path(
        "applications/pilot_001_ingress_bridge/plugin_template/platforms/wecom/adapter.py"
    ).read_text(encoding="utf-8")
    assert 'body.get("msgid")' in source
    assert "req_id" not in source
    assert "uuid" not in source
