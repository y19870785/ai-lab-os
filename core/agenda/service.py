"""Daily Agenda aggregate — assemble a read-only view from existing truth sources."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

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
    """Compose a sorted, workspace-scoped agenda from persisted UserTask,
    Reminder and Work Log records without duplicating truth."""

    COMPONENT = "agenda"

    def __init__(
        self,
        user_tasks,
        reminder_inbox,
        memory_manager,
        *,
        timezone_name: str,
        clock: Clock,
    ) -> None:
        self._user_tasks = user_tasks
        self._reminder_inbox = reminder_inbox
        self._memory = memory_manager
        self._zone = ZoneInfo(timezone_name)
        self._clock = clock

    # -- public entry -------------------------------------------------

    async def list(
        self,
        *,
        workspace_key,
        view: str = "today",
        window_hours: int | None = None,
        limit: int = 50,
        offset: int = 0,
        trace_id: str = "",
    ) -> AgendaPage:
        if limit not in _VALID_LIMIT_RANGE:
            self._raise("agenda.limit_invalid", "limit must be 1-100", trace_id)

        try:
            view = AgendaView(view.lower())
        except ValueError:
            self._raise("agenda.view_invalid", f"Unknown view: {view!r}", trace_id)

        if view == AgendaView.NEXT:
            window_hours = window_hours or 3
        else:
            window_hours = window_hours or 24

        if window_hours not in _VALID_WINDOW_RANGE:
            self._raise("agenda.window_invalid", "window_hours must be 1-168", trace_id)

        now_utc = self._clock.now().astimezone(timezone.utc)
        today_start, today_end = self._today_bounds(now_utc)
        window_start, window_end = self._window_bounds(now_utc, view, window_hours, today_start, today_end)

        try:
            items = await self._collect(view, workspace_key, trace_id, now_utc, today_start, today_end, window_start, window_end)
        except FailureException:
            raise
        except Exception as exc:
            self._raise("agenda.query_failed", "Agenda query failed", trace_id)

        items.sort(key=self._sort_key)

        total_count = len(items)
        page = items[offset : offset + limit] if offset < total_count else []

        return AgendaPage(
            items=page,
            count=len(page),
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total_count,
            timezone=self._zone.key,
            generated_at=now_utc,
            view=view.value,
            window_start=window_start,
            window_end=window_end,
        )

    # -- collection ---------------------------------------------------

    async def _collect(self, view, workspace_key, trace_id, now_utc, today_start, today_end, window_start, window_end):
        items: list[AgendaItem] = []

        if view in (AgendaView.TODAY, AgendaView.ALL):
            items += await self._reminder_items(workspace_key, trace_id, today_start, today_end, include_cancelled=(view == AgendaView.ALL))
            items += await self._user_task_items(workspace_key, trace_id)
            items += await self._work_log_items(workspace_key, trace_id, today_start, today_end)

        elif view == AgendaView.NEXT:
            items += await self._reminder_actions(workspace_key, trace_id, window_start, window_end)
            items += await self._user_task_open(workspace_key, trace_id, False)

        elif view == AgendaView.ATTENTION:
            items += await self._reminder_attention(workspace_key, trace_id, now_utc)
            items += await self._overdue_tasks(workspace_key, trace_id, now_utc)

        elif view == AgendaView.COMPLETED:
            items += await self._reminder_completed(workspace_key, trace_id, today_start, today_end)
            items += await self._work_log_items(workspace_key, trace_id, today_start, today_end)

        return items[: _CANDIDATE_CAP]

    # -- source adapters ----------------------------------------------

    async def _reminder_items(self, workspace_key, trace_id, today_start, today_end, *, include_cancelled):
        from core.reminders.inbox import ReminderInboxTimeScope
        page = await self._reminder_inbox.list(
            workspace_key=workspace_key,
            time_scope=ReminderInboxTimeScope.TODAY,
            limit=300,
            offset=0,
            trace_id=trace_id,
        )
        results = []
        for item in page.items:
            if not include_cancelled and item.status.value == "cancelled":
                continue
            kind = _reminder_kind(item.status.value)
            results.append(AgendaItem(
                id=f"agenda-rem-{item.reminder_id}",
                source=AgendaItemSource.REMINDER,
                kind=kind,
                title=item.task_title,
                status=item.status.value,
                scheduled_for=item.scheduled_for,
                occurred_at=item.triggered_at,
                timezone=item.timezone,
                workspace_id=workspace_key.workspace_id or "",
                source_id=item.reminder_id,
                task_id=item.task_id,
                reminder_id=item.reminder_id,
                metadata={"scheduler_status": item.scheduler_status, "last_failure_code": item.last_failure_code},
            ))
        return results

    async def _reminder_actions(self, workspace_key, trace_id, window_start, window_end):
        from core.reminders.inbox import ReminderInboxStatus
        page = await self._reminder_inbox.list(
            workspace_key=workspace_key,
            statuses={ReminderInboxStatus.SCHEDULED, ReminderInboxStatus.RETRYING},
            limit=300,
            offset=0,
            trace_id=trace_id,
        )
        return [
            AgendaItem(
                id=f"agenda-rem-{item.reminder_id}",
                source=AgendaItemSource.REMINDER,
                kind=AgendaItemKind.ACTION,
                title=item.task_title,
                status=item.status.value,
                scheduled_for=item.scheduled_for,
                timezone=item.timezone,
                workspace_id=workspace_key.workspace_id or "",
                source_id=item.reminder_id,
                task_id=item.task_id,
                reminder_id=item.reminder_id,
            )
            for item in page.items
            if item.scheduled_for and window_start <= item.scheduled_for < window_end
        ]

    async def _reminder_attention(self, workspace_key, trace_id, now_utc):
        from core.reminders.inbox import ReminderInboxStatus
        page = await self._reminder_inbox.list(
            workspace_key=workspace_key,
            statuses={ReminderInboxStatus.FAILED, ReminderInboxStatus.RETRYING},
            limit=100,
            offset=0,
            trace_id=trace_id,
        )
        return [
            AgendaItem(
                id=f"agenda-rem-{item.reminder_id}",
                source=AgendaItemSource.REMINDER,
                kind=AgendaItemKind.ATTENTION,
                title=item.task_title,
                status=item.status.value,
                scheduled_for=item.scheduled_for,
                timezone=item.timezone,
                workspace_id=workspace_key.workspace_id or "",
                source_id=item.reminder_id,
                task_id=item.task_id,
                reminder_id=item.reminder_id,
                metadata={"last_failure_code": item.last_failure_code},
            )
            for item in page.items
        ]

    async def _reminder_completed(self, workspace_key, trace_id, today_start, today_end):
        from core.reminders.inbox import ReminderInboxStatus
        page = await self._reminder_inbox.list(
            workspace_key=workspace_key,
            statuses={ReminderInboxStatus.TRIGGERED},
            limit=100,
            offset=0,
            trace_id=trace_id,
        )
        return [
            AgendaItem(
                id=f"agenda-rem-{item.reminder_id}",
                source=AgendaItemSource.REMINDER,
                kind=AgendaItemKind.COMPLETED,
                title=item.task_title,
                status=item.status.value,
                scheduled_for=item.scheduled_for,
                occurred_at=item.triggered_at,
                timezone=item.timezone,
                workspace_id=workspace_key.workspace_id or "",
                source_id=item.reminder_id,
                task_id=item.task_id,
                reminder_id=item.reminder_id,
            )
            for item in page.items
            if item.triggered_at and today_start <= item.triggered_at < today_end
        ]

    async def _user_task_items(self, workspace_key, trace_id):
        results = []
        for status, kind in [("active", AgendaItemKind.ACTION), ("completed", AgendaItemKind.COMPLETED)]:
            from core.user_tasks import UserTaskQuery, UserTaskStatus
            tasks = await self._user_tasks.list(
                UserTaskQuery(status=UserTaskStatus(status), limit=200),
                trace_id=trace_id,
            )
            for task in tasks:
                if not self._belongs(task, workspace_key):
                    continue
                results.append(AgendaItem(
                    id=f"agenda-ut-{task.id}",
                    source=AgendaItemSource.USER_TASK,
                    kind=kind,
                    title=task.title,
                    status=task.status.value,
                    due_at=task.due_at,
                    timezone=task.timezone,
                    workspace_id=workspace_key.workspace_id or "",
                    source_id=task.id,
                    task_id=task.id,
                ))
        return results

    async def _user_task_open(self, workspace_key, trace_id, overdue_only):
        results = []
        from core.user_tasks import UserTaskQuery, UserTaskStatus
        tasks = await self._user_tasks.list(
            UserTaskQuery(status=UserTaskStatus.ACTIVE, limit=200),
            trace_id=trace_id,
        )
        for task in tasks:
            if not self._belongs(task, workspace_key):
                continue
            results.append(AgendaItem(
                id=f"agenda-ut-{task.id}",
                source=AgendaItemSource.USER_TASK,
                kind=AgendaItemKind.ACTION,
                title=task.title,
                status=task.status.value,
                due_at=task.due_at,
                timezone=task.timezone,
                workspace_id=workspace_key.workspace_id or "",
                source_id=task.id,
                task_id=task.id,
            ))
        return results

    async def _overdue_tasks(self, workspace_key, trace_id, now_utc):
        from core.user_tasks import UserTaskQuery, UserTaskStatus
        tasks = await self._user_tasks.list(
            UserTaskQuery(status=UserTaskStatus.ACTIVE, limit=200),
            trace_id=trace_id,
        )
        return [
            AgendaItem(
                id=f"agenda-ut-{task.id}",
                source=AgendaItemSource.USER_TASK,
                kind=AgendaItemKind.ATTENTION,
                title=task.title,
                status="overdue",
                due_at=task.due_at,
                timezone=task.timezone,
                workspace_id=workspace_key.workspace_id or "",
                source_id=task.id,
                task_id=task.id,
            )
            for task in tasks
            if task.due_at and task.due_at < now_utc and self._belongs(task, workspace_key)
        ]

    async def _work_log_items(self, workspace_key, trace_id, today_start, today_end):
        from core.memory.models import MemoryQuery, MemoryType
        items = await self._memory.retrieve_memory(
            MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=200)
        )
        results = []
        for item in items:
            content = item.content or {}
            if content.get("type") != "work_log":
                continue
            ts = None
            raw_ts = content.get("date") or ""
            try:
                ts = datetime.fromisoformat(str(raw_ts))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=self._zone)
                ts = ts.astimezone(timezone.utc)
            except (ValueError, TypeError):
                pass
            if ts is None or not (today_start <= ts < today_end):
                continue
            results.append(AgendaItem(
                id=f"agenda-wl-{item.id}",
                source=AgendaItemSource.WORK_LOG,
                kind=AgendaItemKind.COMPLETED,
                title=content.get("subject", "") or content.get("raw_text", "") or str(content)[:120],
                status="completed",
                occurred_at=ts,
                timezone=self._zone.key,
                workspace_id=workspace_key.workspace_id or "",
                source_id=item.id,
            ))
        results.sort(key=lambda x: x.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
        return results

    # -- helpers ------------------------------------------------------

    def _today_bounds(self, now_utc):
        local_now = now_utc.astimezone(self._zone)
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        local_end = local_start + timedelta(days=1)
        return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)

    def _window_bounds(self, now_utc, view, window_hours, today_start, today_end):
        if view == AgendaView.TODAY:
            return today_start, today_end
        if view == AgendaView.COMPLETED:
            return today_start, today_end
        if view == AgendaView.ATTENTION:
            return today_start - timedelta(days=30), today_end
        if view == AgendaView.NEXT:
            return now_utc, now_utc + timedelta(hours=window_hours)
        # ALL
        return today_start - timedelta(days=365), today_end + timedelta(days=365)

    @staticmethod
    def _belongs(task, workspace_key) -> bool:
        ws = task.metadata.get("workspace") if isinstance(task.metadata, dict) else {}
        return ws.get("workspace_id", "default") == (workspace_key.workspace_id or "default")

    @staticmethod
    def _sort_key(item: AgendaItem):
        effective = item.scheduled_for or item.due_at or item.occurred_at or datetime.min.replace(tzinfo=timezone.utc)
        return (effective, kind_priority(item.kind), source_priority(item.source), item.source_id)

    @staticmethod
    def _raise(code: str, message: str, trace_id: str):
        raise FailureException(FailureInfo(
            code=code, category=ErrorCategory.VALIDATION, message=message,
            component=DailyAgendaService.COMPONENT, operation="list",
            retryable=False, trace_id=trace_id,
        ))


def _reminder_kind(status: str) -> AgendaItemKind:
    if status in ("scheduled", "retrying"):
        return AgendaItemKind.ACTION
    if status == "triggered":
        return AgendaItemKind.EVENT
    if status in ("failed",):
        return AgendaItemKind.ATTENTION
    if status in ("cancelled", "completed"):
        return AgendaItemKind.COMPLETED
    return AgendaItemKind.ACTION
