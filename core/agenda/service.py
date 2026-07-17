"""Daily Agenda aggregate - assemble a read-only view from existing truth sources."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.agenda.models import (
    AgendaItem,
    AgendaItemKind,
    AgendaItemSource,
    AgendaPage,
    AgendaView,
    kind_priority,
    source_priority,
)
from core.clock import Clock
from core.errors import ErrorCategory, FailureException, FailureInfo
from zoneinfo import ZoneInfo

_VALID_LIMIT_RANGE = range(1, 101)
_VALID_WINDOW_RANGE = range(1, 169)
_CANDIDATE_CAP = 1200


class DailyAgendaService:
    """Compose a sorted, workspace-scoped agenda from persisted sources without duplicating truth."""

    COMPONENT = "agenda"

    def __init__(self, user_tasks, reminder_inbox, memory_manager, *, timezone_name: str, clock: Clock) -> None:
        self._user_tasks = user_tasks
        self._reminder_inbox = reminder_inbox
        self._memory = memory_manager
        self._zone = ZoneInfo(timezone_name)
        self._clock = clock

    async def list(self, *, workspace_key, view: str = "today", window_hours: int | None = None,
                   limit: int = 50, offset: int = 0, trace_id: str = "") -> AgendaPage:
        if limit not in _VALID_LIMIT_RANGE:
            self._raise("agenda.limit_invalid", "limit must be 1-100", trace_id)
        try:
            view = AgendaView(view.lower())
        except ValueError:
            self._raise("agenda.view_invalid", f"Unknown view: {view!r}", trace_id)
        window_hours = window_hours or (3 if view == AgendaView.NEXT else 24)
        if window_hours not in _VALID_WINDOW_RANGE:
            self._raise("agenda.window_invalid", "window_hours must be 1-168", trace_id)
        now_utc = self._clock.now().astimezone(timezone.utc)
        today_start, today_end = self._today_bounds(now_utc)
        window_start, window_end = self._window_bounds(now_utc, view, window_hours, today_start, today_end)
        items, failures = await self._collect(view, workspace_key, trace_id, now_utc, today_start, today_end, window_start, window_end)
        if failures:
            self._raise("agenda.query_failed", "Agenda query failed", trace_id, details={"failed_source": failures[0]})
        items.sort(key=self._sort_key)
        capped = items[:_CANDIDATE_CAP]
        total_count = len(capped)
        page = capped[offset : offset + limit] if offset < total_count else []
        return AgendaPage(
            items=page, count=len(page), limit=limit, offset=offset,
            has_more=(offset + limit) < total_count, timezone=self._zone.key,
            generated_at=now_utc, view=view.value, window_start=window_start, window_end=window_end,
        )

    async def _collect(self, view, workspace_key, trace_id, now_utc, today_start, today_end, window_start, window_end):
        items: list[AgendaItem] = []
        failures: list[str] = []
        if view == AgendaView.TODAY:
            items += await self._safe("reminder", lambda: self._reminder_today(workspace_key, trace_id, today_start, today_end), failures)
            items += await self._safe("user_task", lambda: self._user_task_actions(workspace_key, trace_id, today_start, today_end, False), failures)
            items += await self._safe("work_log", lambda: self._wl(workspace_key, trace_id, today_start, today_end), failures)
        elif view == AgendaView.NEXT:
            items += await self._safe("reminder", lambda: self._reminder_actions(workspace_key, trace_id, window_start, window_end), failures)
            items += await self._safe("user_task", lambda: self._user_task_actions(workspace_key, trace_id, window_start, window_end, True), failures)
        elif view == AgendaView.ATTENTION:
            items += await self._safe("reminder", lambda: self._reminder_attention(workspace_key, trace_id, now_utc), failures)
            items += await self._safe("user_task", lambda: self._overdue_tasks(workspace_key, trace_id, now_utc), failures)
        elif view == AgendaView.COMPLETED:
            items += await self._safe("reminder", lambda: self._reminder_completed(workspace_key, trace_id, today_start, today_end), failures)
            items += await self._safe("work_log", lambda: self._wl(workspace_key, trace_id, today_start, today_end), failures)
        elif view == AgendaView.ALL:
            items += await self._safe("reminder", lambda: self._reminder_all(workspace_key, trace_id), failures)
            items += await self._safe("user_task", lambda: self._user_task_all(workspace_key, trace_id), failures)
            items += await self._safe("work_log", lambda: self._wl(workspace_key, trace_id, today_start - timedelta(days=365), today_end + timedelta(days=365)), failures)
        return items, failures

    async def _reminder_today(self, wk, tid, ts, te):
        from core.reminders.inbox import ReminderInboxTimeScope
        page = await self._reminder_inbox.list(workspace_key=wk, time_scope=ReminderInboxTimeScope.TODAY, limit=300, offset=0, trace_id=tid)
        return [_ri(it, _reminder_kind(it.status.value)) for it in page.items if it.status.value != "cancelled"]

    async def _reminder_actions(self, wk, tid, ws, we):
        from core.reminders.inbox import ReminderInboxStatus
        page = await self._reminder_inbox.list(workspace_key=wk, statuses={ReminderInboxStatus.SCHEDULED, ReminderInboxStatus.RETRYING}, limit=300, offset=0, trace_id=tid)
        return [_ri(it, AgendaItemKind.ACTION) for it in page.items if it.scheduled_for and ws <= it.scheduled_for < we]

    async def _reminder_attention(self, wk, tid, _now):
        from core.reminders.inbox import ReminderInboxStatus
        page = await self._reminder_inbox.list(workspace_key=wk, statuses={ReminderInboxStatus.FAILED, ReminderInboxStatus.RETRYING}, limit=100, offset=0, trace_id=tid)
        return [_ri(it, AgendaItemKind.ATTENTION, extra={"last_failure_code": it.last_failure_code}) for it in page.items]

    async def _reminder_completed(self, wk, tid, ts, te):
        from core.reminders.inbox import ReminderInboxStatus
        page = await self._reminder_inbox.list(workspace_key=wk, statuses={ReminderInboxStatus.TRIGGERED}, limit=100, offset=0, trace_id=tid)
        return [_ri(it, AgendaItemKind.COMPLETED) for it in page.items if it.triggered_at and ts <= it.triggered_at < te]

    async def _reminder_all(self, wk, tid):
        page = await self._reminder_inbox.list(workspace_key=wk, limit=300, offset=0, trace_id=tid)
        return [_ri(it, _reminder_kind(it.status.value)) for it in page.items]

    async def _user_task_actions(self, wk, tid, ws, we, require_due):
        from core.user_tasks import UserTaskQuery, UserTaskStatus
        tasks = await self._user_tasks.list(UserTaskQuery(status=UserTaskStatus.ACTIVE, limit=200), trace_id=tid)
        out = []
        for t in tasks:
            if not self._belongs(t, wk):
                continue
            if t.due_at and ws <= t.due_at < we:
                out.append(_ui(t, AgendaItemKind.ACTION))
        return out

    async def _overdue_tasks(self, wk, tid, now_utc):
        from core.user_tasks import UserTaskQuery, UserTaskStatus
        tasks = await self._user_tasks.list(UserTaskQuery(status=UserTaskStatus.ACTIVE, limit=200), trace_id=tid)
        return [_ui(t, AgendaItemKind.ATTENTION, status_override="overdue") for t in tasks if t.due_at and t.due_at < now_utc and self._belongs(t, wk)]

    async def _user_task_all(self, wk, tid):
        out = []
        for status_str, kind in [("active", AgendaItemKind.ACTION), ("completed", AgendaItemKind.COMPLETED), ("cancelled", AgendaItemKind.COMPLETED)]:
            from core.user_tasks import UserTaskQuery, UserTaskStatus
            tasks = await self._user_tasks.list(UserTaskQuery(status=UserTaskStatus(status_str), limit=200), trace_id=tid)
            out += [_ui(t, kind) for t in tasks if self._belongs(t, wk)]
        return out

    async def _wl(self, wk, tid, ts, te):
        from core.memory.models import MemoryQuery, MemoryType
        items = await self._memory.retrieve_memory(MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=200))
        out = []
        wk_id = (wk.workspace_id or "default") if hasattr(wk, "workspace_id") else "default"
        for it in items:
            content = it.content or {}
            if content.get("type") != "work_log":
                continue
            meta = content.get("metadata") or {}
            item_ws = meta.get("workspace_id", "default")
            if item_ws != wk_id:
                continue
            ts_val = None
            raw = content.get("date") or ""
            try:
                ts_val = datetime.fromisoformat(str(raw))
                if ts_val.tzinfo is None:
                    ts_val = ts_val.replace(tzinfo=self._zone)
                ts_val = ts_val.astimezone(timezone.utc)
            except (ValueError, TypeError):
                pass
            if ts_val is None or not (ts <= ts_val < te):
                continue
            out.append(AgendaItem(
                id=f"agenda-wl-{it.id}", source=AgendaItemSource.WORK_LOG, kind=AgendaItemKind.COMPLETED,
                title=content.get("subject", "") or content.get("raw_text", "") or str(content)[:120],
                status="completed", occurred_at=ts_val, timezone=self._zone.key,
                workspace_id=wk_id, source_id=it.id,
            ))
        out.sort(key=lambda x: x.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
        return out

    def _today_bounds(self, now_utc):
        local = now_utc.astimezone(self._zone)
        ls = local.replace(hour=0, minute=0, second=0, microsecond=0)
        le = ls + timedelta(days=1)
        return ls.astimezone(timezone.utc), le.astimezone(timezone.utc)

    def _window_bounds(self, now_utc, view, wh, ts, te):
        if view in (AgendaView.TODAY, AgendaView.COMPLETED):
            return ts, te
        if view == AgendaView.ATTENTION:
            return ts - timedelta(days=30), te
        if view == AgendaView.NEXT:
            return now_utc, now_utc + timedelta(hours=wh)
        return ts - timedelta(days=365), te + timedelta(days=365)

    @staticmethod
    def _belongs(task, wk) -> bool:
        ws = task.metadata.get("workspace") if isinstance(task.metadata, dict) else {}
        return ws.get("workspace_id", "default") == ((wk.workspace_id or "default") if hasattr(wk, "workspace_id") else "default")

    @staticmethod
    def _sort_key(item: AgendaItem):
        eff = item.scheduled_for or item.due_at or item.occurred_at or datetime.min.replace(tzinfo=timezone.utc)
        return (eff, kind_priority(item.kind), source_priority(item.source), item.source_id)

    @staticmethod
    def _raise(code: str, message: str, trace_id: str, details: dict | None = None):
        cat = ErrorCategory.VALIDATION if code.endswith("_invalid") else ErrorCategory.DEPENDENCY_FAILURE
        raise FailureException(FailureInfo(
            code=code, category=cat, message=message, component=DailyAgendaService.COMPONENT,
            operation="list", retryable=False, trace_id=trace_id, details=details or {},
        ))

    @staticmethod
    async def _safe(source: str, fn, failures: list[str]):
        try:
            return await fn()
        except Exception as exc:
            from core.errors import FailureException
            if isinstance(exc, FailureException):
                raise
            failures.append(source)
            return []


def _ri(it, kind, extra=None):
    return AgendaItem(id=f"agenda-rem-{it.reminder_id}", source=AgendaItemSource.REMINDER, kind=kind,
                       title=it.task_title, status=it.status.value, scheduled_for=it.scheduled_for,
                       occurred_at=it.triggered_at, timezone=it.timezone,
                       workspace_id="", source_id=it.reminder_id, task_id=it.task_id, reminder_id=it.reminder_id,
                       metadata={"scheduler_status": it.scheduler_status, **(extra or {})})


def _ui(t, kind, status_override=None):
    return AgendaItem(id=f"agenda-ut-{t.id}", source=AgendaItemSource.USER_TASK, kind=kind,
                       title=t.title, status=status_override or t.status.value, due_at=t.due_at,
                       timezone=t.timezone, workspace_id="", source_id=t.id, task_id=t.id)


def _reminder_kind(status: str) -> AgendaItemKind:
    if status in ("scheduled", "retrying"):
        return AgendaItemKind.ACTION
    if status == "triggered":
        return AgendaItemKind.EVENT
    if status == "failed":
        return AgendaItemKind.ATTENTION
    return AgendaItemKind.COMPLETED
