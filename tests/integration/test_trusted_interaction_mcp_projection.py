"""Integration evidence for the official MCP stdio projection contract."""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from applications.trusted_interaction_adapter import TrustedInteractionAdapter
from applications.trusted_interaction_adapter.mcp_server import (
    TOOL_NAMES,
    build_mcp_server,
)
from core.system import create_system, make_test_settings
from tests.helpers.interaction_adapter import (
    ReferenceOperationPolicyResolver,
    ReferenceShellBindingResolver,
    shell_assertion,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_mcp_tool_allowlist_is_exact_and_forbidden_authorities_absent(tmp_path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    server = build_mcp_server(TrustedInteractionAdapter(system.interaction_service))
    tools = await server.list_tools()
    names = tuple(tool.name for tool in tools)
    assert names == TOOL_NAMES
    assert not any(
        forbidden in name
        for name in names
        for forbidden in ("approve", "execute", "verify", "canonical_commit")
    )
    await system.shutdown()


async def test_mcp_tool_success_projects_fail_closed_business_result(tmp_path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    server = build_mcp_server(TrustedInteractionAdapter(system.interaction_service))
    result = await server.call_tool(
        "ai_lab_interaction_preview",
        {
            "assertion": {
                "channel": "reference-channel",
                "shell": "replaceable-shell",
                "shell_session_id": "session-1",
                "channel_identity": "untrusted-user",
                "message_id": "message-1",
                "correlation": {"request_id": "request-1", "trace_id": "trace-1"},
            },
            "requested_operation": "reference.noop",
            "parameters": {},
            "idempotency_key": "request-1",
        },
    )
    assert result.is_error is False
    assert result.structured_content["authoritative"] is False
    assert result.structured_content["final"] is False
    assert result.structured_content["failure"]["code"] == (
        "interaction_adapter.identity_binding_unavailable"
    )
    await system.shutdown()


async def test_official_stdio_entrypoint_discovers_exact_tools_and_fails_closed(
    tmp_path,
):
    environment = os.environ.copy()
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
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "applications.trusted_interaction_adapter.mcp_server"],
        env=environment,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert tuple(tool.name for tool in tools.tools) == TOOL_NAMES
        result = await session.call_tool(
            "ai_lab_interaction_preview",
            {
                "assertion": {
                    "channel": "reference-channel",
                    "shell": "replaceable-shell",
                    "shell_session_id": "session-1",
                    "channel_identity": "untrusted-user",
                    "message_id": "message-1",
                    "correlation": {
                        "request_id": "request-1",
                        "trace_id": "trace-1",
                    },
                },
                "requested_operation": "reference.noop",
                "parameters": {},
                "idempotency_key": "request-1",
            },
        )
        assert result.is_error is False
        assert result.structured_content["final"] is False
        assert result.structured_content["failure"]["code"] == (
            "interaction_adapter.identity_binding_unavailable"
        )


async def test_status_survives_restart_and_shell_replacement(tmp_path):
    settings = make_test_settings(tmp_path)
    binding = ReferenceShellBindingResolver()
    policy = ReferenceOperationPolicyResolver()
    first = await create_system(settings)
    await first.start()
    first_adapter = TrustedInteractionAdapter(
        first.interaction_service, binding, policy
    )
    previewed = await first_adapter.preview(
        assertion=shell_assertion(shell="shell-a"),
        requested_operation="reference.noop",
        parameters={"value": 1},
        idempotency_key="restart-1",
    )
    await first.shutdown()

    second = await create_system(settings)
    await second.start()
    second_adapter = TrustedInteractionAdapter(
        second.interaction_service, binding, policy
    )
    restored = await second_adapter.status(
        assertion=shell_assertion(shell="shell-b"),
        interaction_id=previewed.interaction_id,
    )
    assert restored.interaction_id == previewed.interaction_id
    assert restored.revision == previewed.revision
    assert restored.authoritative is True
    await second.shutdown()


async def test_adapter_has_no_database_repository_or_shell_private_dependency():
    import applications.trusted_interaction_adapter as package

    source = "\n".join(
        inspect.getsource(module)
        for module in (
            package,
            __import__(
                "applications.trusted_interaction_adapter.service", fromlist=["*"]
            ),
            __import__(
                "applications.trusted_interaction_adapter.projection", fromlist=["*"]
            ),
        )
    ).lower()
    assert "databasemanager" not in source
    assert "sqliteinteractionrepository" not in source
    assert "raw sql" not in source
    assert "hermes" not in source
