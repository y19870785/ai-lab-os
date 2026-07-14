"""SystemContainer-backed health and metrics routes."""

import time

from fastapi import APIRouter, Depends

from api.dependencies import get_system
from core.system.container import SystemContainer

router = APIRouter(tags=["health"])
_start_time = time.time()
_request_count = 0
_error_count = 0


def record_request() -> None:
    global _request_count
    _request_count += 1


def record_error() -> None:
    global _error_count
    _error_count += 1


@router.get("/health")
async def health_check(system: SystemContainer = Depends(get_system)):
    record_request()
    result = await system.health()
    result.update({"uptime_seconds": int(time.time() - _start_time), "version": "0.32.4"})
    return result


@router.get("/health/details")
async def health_details(system: SystemContainer = Depends(get_system)):
    record_request()
    health = await system.health()
    return {
        "status": health["status"],
        "version": "0.32.4",
        "uptime_seconds": int(time.time() - _start_time),
        "components": health,
    }


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(system: SystemContainer = Depends(get_system)):
    health = await system.health()
    return {"status": "ready" if health["status"] == "healthy" else "not_ready"}


@router.get("/metrics")
async def metrics(system: SystemContainer = Depends(get_system)):
    return {
        "uptime_seconds": int(time.time() - _start_time),
        "requests": {
            "total": _request_count,
            "errors": _error_count,
            "error_rate": _error_count / max(1, _request_count),
        },
        "provider": {"mode": system.settings.provider_mode},
        "applications": system.application_registry.count,
        "version": "0.32.4",
    }
