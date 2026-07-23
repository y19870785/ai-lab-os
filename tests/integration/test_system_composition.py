"""Single Composition Root integration tests."""

from pathlib import Path

import pytest

from applications.models import ApplicationRequest
from core.memory.models import MemoryQuery, MemoryType
from core.system import create_system, make_test_settings
from core.system.exceptions import SystemInitializationError

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_create_start_and_shutdown_system(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()

    assert system.started is True
    assert system.memory_manager is not None
    assert system.application_runtime is not None
    assert system.ceo_assistant is not None
    assert (await system.health())["status"] == "healthy"

    await system.shutdown()
    await system.shutdown()
    assert system.started is False


async def test_ceo_assistant_is_registered_as_instance(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    try:
        instance = system.application_registry.get_instance_by_name("ceo-assistant")
        assert instance is system.ceo_assistant
    finally:
        await system.shutdown()


async def test_application_runtime_dispatches_real_ceo_instance(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    try:
        response = await system.application_runtime.execute(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="记录: 今天确认了统一组合根",
        ))
        memories = await system.memory_manager.retrieve_memory(
            MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=10)
        )
        assert response.status == "ok"
        assert "[mock] Echo" not in response.answer
        assert any(item.content.get("type") == "work_log" for item in memories)
    finally:
        await system.shutdown()


async def test_scheduler_lifecycle_is_owned_by_system(tmp_path: Path):
    settings = make_test_settings(tmp_path, enable_scheduler=True)
    system = await create_system(settings)
    await system.start()
    assert system.scheduler_runtime is not None
    assert await system.scheduler_runtime.health_check() is True
    await system.shutdown()
    assert await system.scheduler_runtime.health_check() is False


async def test_reminder_orchestrator_is_production_wired(tmp_path: Path):
    settings = make_test_settings(
        tmp_path, enable_scheduler=True, enable_reminders=True
    )
    system = await create_system(settings)
    await system.start()
    try:
        assert system.reminder_orchestrator is not None
        assert system.ceo_assistant._reminder_orchestrator is system.reminder_orchestrator
        assert system.reminder_inbox is not None
        assert system.ceo_assistant._reminder_inbox is system.reminder_inbox
        assert system.ceo_assistant._task_intent_parser is not None
        assert system.inbox_service._waiting_for is system.waiting_for_service
        assert system.ceo_assistant._waiting_for is system.waiting_for_service
    finally:
        await system.shutdown()


async def test_knowledge_can_be_explicitly_enabled(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path, enable_knowledge=True))
    await system.start()
    try:
        assert system.knowledge_manager is not None
        health = await system.health()
        assert health["components"]["knowledge"]["status"] == "healthy"
    finally:
        await system.shutdown()


async def test_partial_startup_failure_rolls_back_resources(tmp_path: Path, monkeypatch):
    system = await create_system(make_test_settings(tmp_path))

    async def fail_initialize():
        raise RuntimeError("provider startup failed")

    monkeypatch.setattr(system.llm_provider, "initialize", fail_initialize)
    with pytest.raises(SystemInitializationError, match="provider startup failed"):
        await system.start()

    assert system.started is False
    assert system.event_bus.is_running is False
