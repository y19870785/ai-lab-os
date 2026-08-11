"""PILOT-001 Phase-0 preview-only stdio MCP composition."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping

from applications.trusted_interaction_adapter.mcp_server import build_mcp_server
from applications.trusted_interaction_adapter.pilot_001 import (
    Pilot001AuthorityConfig,
    Pilot001OperationPolicyResolver,
    Pilot001OwnerBindingResolver,
)
from applications.trusted_interaction_adapter.service import TrustedInteractionAdapter
from core.interaction import InteractionService


def build_pilot_001_adapter(
    interaction_service: InteractionService,
    environ: Mapping[str, str] | None = None,
) -> TrustedInteractionAdapter:
    """Inject the explicit Pilot authorities without changing generic defaults."""

    config = Pilot001AuthorityConfig.from_environment(
        os.environ if environ is None else environ
    )
    return TrustedInteractionAdapter(
        interaction_service,
        binding_resolver=Pilot001OwnerBindingResolver(config),
        policy_resolver=Pilot001OperationPolicyResolver(),
    )


async def _serve_stdio() -> None:
    from core.system import create_system, load_system_settings

    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        adapter = build_pilot_001_adapter(system.interaction_service)
        await build_mcp_server(adapter).run_stdio_async()
    finally:
        await system.shutdown()


def main() -> None:
    asyncio.run(_serve_stdio())


if __name__ == "__main__":
    main()
