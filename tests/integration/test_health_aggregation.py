from pathlib import Path

import pytest

from core.errors import ErrorCategory, FailureInfo
from core.system import create_system, make_test_settings


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_unstarted_system_is_not_initialized(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path))
    health = await system.health()
    assert health["status"] == "not_initialized"
    assert health["components"] == {}


async def test_required_services_healthy_and_disabled_knowledge_does_not_degrade(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path, enable_knowledge=False))
    await system.start()
    try:
        health = await system.health()
        assert health["status"] == "healthy"
        assert health["components"]["knowledge"]["status"] == "disabled"
        assert health["components"]["provider"]["readiness"] == "ready"
    finally:
        await system.shutdown()


async def test_enabled_degraded_scheduler_degrades_top_level(tmp_path: Path, monkeypatch):
    system = await create_system(make_test_settings(tmp_path, enable_scheduler=True))
    await system.start()

    async def degraded_health():
        return {"status": "degraded", "running": True, "last_error": {"code": "scheduler.tick.failed"}}

    monkeypatch.setattr(system.scheduler_runtime, "health", degraded_health)
    try:
        health = await system.health()
        assert health["status"] == "degraded"
        assert health["components"]["scheduler"]["status"] == "degraded"
    finally:
        await system.shutdown()


async def test_known_memory_failure_fails_top_level_health(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    try:
        system.memory_manager.record_failure(FailureInfo(
            code="memory.write.failed",
            category=ErrorCategory.PERSISTENCE_FAILURE,
            message="memory write failed",
            component="memory",
            operation="save",
            retryable=True,
        ))
        health = await system.health()
        assert health["status"] == "failed"
        assert health["components"]["memory"]["last_error"]["code"] == "memory.write.failed"
    finally:
        await system.shutdown()
