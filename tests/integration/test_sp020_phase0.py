"""SP-020 Phase 0 lifecycle, sustained-run, and restart evidence."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from core.system import create_system, make_test_settings
from core.system.exceptions import SystemInitializationError
from core.system.lifecycle import SystemLifecycleState
from core.workspace.models import WorkspaceKey

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_partial_start_rolls_back_and_failed_container_cannot_restart(
    tmp_path, monkeypatch
):
    system = await create_system(
        make_test_settings(
            tmp_path,
            enable_scheduler=True,
            enable_reminders=True,
            scheduler_tick_interval=0.05,
        )
    )

    async def fail_initialize():
        raise RuntimeError("injected application startup failure")

    monkeypatch.setattr(system.application_runtime, "initialize", fail_initialize)
    with pytest.raises(SystemInitializationError):
        await system.start()

    assert system.lifecycle_state == SystemLifecycleState.FAILED
    assert system.accepting_work is False
    assert system.database_manager.connection_count == 0
    assert system.event_bus.is_running is False
    assert (await system.scheduler_runtime.health())["running_jobs"] == 0
    assert system.scheduler_runtime._tick_task is None
    with pytest.raises(SystemInitializationError, match="cannot be restarted"):
        await system.start()


async def test_sustained_ticks_one_shot_idle_shutdown_and_restart(tmp_path):
    settings = make_test_settings(
        tmp_path,
        enable_scheduler=True,
        enable_reminders=True,
        scheduler_tick_interval=0.05,
    )
    workspace = WorkspaceKey(
        tenant_id="tenant",
        workspace_id="workspace",
        namespace="daily",
        session_id="session",
        agent_id="owner",
        trace_id="phase-0",
    )
    system = await create_system(settings)
    await system.start()
    started_at = datetime.now(UTC)
    task = await system.user_task_service.create(
        workspace_key=workspace,
        title="Phase 0 one-shot reminder",
    )
    reminder = await system.reminder_bridge.create(
        workspace_key=workspace,
        user_task_id=task.id,
        remind_at=datetime.now(UTC) + timedelta(milliseconds=120),
        timezone_name="UTC",
    )

    snapshots = []
    for _ in range(6):
        await asyncio.sleep(0.08)
        health = await system.health()
        snapshots.append({
            "at": datetime.now(UTC),
            "background_tasks": health["background_tasks"],
            "connection_count": health["database_connections"],
            "lifecycle": health["lifecycle"],
        })
    ended_at = datetime.now(UTC)
    stored = await system.reminder_service.get(reminder.id)
    occurrences = await system.reminder_service.list_occurrences(reminder.id)

    assert ended_at > started_at
    assert len(snapshots) >= 3
    assert all(item["lifecycle"] == "ready" for item in snapshots)
    assert all(item["connection_count"] > 0 for item in snapshots)
    assert stored.status.value == "triggered"
    assert len(occurrences) == 1

    await asyncio.gather(system.shutdown(), system.shutdown())
    await system.shutdown()
    assert system.lifecycle_state == SystemLifecycleState.STOPPED
    assert system.database_manager.connection_count == 0
    assert (await system.scheduler_runtime.health())["running_jobs"] == 0
    assert system.scheduler_runtime._tick_task is None

    restored = await create_system(settings)
    await restored.start()
    try:
        await asyncio.sleep(0.2)
        restored_reminder = await restored.reminder_service.get(reminder.id)
        restored_occurrences = await restored.reminder_service.list_occurrences(
            reminder.id
        )
        assert restored_reminder.status.value == "triggered"
        assert len(restored_occurrences) == 1
        assert (await restored.user_task_service.get(
            workspace_key=workspace,
            task_id=task.id,
        )).id == task.id
    finally:
        await restored.shutdown()
    assert restored.database_manager.connection_count == 0
