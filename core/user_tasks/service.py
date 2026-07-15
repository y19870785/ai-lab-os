"""UserTask application service and lifecycle policy."""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from core.bus.event import Event
from core.errors import ErrorCategory, FailureException, failure_from_exception
from core.memory.models import MemoryQuery, MemoryType
from core.user_tasks.exceptions import (
    UserTaskConflictError,
    UserTaskNotFoundError,
    UserTaskPersistenceError,
)
from core.user_tasks.models import (
    LegacyImportResult,
    UserTask,
    UserTaskPriority,
    UserTaskQuery,
    UserTaskStatus,
    utc_now,
)
from core.user_tasks.repository import SQLiteUserTaskRepository


_UNSET = object()
_LEGACY_PAGE_SIZE = 500


def _legacy_priority(value: Any) -> UserTaskPriority:
    normalized = str(value or "").strip().lower()
    mapping = {
        "": UserTaskPriority.MEDIUM,
        "中": UserTaskPriority.MEDIUM,
        "medium": UserTaskPriority.MEDIUM,
        "normal": UserTaskPriority.MEDIUM,
        "高": UserTaskPriority.HIGH,
        "high": UserTaskPriority.HIGH,
        "urgent": UserTaskPriority.URGENT,
        "紧急": UserTaskPriority.URGENT,
        "低": UserTaskPriority.LOW,
        "low": UserTaskPriority.LOW,
    }
    if normalized not in mapping:
        raise ValueError("unsupported legacy priority")
    return mapping[normalized]


def _legacy_status(value: Any) -> UserTaskStatus:
    normalized = str(value or "").strip().lower()
    mapping = {
        "": UserTaskStatus.ACTIVE,
        "待办": UserTaskStatus.ACTIVE,
        "进行中": UserTaskStatus.ACTIVE,
        "active": UserTaskStatus.ACTIVE,
        "pending": UserTaskStatus.ACTIVE,
        "完成": UserTaskStatus.COMPLETED,
        "已完成": UserTaskStatus.COMPLETED,
        "complete": UserTaskStatus.COMPLETED,
        "completed": UserTaskStatus.COMPLETED,
        "取消": UserTaskStatus.CANCELLED,
        "已取消": UserTaskStatus.CANCELLED,
        "cancel": UserTaskStatus.CANCELLED,
        "cancelled": UserTaskStatus.CANCELLED,
        "canceled": UserTaskStatus.CANCELLED,
    }
    if normalized not in mapping:
        raise ValueError("unsupported legacy status")
    return mapping[normalized]


def _legacy_datetime(value: Any, timezone_name: str, *, date_end: bool = False) -> datetime | None:
    if value in (None, ""):
        return None
    zone = ZoneInfo(timezone_name)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if date_end and len(text) == 10:
            parsed = datetime.combine(datetime.fromisoformat(text).date(), time(23, 59, 59))
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


class UserTaskService:
    COMPONENT = "user_tasks"

    def __init__(self, repository: SQLiteUserTaskRepository, bus=None) -> None:
        self._repository = repository
        self._bus = bus
        self._degraded = False
        self._lifecycle_degraded = False
        self._lifecycle_coordinator = None

    def set_lifecycle_coordinator(self, coordinator) -> None:
        """Composition Root hook for synchronous terminal-state coordination."""
        self._lifecycle_coordinator = coordinator

    async def _coordinate_terminal(self, task, trace_id: str) -> None:
        if self._lifecycle_coordinator is None:
            return
        try:
            await self._lifecycle_coordinator.after_user_task_terminal(task, trace_id)
            self._lifecycle_degraded = False
        except Exception:
            self._lifecycle_degraded = True
            raise

    async def initialize(self) -> None:
        try:
            await self._repository.initialize()
        except Exception as exc:
            await self._publish("user_task.failed", "repository", "", "failed")
            self._raise(exc, "initialize", "")

    async def close(self) -> None:
        await self._repository.close()

    async def _publish(self, event_type: str, task_id: str, trace_id: str, status: str = "ok") -> None:
        if self._bus is None or not getattr(self._bus, "is_running", False):
            return
        await self._bus.publish(event_type, Event(
            event_type=event_type,
            source=self.COMPONENT,
            payload={"task_id": task_id, "status": status},
            metadata={"trace_id": trace_id, "component": self.COMPONENT},
        ))

    def _raise(self, exc: Exception, operation: str, trace_id: str) -> None:
        category = (
            ErrorCategory.NOT_FOUND if isinstance(exc, UserTaskNotFoundError)
            else ErrorCategory.CONFLICT if isinstance(exc, UserTaskConflictError)
            else ErrorCategory.VALIDATION if isinstance(exc, (ValidationError, ValueError))
            else ErrorCategory.PERSISTENCE_FAILURE
        )
        failure = failure_from_exception(
            exc, component=self.COMPONENT, operation=operation, trace_id=trace_id,
            code=f"user_tasks.{operation}.{category.value}", category=category,
            retryable=category == ErrorCategory.PERSISTENCE_FAILURE,
        ).model_copy(update={"message": f"UserTask {operation} failed"})
        raise FailureException(failure) from exc

    async def create(self, *, title: str, description: str = "",
                     priority: UserTaskPriority = UserTaskPriority.MEDIUM,
                     due_at: datetime | None = None, timezone: str = "UTC",
                     status: UserTaskStatus = UserTaskStatus.ACTIVE,
                     created_at: datetime | None = None,
                     completed_at: datetime | None = None,
                     cancelled_at: datetime | None = None,
                     source: str = "api", session_id: str = "", agent_id: str = "",
                     trace_id: str = "", metadata: dict[str, Any] | None = None,
                     task_id: str | None = None, legacy_source_id: str | None = None) -> UserTask:
        try:
            task = UserTask(
                **({"id": task_id} if task_id else {}), title=title, description=description,
                priority=priority, due_at=due_at, timezone=timezone, status=status,
                **({"created_at": created_at, "updated_at": created_at} if created_at else {}),
                completed_at=completed_at, cancelled_at=cancelled_at, source=source,
                session_id=session_id, agent_id=agent_id, trace_id=trace_id,
                metadata=metadata or {}, legacy_source_id=legacy_source_id,
            )
            result = await self._repository.create(task)
            await self._publish("user_task.created", result.id, trace_id)
            return result
        except Exception as exc:
            await self._publish(
                "user_task.failed", task_id or "validation", trace_id, "failed"
            )
            self._raise(exc, "create", trace_id)

    async def get(self, task_id: str, trace_id: str = "") -> UserTask:
        try:
            return await self._repository.get(task_id)
        except Exception as exc:
            await self._publish("user_task.failed", task_id, trace_id, "failed")
            self._raise(exc, "get", trace_id)

    async def list(
        self,
        query: UserTaskQuery | None = None,
        trace_id: str = "",
        *,
        status: UserTaskStatus | None = None,
        priority: UserTaskPriority | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        overdue: bool | None = None,
        limit: int | None = None,
    ) -> list[UserTask]:
        try:
            raw_filters = (status, priority, due_from, due_to, overdue, limit)
            if query is not None and any(value is not None for value in raw_filters):
                raise ValueError("query model and raw filters are mutually exclusive")
            spec = query or UserTaskQuery(
                status=status,
                priority=priority,
                due_from=due_from,
                due_to=due_to,
                overdue=overdue,
                limit=100 if limit is None else limit,
            )
            return await self._repository.list(spec)
        except Exception as exc:
            await self._publish("user_task.failed", "query", trace_id, "failed")
            self._raise(exc, "list", trace_id)

    async def update(self, task_id: str, *, title: str | None = None,
                     description: str | None = None, priority: UserTaskPriority | None = None,
                     due_at: datetime | None | object = _UNSET, timezone: str | None = None,
                     metadata: dict[str, Any] | None = None, expected_revision: int | None = None,
                     trace_id: str = "") -> UserTask:
        current = await self.get(task_id, trace_id)
        if current.status != UserTaskStatus.ACTIVE:
            self._raise(UserTaskConflictError("terminal task cannot be edited"), "update", trace_id)
        changes: dict[str, Any] = {"updated_at": utc_now(), "trace_id": trace_id or current.trace_id}
        for key, value in (("title", title), ("description", description), ("priority", priority),
                           ("timezone", timezone), ("metadata", metadata)):
            if value is not None:
                changes[key] = value
        if due_at is not _UNSET:
            changes["due_at"] = due_at
        try:
            candidate = UserTask.model_validate({**current.model_dump(), **changes})
            revision = current.revision if expected_revision is None else expected_revision
            result = await self._repository.update(candidate, revision)
            await self._publish("user_task.updated", result.id, trace_id)
            return result
        except Exception as exc:
            await self._publish("user_task.failed", task_id, trace_id, "failed")
            self._raise(exc, "update", trace_id)

    async def _transition(self, task_id: str, target: UserTaskStatus, trace_id: str) -> UserTask:
        current = await self.get(task_id, trace_id)
        if current.status == target:
            await self._coordinate_terminal(current, trace_id)
            return current
        if current.status != UserTaskStatus.ACTIVE:
            await self._publish("user_task.failed", task_id, trace_id, "failed")
            self._raise(UserTaskConflictError("invalid terminal state transition"), target.value, trace_id)
        now = utc_now()
        changes = {"status": target, "updated_at": now, "trace_id": trace_id or current.trace_id}
        changes["completed_at" if target == UserTaskStatus.COMPLETED else "cancelled_at"] = now
        try:
            result = await self._repository.update(current.model_copy(update=changes), current.revision)
            await self._publish(f"user_task.{target.value}", result.id, trace_id)
        except Exception as exc:
            await self._publish("user_task.failed", task_id, trace_id, "failed")
            self._raise(exc, target.value, trace_id)
        await self._coordinate_terminal(result, trace_id)
        return result

    async def complete(self, task_id: str, trace_id: str = "") -> UserTask:
        return await self._transition(task_id, UserTaskStatus.COMPLETED, trace_id)

    async def cancel(self, task_id: str, trace_id: str = "") -> UserTask:
        return await self._transition(task_id, UserTaskStatus.CANCELLED, trace_id)

    async def reopen(self, task_id: str, trace_id: str = "") -> UserTask:
        current = await self.get(task_id, trace_id)
        if current.status == UserTaskStatus.ACTIVE:
            return current
        candidate = current.model_copy(update={
            "status": UserTaskStatus.ACTIVE, "updated_at": utc_now(),
            "completed_at": None, "cancelled_at": None,
        })
        try:
            result = await self._repository.update(candidate, current.revision)
            await self._publish("user_task.reopened", result.id, trace_id)
            return result
        except Exception as exc:
            await self._publish("user_task.failed", task_id, trace_id, "failed")
            self._raise(exc, "reopen", trace_id)

    async def import_legacy(self, memory_manager, trace_id: str = "") -> LegacyImportResult:
        result = LegacyImportResult()
        offset = 0
        seen_pages: set[tuple[str, ...]] = set()
        while True:
            try:
                items = await memory_manager.retrieve_memory(MemoryQuery(
                    memory_type=MemoryType.DECISION,
                    top_k=_LEGACY_PAGE_SIZE,
                    offset=offset,
                ))
            except Exception as exc:
                self._degraded = True
                await self._publish("user_task.failed", "legacy_import", trace_id, "failed")
                self._raise(exc, "legacy_import", trace_id)
            if not items:
                break
            page_signature = tuple(str(getattr(item, "id", "")) for item in items)
            if page_signature in seen_pages:
                self._degraded = True
                await self._publish("user_task.failed", "legacy_import", trace_id, "failed")
                self._raise(
                    UserTaskPersistenceError("Legacy memory pagination did not advance"),
                    "legacy_import",
                    trace_id,
                )
            seen_pages.add(page_signature)
            for item in items:
                try:
                    content = getattr(item, "content", None)
                    if not isinstance(content, dict):
                        raise ValueError("legacy task content must be an object")
                    if content.get("type") != "task":
                        result.skipped += 1
                        continue
                    raw_legacy_id = getattr(item, "id", None)
                    title = str(content.get("title") or content.get("subject") or "").strip()
                    if not raw_legacy_id or not title:
                        raise ValueError("legacy task requires id and title")
                    legacy_id = str(raw_legacy_id)
                    item_metadata = getattr(item, "metadata", {})
                    if not isinstance(item_metadata, dict):
                        item_metadata = {}
                    timezone_name = str(
                        content.get("timezone") or item_metadata.get("timezone")
                        or "Asia/Shanghai"
                    )
                    priority = _legacy_priority(content.get("priority"))
                    status = _legacy_status(content.get("status"))
                    due_at = _legacy_datetime(
                        content.get("deadline"), timezone_name, date_end=True
                    )
                    created_at = _legacy_datetime(
                        getattr(item, "timestamp", None), timezone_name
                    ) or utc_now()
                    completed_at = _legacy_datetime(
                        content.get("completed_at") or item_metadata.get("completed_at"),
                        timezone_name,
                    )
                    cancelled_at = _legacy_datetime(
                        content.get("cancelled_at") or item_metadata.get("cancelled_at"),
                        timezone_name,
                    )
                    task_id = "ut_legacy_" + hashlib.sha256(legacy_id.encode()).hexdigest()[:24]
                    await self.create(
                        task_id=task_id,
                        title=title,
                        description=str(content.get("raw_text", "")),
                        priority=priority,
                        due_at=due_at,
                        timezone=timezone_name,
                        status=status,
                        created_at=created_at,
                        completed_at=(
                            completed_at if status == UserTaskStatus.COMPLETED else None
                        ),
                        cancelled_at=(
                            cancelled_at if status == UserTaskStatus.CANCELLED else None
                        ),
                        source=str(
                            content.get("source") or item_metadata.get("source")
                            or "legacy_decision_memory"
                        ),
                        session_id=str(
                            content.get("session_id") or item_metadata.get("session_id") or ""
                        ),
                        agent_id=str(
                            content.get("agent_id") or item_metadata.get("agent_id") or ""
                        ),
                        trace_id=trace_id,
                        metadata={"legacy_imported": True},
                        legacy_source_id=legacy_id,
                    )
                    result.imported += 1
                except FailureException as exc:
                    if exc.failure.category == ErrorCategory.CONFLICT:
                        result.skipped += 1
                    else:
                        result.failed += 1
                        self._degraded = True
                except Exception:
                    result.failed += 1
                    self._degraded = True
            offset += len(items)
            if len(items) < _LEGACY_PAGE_SIZE:
                break
        if result.failed:
            await self._publish("user_task.failed", "legacy_import", trace_id, "degraded")
        await self._publish(
            "user_task.legacy_imported", "migration", trace_id,
            "degraded" if result.failed else "ok",
        )
        return result

    async def health(self) -> dict[str, object]:
        health = await self._repository.health_check()
        if health["status"] == "healthy" and (self._degraded or self._lifecycle_degraded):
            health = {
                "status": "degraded",
                "legacy_import_failures": self._degraded,
                "reminder_reconciliation_required": self._lifecycle_degraded,
            }
        return health
