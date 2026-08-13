"""Exact four-tool MCP surface for the P1A internal trusted-host pilot."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from applications.pilot_001_ingress_bridge.crypto import PilotIngressKeys
from applications.pilot_001_ingress_bridge.service import (
    Pilot001IngressConfirmationService,
    PilotIngressAuthority,
)
from applications.trusted_interaction_adapter.pilot_001_mcp_server import (
    build_pilot_001_adapter,
)
from core.errors import FailureException

PILOT_TOOL_NAMES = (
    "ai_lab_interaction_preview",
    "ai_lab_interaction_status",
    "ai_lab_interaction_view",
    "ai_lab_interaction_confirm",
)


def _denied(exc: FailureException) -> dict[str, object]:
    return {
        "authoritative": True,
        "failure": exc.failure.model_dump(mode="json"),
        "final": False,
    }


def build_p1a_mcp_server(
    pilot: Pilot001IngressConfirmationService,
) -> MCPServer:
    server = MCPServer(
        name="ai-lab-pilot-001-p1a",
        title="AI-Lab PILOT-001 Internal Confirmation",
        description=(
            "Internal trusted-host pilot; tool completion is never business success"
        ),
        version="pilot-001-p1a/v1",
    )

    @server.tool(name=PILOT_TOOL_NAMES[0], structured_output=True)
    async def interaction_preview(
        parameters: dict[str, Any], idempotency_key: str,
    ) -> dict[str, Any]:
        return await pilot.preview(parameters=parameters, idempotency_key=idempotency_key)

    @server.tool(name=PILOT_TOOL_NAMES[1], structured_output=True)
    async def interaction_status(interaction_id: str) -> dict[str, Any]:
        try:
            response = await pilot._adapter.status(
                assertion=pilot.assertion(), interaction_id=interaction_id
            )
            return response.model_dump(mode="json")
        except FailureException as exc:
            return _denied(exc)

    @server.tool(name=PILOT_TOOL_NAMES[2], structured_output=True)
    async def interaction_view(interaction_id: str) -> dict[str, Any]:
        try:
            response = await pilot._adapter.view(
                assertion=pilot.assertion(), interaction_id=interaction_id
            )
            return response.model_dump(mode="json")
        except FailureException as exc:
            return _denied(exc)

    @server.tool(name=PILOT_TOOL_NAMES[3], structured_output=True)
    async def interaction_confirm(
        interaction_id: str,
        expected_revision: int,
        evidence_id: str,
        confirmation_text: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        try:
            return await pilot.confirm(
                interaction_id=interaction_id,
                expected_revision=expected_revision,
                evidence_id=evidence_id,
                confirmation_text=confirmation_text,
                idempotency_key=idempotency_key,
            )
        except FailureException as exc:
            return _denied(exc)

    return server


def build_p1a_service(system, environ: dict[str, str] | None = None):
    source = os.environ if environ is None else environ
    adapter = build_pilot_001_adapter(system.interaction_service, source)
    required = {
        "account": source.get("AI_LAB_PILOT_001_CHANNEL_ACCOUNT_ID", ""),
        "owner": source.get("AI_LAB_PILOT_001_OWNER_CHANNEL_IDENTITY", ""),
        "conversation": source.get("AI_LAB_PILOT_001_CONVERSATION_ID", ""),
    }
    if any(not value.strip() for value in required.values()):
        raise RuntimeError("P1A account, Owner, and conversation bindings are required")
    keys = PilotIngressKeys(Path(source["AI_LAB_DATA_DIR"]) / "pilot-001" / "trusted-ingress")
    return Pilot001IngressConfirmationService(
        adapter=adapter,
        interactions=system.interaction_service,
        keys=keys,
        authority=PilotIngressAuthority(
            raw_account_id=required["account"],
            raw_owner_id=required["owner"],
            raw_conversation_id=required["conversation"],
        ),
    )


async def _serve_stdio() -> None:
    from core.system import create_system, load_system_settings

    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        await build_p1a_mcp_server(build_p1a_service(system)).run_stdio_async()
    finally:
        await system.shutdown()


def main() -> None:
    asyncio.run(_serve_stdio())


if __name__ == "__main__":
    main()
