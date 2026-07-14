"""FastAPI dependencies backed by the lifespan-owned SystemContainer."""

from fastapi import Depends, Request

from applications.runtime import ApplicationRuntime
from core.system.container import SystemContainer
from core.system.exceptions import ServiceUnavailableError


def get_system(request: Request) -> SystemContainer:
    system = getattr(request.app.state, "system", None)
    if system is None or not system.started:
        raise ServiceUnavailableError("AI-Lab system is not initialized")
    return system


def get_runtime(system: SystemContainer = Depends(get_system)) -> ApplicationRuntime:
    return system.application_runtime
