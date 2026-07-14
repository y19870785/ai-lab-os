"""CLI 对共享 Composition Root 的薄适配层。"""

from __future__ import annotations

from applications.models import ApplicationRequest, ApplicationResponse
from core.system import create_system, load_system_settings


async def execute_ceo_request(user_input: str) -> tuple[ApplicationResponse, str]:
    """Run one command through the same system factory used by API and interactive CLI."""

    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        response = await system.application_runtime.execute(ApplicationRequest(
            application_name="ceo-assistant",
            user_input=user_input,
        ))
        return response, settings.provider_mode
    finally:
        await system.shutdown()
