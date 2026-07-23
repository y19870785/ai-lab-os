"""Canonical WorkLogService behavior and FailureInfo tests."""

from datetime import datetime, timezone
import hashlib

import pytest

from core.errors import FailureException
from core.system import create_system, make_test_settings
from core.work_log import WorkLogCreateCommand, WorkLogQuery, WorkLogSource
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock

NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_service_create_get_list_and_failure_contract(tmp_path):
    system = await create_system(
        make_test_settings(tmp_path, timezone_name="Asia/Shanghai"),
        clock=MutableClock(NOW),
    )
    await system.start()
    workspace = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    try:
        record = await system.work_log_service.create(
            workspace_key=workspace,
            command=WorkLogCreateCommand(
                subject="完成报价",
                raw_text="完成报价",
                source=WorkLogSource.API,
            ),
        )
        assert record.id.startswith("wl_") and len(record.id) == 35
        assert (
            await system.work_log_service.get(
                workspace_key=workspace, work_log_id=record.id
            )
        ) == record
        assert (
            await system.work_log_service.list(
                workspace_key=workspace, query=WorkLogQuery()
            )
        ).items == (record,)
        with pytest.raises(FailureException) as invalid:
            await system.work_log_service.get(
                workspace_key=workspace, work_log_id="raw-memory-id"
            )
        assert invalid.value.failure.code == "work_log.id_invalid"
        assert invalid.value.failure.trace_id == workspace.trace_id
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_inbox_id_is_deterministic_and_duplicate_safe(tmp_path):
    system = await create_system(
        make_test_settings(tmp_path), clock=MutableClock(NOW)
    )
    await system.start()
    workspace = WorkspaceKey()
    try:
        first = await system.work_log_service.create_from_inbox(
            workspace_key=workspace,
            inbox_item_id="inbox_source",
            subject="Inbox",
            raw_text="Inbox",
        )
        second = await system.work_log_service.create_from_inbox(
            workspace_key=workspace,
            inbox_item_id="inbox_source",
            subject="Inbox",
            raw_text="Inbox",
        )
        assert first == second
        assert first.id.startswith("wl_")
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_historical_inbox_alias_recovers_and_projects_one_legacy_object(
    tmp_path,
):
    system = await create_system(
        make_test_settings(tmp_path), clock=MutableClock(NOW)
    )
    await system.start()
    workspace = WorkspaceKey()
    inbox_item_id = "inbox_historical"
    alias = (
        "inbox_wl_"
        + hashlib.sha256(
            f"inbox_wl|{inbox_item_id}".encode("utf-8")
        ).hexdigest()[:24]
    )
    try:
        created = await system.work_log_service.create_from_inbox(
            workspace_key=workspace,
            inbox_item_id=inbox_item_id,
            subject="Historical Inbox",
            raw_text="Historical Inbox",
            reserved_id=alias,
        )
        assert created.id.startswith("wl_legacy_")
        assert created.legacy_memory_id == alias
        assert (
            await system.work_log_service.get(
                workspace_key=workspace, work_log_id=alias
            )
        ).id == created.id
        repeated = await system.work_log_service.create_from_inbox(
            workspace_key=workspace,
            inbox_item_id=inbox_item_id,
            subject="Historical Inbox",
            raw_text="Historical Inbox",
            reserved_id=alias,
        )
        assert repeated.id == created.id
        with system.database_manager.lease("episodic") as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM episodic_memories WHERE id=?", (alias,)
            ).fetchone()[0] == 1
    finally:
        await system.shutdown()
