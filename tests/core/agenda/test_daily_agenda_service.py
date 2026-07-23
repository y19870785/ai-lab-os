import pytest
from datetime import datetime, timedelta, timezone
from core.agenda.service import DailyAgendaService
from tests.helpers.clock import MutableClock
from core.errors import ErrorCategory, FailureException


class FakeUserTaskService:
    def __init__(self, tasks=None):
        self._tasks = tasks or []
    async def list(self, query, trace_id=""):
        st = query.status.value if hasattr(query, "status") else None
        return [t for t in self._tasks if not st or t.status.value == st]
    async def get(self, tid, trace_id=""):
        return next((t for t in self._tasks if t.id == tid), None)


class FakeReminderInbox:
    def __init__(self, items=None):
        self._items = items or []
    async def list(self, *, workspace_key, statuses=None, time_scope=None, view=None, limit=100, offset=0, trace_id=""):
        result = list(self._items)
        if statuses:
            result = [i for i in result if i["status"] in statuses]
        return type("Page", (), {"items": [type("Item", (), i) for i in result]})()


class FakeMemoryManager:
    def __init__(self, items=None):
        self._items = items or []
    async def retrieve_memory(self, query):
        return self._items


class FakeWorkLogService:
    def __init__(self, items=None):
        self._items = items or []

    async def list(self, *, workspace_key, query):
        identity = (
            getattr(workspace_key, "tenant_id", "") or "default",
            getattr(workspace_key, "workspace_id", "") or "default",
            getattr(workspace_key, "namespace", "") or "default",
        )
        items = [
            item
            for item in self._items
            if (
                item.workspace_key.tenant_id,
                item.workspace_key.workspace_id,
                item.workspace_key.namespace,
            )
            == identity
            and (query.date_from is None or item.occurred_at >= query.date_from)
            and (query.date_to is None or item.occurred_at < query.date_to)
        ]
        return type(
            "Page",
            (),
            {
                "items": tuple(items[query.offset : query.offset + query.limit]),
                "has_more": query.offset + query.limit < len(items),
                "count": len(items[query.offset : query.offset + query.limit]),
            },
        )()


class FakeWaitingForService:
    def __init__(self, items=None):
        self._items = items or []

    async def list(self, **_kwargs):
        return type("Page", (), {"items": self._items})()


def _fake_reminder_item(reminder_id, title, status, scheduled_for, triggered_at=None, last_failure_code=None):
    return {"reminder_id": reminder_id, "task_title": title, "status": type("S", (), {"value": status})(),
            "task_id": f"ut_{reminder_id}", "scheduled_for": scheduled_for, "triggered_at": triggered_at,
            "timezone": "Asia/Shanghai", "scheduler_status": status, "last_failure_code": last_failure_code}


def _fake_task(task_id, title, status, due_at=None):
    return type("T", (), {"id": task_id, "title": title, "status": type("S", (), {"value": status})(),
                           "due_at": due_at, "timezone": "Asia/Shanghai",
                           "metadata": {"workspace": {"workspace_id": "default"}}})()


def _fake_wl(item_id, date_str, subject, ws="default"):
    from core.work_log import WorkLogRecord
    from core.workspace.models import WorkspaceKey

    return WorkLogRecord(
        id=item_id,
        workspace_key=WorkspaceKey(
            tenant_id="default",
            workspace_id=ws,
            namespace="default",
            trace_id="",
        ),
        occurred_at=datetime.fromisoformat(date_str).replace(
            tzinfo=timezone.utc
        ),
        timezone="Asia/Shanghai",
        subject=subject,
        raw_text=subject,
        source="legacy",
        created_at=datetime.fromisoformat(date_str).replace(
            tzinfo=timezone.utc
        ),
        schema_version=1,
    )


def _fake_waiting_for(clock, subject, **changes):
    from core.waiting_for import WaitingFor
    from core.workspace.models import WorkspaceKey

    values = {
        "workspace_key": WorkspaceKey(workspace_id="default"),
        "subject": subject,
        "waiting_on": "Supplier",
        "source": "test",
        "created_at": clock.now() - timedelta(days=1),
        "updated_at": clock.now(),
    }
    values.update(changes)
    return WaitingFor(**values)


@pytest.fixture
def clock():
    return MutableClock(datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc))


@pytest.fixture
def svc(clock):
    return DailyAgendaService(
        FakeUserTaskService(),
        FakeReminderInbox(),
        FakeMemoryManager(),
        work_log_service=FakeWorkLogService(),
        timezone_name="Asia/Shanghai",
        clock=clock,
    )


class FakeWorkspace:
    workspace_id = "default"


@pytest.mark.asyncio
async def test_today_active_task_with_due_at_in_window(svc, clock):
    svc._user_tasks = FakeUserTaskService([_fake_task("ut1", "Review", "active", due_at=datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc))])
    page = await svc.list(workspace_key=FakeWorkspace(), view="today")
    assert len(page.items) == 1
    assert page.items[0].title == "Review"


@pytest.mark.asyncio
async def test_today_active_task_no_due_at_excluded(svc, clock):
    svc._user_tasks = FakeUserTaskService([_fake_task("ut1", "NoDue", "active")])
    page = await svc.list(workspace_key=FakeWorkspace(), view="today")
    assert len(page.items) == 0


@pytest.mark.asyncio
async def test_today_active_task_outside_window_excluded(svc, clock):
    svc._user_tasks = FakeUserTaskService([_fake_task("ut1", "Future", "active", due_at=datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc))])
    page = await svc.list(workspace_key=FakeWorkspace(), view="today")
    assert len(page.items) == 0


@pytest.mark.asyncio
async def test_next_past_due_task_excluded(svc, clock):
    svc._user_tasks = FakeUserTaskService([_fake_task("ut1", "Past", "active", due_at=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc))])
    page = await svc.list(workspace_key=FakeWorkspace(), view="next", window_hours=3)
    assert len(page.items) == 0


@pytest.mark.asyncio
async def test_next_in_window_task_included(svc, clock):
    svc._user_tasks = FakeUserTaskService([_fake_task("ut1", "Soon", "active", due_at=datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc))])
    page = await svc.list(workspace_key=FakeWorkspace(), view="next", window_hours=3)
    assert len(page.items) == 1


@pytest.mark.asyncio
async def test_wl_workspace_isolation(svc, clock):
    svc._work_logs = FakeWorkLogService([
        _fake_wl("wl_" + "1" * 32, "2026-07-17", "Alpha", ws="alpha"),
        _fake_wl("wl_" + "2" * 32, "2026-07-17", "Default", ws="default"),
    ])
    page = await svc.list(workspace_key=FakeWorkspace(), view="today")
    assert len(page.items) == 1
    assert page.items[0].title == "Default"


@pytest.mark.asyncio
async def test_reminder_source_failure_causes_agenda_query_failed(svc, clock):
    class FailingInbox:
        async def list(self, **kw):
            raise RuntimeError("boom")
    svc._reminder_inbox = FailingInbox()
    with pytest.raises(FailureException) as exc:
        await svc.list(workspace_key=FakeWorkspace(), view="today")
    assert exc.value.failure.code == "agenda.query_failed"
    assert exc.value.failure.category != ErrorCategory.VALIDATION


@pytest.mark.asyncio
async def test_invalid_view_raises(svc):
    with pytest.raises(FailureException) as exc:
        await svc.list(workspace_key=FakeWorkspace(), view="nonexistent")
    assert exc.value.failure.code == "agenda.view_invalid"


@pytest.mark.asyncio
async def test_invalid_limit_raises(svc):
    with pytest.raises(FailureException) as exc:
        await svc.list(workspace_key=FakeWorkspace(), view="today", limit=200)
    assert exc.value.failure.code == "agenda.limit_invalid"


@pytest.mark.asyncio
async def test_waiting_for_attention_and_completed_mapping(clock):
    from core.waiting_for import WaitingFor, WaitingForStatus
    from core.workspace.models import WorkspaceKey

    base = {
        "workspace_key": WorkspaceKey(workspace_id="default"),
        "waiting_on": "Supplier",
        "source": "test",
        "created_at": clock.now() - timedelta(days=1),
        "updated_at": clock.now(),
    }
    attention = WaitingFor(
        **base,
        subject="Reply overdue",
        next_review_at=clock.now() - timedelta(hours=1),
    )
    resolved = WaitingFor(
        **base,
        subject="Reply received",
        status=WaitingForStatus.RESOLVED,
        resolved_at=clock.now(),
        resolution_note="Done",
    )
    service = DailyAgendaService(
        waiting_for=FakeWaitingForService([attention, resolved]),
        timezone_name="Asia/Shanghai",
        clock=clock,
    )
    attention_page = await service.list(
        workspace_key=WorkspaceKey(), view="attention"
    )
    completed_page = await service.list(
        workspace_key=WorkspaceKey(), view="completed"
    )
    assert attention_page.items[0].waiting_for_id == attention.id
    assert attention_page.items[0].kind.value == "attention"
    assert attention_page.items[0].metadata == {"waiting_on": "Supplier"}
    assert completed_page.items[0].waiting_for_id == resolved.id
    assert completed_page.items[0].kind.value == "completed"


@pytest.mark.asyncio
async def test_missing_sources_are_disabled_not_failed(clock):
    service = DailyAgendaService(timezone_name="Asia/Shanghai", clock=clock)
    page = await service.list(workspace_key=FakeWorkspace(), view="today")
    assert page.items == []


@pytest.mark.asyncio
@pytest.mark.parametrize("view", ["today", "next"])
async def test_waiting_for_dual_times_include_either_field_once(clock, view):
    from core.workspace.models import WorkspaceKey

    item = _fake_waiting_for(
        clock,
        "Dual time",
        next_review_at=clock.now() + timedelta(days=2),
        expected_by=clock.now() + timedelta(hours=1),
    )
    service = DailyAgendaService(
        waiting_for=FakeWaitingForService([item]),
        timezone_name="Asia/Shanghai",
        clock=clock,
    )
    kwargs = {"window_hours": 3} if view == "next" else {}
    page = await service.list(workspace_key=WorkspaceKey(), view=view, **kwargs)
    assert [agenda_item.waiting_for_id for agenda_item in page.items] == [item.id]


@pytest.mark.asyncio
async def test_waiting_for_both_times_in_today_produces_no_duplicate(clock):
    from core.workspace.models import WorkspaceKey

    item = _fake_waiting_for(
        clock,
        "Both today",
        next_review_at=clock.now() + timedelta(hours=1),
        expected_by=clock.now() + timedelta(hours=2),
    )
    service = DailyAgendaService(
        waiting_for=FakeWaitingForService([item]),
        timezone_name="Asia/Shanghai",
        clock=clock,
    )
    page = await service.list(workspace_key=WorkspaceKey(), view="today")
    assert len(page.items) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["resolved", "cancelled"])
async def test_terminal_waiting_for_is_excluded_from_today_and_in_completed(clock, status):
    from core.waiting_for import WaitingForStatus
    from core.workspace.models import WorkspaceKey

    terminal_at = clock.now()
    terminal = {
        "status": WaitingForStatus(status),
        "expected_by": clock.now() + timedelta(hours=1),
        "resolved_at" if status == "resolved" else "cancelled_at": terminal_at,
    }
    if status == "resolved":
        terminal["resolution_note"] = "done"
    item = _fake_waiting_for(clock, status, **terminal)
    service = DailyAgendaService(
        waiting_for=FakeWaitingForService([item]),
        timezone_name="Asia/Shanghai",
        clock=clock,
    )
    today = await service.list(workspace_key=WorkspaceKey(), view="today")
    completed = await service.list(workspace_key=WorkspaceKey(), view="completed")
    assert today.items == []
    assert completed.items[0].status == status
    assert completed.items[0].kind.value == "completed"


@pytest.mark.asyncio
async def test_waiting_for_derived_status_priority_and_kind(clock):
    from core.workspace.models import WorkspaceKey

    expected = _fake_waiting_for(
        clock,
        "Expected overdue",
        expected_by=clock.now() - timedelta(hours=2),
        next_review_at=clock.now() - timedelta(hours=1),
    )
    review = _fake_waiting_for(
        clock,
        "Review due",
        next_review_at=clock.now() - timedelta(minutes=1),
    )
    future = _fake_waiting_for(
        clock,
        "Future",
        next_review_at=clock.now() + timedelta(hours=1),
    )
    service = DailyAgendaService(
        waiting_for=FakeWaitingForService([expected, review, future]),
        timezone_name="Asia/Shanghai",
        clock=clock,
    )
    page = await service.list(workspace_key=WorkspaceKey(), view="all")
    by_id = {item.waiting_for_id: item for item in page.items}
    assert by_id[expected.id].status == "expected_overdue"
    assert by_id[expected.id].kind.value == "attention"
    assert by_id[review.id].status == "review_due"
    assert by_id[review.id].kind.value == "attention"
    assert by_id[future.id].status == "open"
    assert by_id[future.id].kind.value == "action"


@pytest.mark.asyncio
async def test_waiting_for_open_and_completed_sort_use_correct_effective_time(clock):
    from core.waiting_for import WaitingForStatus
    from core.workspace.models import WorkspaceKey

    open_item = _fake_waiting_for(
        clock,
        "Earliest expected",
        next_review_at=clock.now() + timedelta(hours=3),
        expected_by=clock.now() + timedelta(hours=1),
    )
    other_open = _fake_waiting_for(
        clock, "Later", next_review_at=clock.now() + timedelta(hours=2)
    )
    completed_early = _fake_waiting_for(
        clock,
        "Completed early",
        status=WaitingForStatus.RESOLVED,
        expected_by=clock.now() - timedelta(days=30),
        resolved_at=clock.now() - timedelta(hours=1),
        resolution_note="done",
    )
    completed_late = _fake_waiting_for(
        clock,
        "Completed late",
        status=WaitingForStatus.RESOLVED,
        expected_by=clock.now() - timedelta(days=60),
        resolved_at=clock.now(),
        resolution_note="done",
    )
    service = DailyAgendaService(
        waiting_for=FakeWaitingForService(
            [other_open, completed_late, open_item, completed_early]
        ),
        timezone_name="Asia/Shanghai",
        clock=clock,
    )
    all_page = await service.list(workspace_key=WorkspaceKey(), view="all")
    open_ids = [item.waiting_for_id for item in all_page.items if item.kind.value != "completed"]
    assert open_ids == [open_item.id, other_open.id]
    completed_page = await service.list(workspace_key=WorkspaceKey(), view="completed")
    assert [item.waiting_for_id for item in completed_page.items] == [
        completed_early.id,
        completed_late.id,
    ]
