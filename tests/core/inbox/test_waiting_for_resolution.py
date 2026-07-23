from datetime import datetime, timedelta, timezone

import pytest

from core.errors import FailureException
from core.inbox import InboxResolvedType, InboxService, InboxStatus
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


NOW = datetime(2026, 7, 23, 1, 0, tzinfo=timezone.utc)


async def _system(tmp_path):
    system = await create_system(
        make_test_settings(tmp_path, timezone_name="Asia/Shanghai"),
        clock=MutableClock(NOW),
    )
    await system.start()
    return system


def test_waiting_for_id_is_deterministic_and_item_scoped():
    first = InboxService._target_id("wf_inbox", "inbox_alpha")
    repeat = InboxService._target_id("wf_inbox", "inbox_alpha")
    other = InboxService._target_id("wf_inbox", "inbox_beta")

    assert first == repeat
    assert first.startswith("wf_inbox_")
    assert first != other


@pytest.mark.asyncio
async def test_resolve_to_waiting_for_is_idempotent_and_preserves_source(tmp_path):
    system = await _system(tmp_path)
    workspace = WorkspaceKey(workspace_id="alpha")
    try:
        captured = await system.inbox_service.capture(
            workspace_key=workspace,
            content="等张经理回复蜂蜡检测方案",
            source="ceo_assistant",
        )
        values = {
            "workspace_key": workspace,
            "inbox_item_id": captured.id,
            "subject": "蜂蜡检测方案",
            "waiting_on": "张经理",
            "context": "等待确认检测方案",
            "next_review_at": NOW + timedelta(days=1),
            "timezone": "Asia/Shanghai",
        }

        resolved = await system.inbox_service.resolve_to_waiting_for(**values)
        repeated = await system.inbox_service.resolve_to_waiting_for(**values)
        target = await system.waiting_for_service.get(
            workspace_key=workspace,
            waiting_for_id=resolved.resolved_target_id,
        )
        events = await system.waiting_for_service.list_events(
            workspace_key=workspace,
            waiting_for_id=target.id,
        )

        assert resolved.resolved_type == InboxResolvedType.WAITING_FOR
        assert repeated.resolved_target_id == resolved.resolved_target_id
        assert target.metadata == {
            "inbox_item_id": captured.id,
            "inbox_source": "ceo_assistant",
        }
        assert target.revision == 1
        assert len(events.items) == 1
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_missing_waiting_for_fields_fail_before_claim_or_target(tmp_path):
    system = await _system(tmp_path)
    workspace = WorkspaceKey()
    try:
        captured = await system.inbox_service.capture(
            workspace_key=workspace,
            content="等待确认",
            source="api",
        )
        with pytest.raises(FailureException) as exc:
            await system.inbox_service.resolve_to_waiting_for(
                workspace_key=workspace,
                inbox_item_id=captured.id,
                subject="",
                waiting_on="",
            )

        stored = await system.inbox_service.get(
            workspace_key=workspace,
            inbox_item_id=captured.id,
        )
        page = await system.waiting_for_service.list(
            workspace_key=workspace,
            view="all",
        )

        assert exc.value.failure.code == "inbox.waiting_for.fields_missing"
        assert exc.value.failure.details["missing_fields"] == [
            "subject",
            "waiting_on",
            "expected_by_or_next_review_at",
        ]
        assert "resolve-waiting-for" in exc.value.failure.details["confirmation_template"]
        assert stored.status == InboxStatus.PENDING
        assert page.items == ()
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_existing_deterministic_target_with_other_source_fails_closed(tmp_path):
    system = await _system(tmp_path)
    workspace = WorkspaceKey()
    try:
        captured = await system.inbox_service.capture(
            workspace_key=workspace,
            content="等待确认",
            source="api",
        )
        target_id = InboxService._target_id("wf_inbox", captured.id)
        await system.waiting_for_service.create(
            workspace_key=workspace,
            subject="冲突对象",
            waiting_on="其他人",
            next_review_at=NOW + timedelta(days=1),
            timezone="Asia/Shanghai",
            source="api",
            waiting_for_id=target_id,
            metadata={"inbox_item_id": "inbox_other", "inbox_source": "api"},
        )

        with pytest.raises(FailureException) as exc:
            await system.inbox_service.resolve_to_waiting_for(
                workspace_key=workspace,
                inbox_item_id=captured.id,
                subject="等待确认",
                waiting_on="张经理",
                next_review_at=NOW + timedelta(days=1),
                timezone="Asia/Shanghai",
            )
        stored = await system.inbox_service.get(
            workspace_key=workspace,
            inbox_item_id=captured.id,
        )

        assert exc.value.failure.code == "inbox.waiting_for.source_mismatch"
        assert stored.status == InboxStatus.PENDING
    finally:
        await system.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["claimed", "target_created", "target_recorded"])
async def test_waiting_for_resolution_recovers_each_saga_interruption(tmp_path, stage):
    settings = make_test_settings(tmp_path, timezone_name="Asia/Shanghai")
    workspace = WorkspaceKey()
    first = await create_system(settings, clock=MutableClock(NOW))
    await first.start()
    try:
        captured = await first.inbox_service.capture(
            workspace_key=workspace,
            content="等待恢复",
            source="api",
        )
        target_id = InboxService._target_id("wf_inbox", captured.id)
        await first.inbox_repository.claim_resolution(
            workspace,
            captured.id,
            resolved_type=InboxResolvedType.WAITING_FOR,
            target_key=target_id,
            target_id=target_id,
            now=NOW,
        )
        if stage in {"target_created", "target_recorded"}:
            await first.waiting_for_service.create(
                workspace_key=workspace,
                subject="等待恢复",
                waiting_on="张经理",
                next_review_at=NOW + timedelta(days=1),
                timezone="Asia/Shanghai",
                source="inbox",
                waiting_for_id=target_id,
                metadata={
                    "inbox_item_id": captured.id,
                    "inbox_source": captured.source,
                },
            )
        if stage == "target_recorded":
            await first.inbox_repository.record_target_created(
                workspace,
                captured.id,
                resolved_type=InboxResolvedType.WAITING_FOR,
                target_id=target_id,
                now=NOW,
            )
    finally:
        await first.shutdown()

    second = await create_system(settings, clock=MutableClock(NOW))
    await second.start()
    try:
        resolved = await second.inbox_service.resolve_to_waiting_for(
            workspace_key=workspace,
            inbox_item_id=captured.id,
            subject="等待恢复",
            waiting_on="张经理",
            next_review_at=NOW + timedelta(days=1),
            timezone="Asia/Shanghai",
        )
        page = await second.waiting_for_service.list(
            workspace_key=workspace, view="all"
        )
        events = await second.waiting_for_service.list_events(
            workspace_key=workspace, waiting_for_id=target_id
        )

        assert resolved.status == InboxStatus.RESOLVED
        assert resolved.resolved_target_id == target_id
        assert [item.id for item in page.items] == [target_id]
        assert len(events.items) == 1
    finally:
        await second.shutdown()
