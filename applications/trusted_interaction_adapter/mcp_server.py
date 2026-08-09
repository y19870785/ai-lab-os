"""Standards-compliant local stdio MCP projection for trusted interactions."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.mcpserver import MCPServer

from applications.trusted_interaction_adapter.models import (
    AdapterResponse,
    ShellAssertion,
)
from applications.trusted_interaction_adapter.service import TrustedInteractionAdapter

TOOL_NAMES = (
    "ai_lab_interaction_preview",
    "ai_lab_interaction_modify",
    "ai_lab_interaction_confirm",
    "ai_lab_interaction_cancel",
    "ai_lab_interaction_status",
    "ai_lab_interaction_view",
    "ai_lab_interaction_recover",
)


def _wire(response: AdapterResponse) -> dict[str, Any]:
    """Serialize the adapter contract without reinterpreting canonical status."""

    return response.model_dump(mode="json")


def build_mcp_server(adapter: TrustedInteractionAdapter) -> MCPServer:
    """Bind the transport projection to an injected Shell-neutral adapter."""

    server = MCPServer(
        name="ai-lab-trusted-interaction",
        title="AI-Lab Trusted Interaction",
        description=(
            "Shell-neutral projection of AI-Lab canonical trusted interactions; "
            "tool completion is not proof of business success"
        ),
        version="trusted-interaction/v1",
    )

    @server.tool(name=TOOL_NAMES[0], structured_output=True)
    async def interaction_preview(
        assertion: ShellAssertion,
        requested_operation: str,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Create a canonical zero-external-side-effect Preview."""

        return _wire(
            await adapter.preview(
                assertion=assertion,
                requested_operation=requested_operation,
                parameters=parameters,
                idempotency_key=idempotency_key,
            )
        )

    @server.tool(name=TOOL_NAMES[1], structured_output=True)
    async def interaction_modify(
        assertion: ShellAssertion,
        interaction_id: str,
        expected_revision: int,
        requested_operation: str,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Replace a canonical Preview and invalidate prior consent."""

        return _wire(
            await adapter.modify(
                assertion=assertion,
                interaction_id=interaction_id,
                expected_revision=expected_revision,
                requested_operation=requested_operation,
                parameters=parameters,
                idempotency_key=idempotency_key,
            )
        )

    @server.tool(name=TOOL_NAMES[2], structured_output=True)
    async def interaction_confirm(
        assertion: ShellAssertion,
        interaction_id: str,
        preview_id: str,
        preview_revision: int,
        expected_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Confirm one exact canonical Preview revision."""

        return _wire(
            await adapter.confirm(
                assertion=assertion,
                interaction_id=interaction_id,
                preview_id=preview_id,
                preview_revision=preview_revision,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
        )

    @server.tool(name=TOOL_NAMES[3], structured_output=True)
    async def interaction_cancel(
        assertion: ShellAssertion,
        interaction_id: str,
        expected_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Cancel only while canonical cancellation is safe."""

        return _wire(
            await adapter.cancel(
                assertion=assertion,
                interaction_id=interaction_id,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
        )

    @server.tool(name=TOOL_NAMES[4], structured_output=True)
    async def interaction_status(
        assertion: ShellAssertion, interaction_id: str
    ) -> dict[str, Any]:
        """Read canonical status; never infer success from transport completion."""

        return _wire(
            await adapter.status(assertion=assertion, interaction_id=interaction_id)
        )

    @server.tool(name=TOOL_NAMES[5], structured_output=True)
    async def interaction_view(
        assertion: ShellAssertion, interaction_id: str
    ) -> dict[str, Any]:
        """Read the canonical safe view and available operations."""

        return _wire(
            await adapter.view(assertion=assertion, interaction_id=interaction_id)
        )

    @server.tool(name=TOOL_NAMES[6], structured_output=True)
    async def interaction_recover(
        assertion: ShellAssertion,
        interaction_id: str,
        expected_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Invoke canonical recovery without re-executing an external action."""

        return _wire(
            await adapter.recover(
                assertion=assertion,
                interaction_id=interaction_id,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
            )
        )

    return server


async def _serve_stdio() -> None:
    from core.system import create_system, load_system_settings

    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        adapter = TrustedInteractionAdapter(system.interaction_service)
        await build_mcp_server(adapter).run_stdio_async()
    finally:
        await system.shutdown()


def main() -> None:
    asyncio.run(_serve_stdio())


if __name__ == "__main__":
    main()
