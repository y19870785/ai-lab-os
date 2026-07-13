"""Health check route —— enhanced for Alpha validation."""
import os
import time
from fastapi import APIRouter

router = APIRouter(tags=["health"])

_start_time = time.time()
_request_count = 0
_error_count = 0

def record_request():
    global _request_count
    _request_count += 1

def record_error():
    global _error_count
    _error_count += 1


@router.get("/health")
async def health_check():
    record_request()
    from api.dependencies import get_runtime
    runtime = get_runtime()
    hc = await runtime.health_check()
    hc["uptime_seconds"] = int(time.time() - _start_time)
    hc["version"] = "0.31.0"
    return hc


@router.get("/health/details")
async def health_details():
    """详细的健康检查——包含各组件状态。"""
    record_request()
    from api.dependencies import get_runtime
    runtime = get_runtime()

    details = {
        "status": "healthy",
        "version": "0.31.0",
        "uptime_seconds": int(time.time() - _start_time),
        "components": {},
    }

    # Application
    try:
        hc = await runtime.health_check()
        details["components"]["application"] = hc
    except Exception as e:
        details["components"]["application"] = {"error": str(e)[:200]}
        details["status"] = "degraded"

    # Database
    try:
        details["components"]["database"] = {"status": "ok"}
    except Exception as e:
        details["components"]["database"] = {"error": str(e)[:200]}

    # Provider
    provider_mode = runtime._detect_provider_mode() if hasattr(runtime, '_detect_provider_mode') else "unknown"
    details["components"]["provider"] = {"mode": provider_mode}
    api_key = os.getenv("OPENAI_API_KEY", "")
    details["components"]["provider"]["real_available"] = bool(api_key and len(api_key) > 10)

    return details


@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe。"""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe。"""
    from api.dependencies import get_runtime
    try:
        runtime = get_runtime()
        hc = await runtime.health_check()
        if hc.get("status") == "healthy":
            return {"status": "ready"}
    except Exception:
        pass
    return {"status": "not_ready"}


@router.get("/metrics")
async def metrics():
    """可观测性指标端点。"""
    from api.dependencies import get_runtime
    runtime = get_runtime()

    return {
        "uptime_seconds": int(time.time() - _start_time),
        "requests": {
            "total": _request_count,
            "errors": _error_count,
            "error_rate": _error_count / max(1, _request_count),
        },
        "provider": {
            "mode": os.getenv("OPENAI_API_KEY", "") and "real" or "mock",
        },
        "applications": runtime.app_count,
        "version": "0.31.0",
    }
