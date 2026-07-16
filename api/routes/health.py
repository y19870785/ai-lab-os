"""SystemContainer-backed health and metrics routes."""

import time

from fastapi import APIRouter, Depends, Request

from api.dependencies import get_system
from core.system.exceptions import ServiceUnavailableError
from core import __version__
from core.system.container import SystemContainer


def _system_unguarded(request: Request):
    s = getattr(request.app.state, "system", None)
    if s is None:
        raise ServiceUnavailableError("AI-Lab system is not initialized")
    return s

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
async def health_check(request: Request):
    system = _system_unguarded(request)
    record_request()
    result = await system.health()
    result.update({"uptime_seconds": int(time.time() - _start_time), "version": __version__})
    return result


@router.get("/health/details")
async def health_details(request: Request):
    system = _system_unguarded(request)
    record_request()
    health = await system.health()
    return {
        "status": health["status"],
        "version": __version__,
        "uptime_seconds": int(time.time() - _start_time),
        "components": health["components"],
    }


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(request: Request):
    system = _system_unguarded(request)
    health = await system.health()
    return {
        "status": "ready"
        if health.get("accepting_work", False)
        else "not_ready",
        "lifecycle": health.get("lifecycle", "unknown"),
        "accepting_work": health.get("accepting_work", False)
    }


@router.get("/metrics")
async def metrics(request: Request):
    system = _system_unguarded(request)
    return {
        "uptime_seconds": int(time.time() - _start_time),
        "requests": {
            "total": _request_count,
            "errors": _error_count,
            "error_rate": _error_count / max(1, _request_count),
        },
        "provider": {"mode": system.settings.provider_mode},
        "applications": system.application_registry.count,
        "version": __version__,
    }
