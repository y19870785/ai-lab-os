import pytest
from datetime import datetime, timedelta, timezone
from core.agenda.models import AgendaView
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
        from core.reminders.inbox import ReminderInboxStatus
        result = list(self._items)
        if statuses:
            result = [i for i in result if i["status"] in statuses]
        return type("Page", (), {"items": [type("Item", (), i) for i in result]})()


class FakeMemoryManager:
    def __init__(self, items=None):
        self._items = items or []
    async def retrieve_memory(self, query):
        return self._items


def _fake_reminder_item(reminder_id, title, status, scheduled_for, triggered_at=None, last_failure_code=None):
    return {"reminder_id": reminder_id, "task_title": title, "status": type("S", (), {"value": status})(),
            "task_id": f"ut_{reminder_id}", "scheduled_for": scheduled_for, "triggered_at": triggered_at,
            "timezone": "Asia/Shanghai", "scheduler_status": status, "last_failure_code": last_failure_code}


def _fake_task(task_id, title, status, due_at=None):
    return type("T", (), {"id": task_id, "title": title, "status": type("S", (), {"value": status})(),
                           "due_at": due_at, "timezone": "Asia/Shanghai",
                           "metadata": {"workspace": {"workspace_id": "default"}}})()


def _fake_wl(item_id, date_str, subject, ws="default"):
    from core.memory.models import MemoryItem, MemoryType
    return MemoryItem(id=item_id, memory_type=MemoryType.EPISODIC,
                      content={"type": "work_log", "date": date_str, "subject": subject, "metadata": {"workspace_id": ws}})


@pytest.fixture
def clock():
    return MutableClock(datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc))


@pytest.fixture
def svc(clock):
    return DailyAgendaService(FakeUserTaskService(), FakeReminderInbox(), FakeMemoryManager(), timezone_name="Asia/Shanghai", clock=clock)


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
    svc._memory = FakeMemoryManager([
        _fake_wl("wl1", "2026-07-17", "Alpha", ws="alpha"),
        _fake_wl("wl2", "2026-07-17", "Default", ws="default"),
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
