"""UserTask application service and lifecycle policy."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from core.bus.event import Event
from core.errors import ErrorCategory, FailureException, FailureInfo, failure_from_exception
from core.memory.models import MemoryQuery, MemoryType
from core.user_tasks.exceptions import (
    UserTaskConflictError,
    UserTaskNotFoundError,
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


class UserTaskService:
    COMPONENT = "user_tasks"

    def __init__(self, repository: SQLiteUserTaskRepository, bus=None) -> None:
        self._repository = repository
        self._bus = bus
        self._degraded = False

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
                     source: str = "api", session_id: str = "", agent_id: str = "",
                     trace_id: str = "", metadata: dict[str, Any] | None = None,
                     task_id: str | None = None, legacy_source_id: str | None = None) -> UserTask:
        try:
            task = UserTask(
                **({"id": task_id} if task_id else {}), title=title, description=description,
                priority=priority, due_at=due_at, timezone=timezone, source=source,
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

    async def list(self, query: UserTaskQuery | None = None, trace_id: str = "") -> list[UserTask]:
        try:
            return await self._repository.list(query)
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
            result = await self._repository.update(candidate, expected_revision or current.revision)
            await self._publish("user_task.updated", result.id, trace_id)
            return result
        except Exception as exc:
            await self._publish("user_task.failed", task_id, trace_id, "failed")
            self._raise(exc, "update", trace_id)

    async def _transition(self, task_id: str, target: UserTaskStatus, trace_id: str) -> UserTask:
        current = await self.get(task_id, trace_id)
        if current.status == target:
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
            return result
        except Exception as exc:
            await self._publish("user_task.failed", task_id, trace_id, "failed")
            self._raise(exc, target.value, trace_id)

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
        try:
            items = await memory_manager.retrieve_memory(
                MemoryQuery(memory_type=MemoryType.DECISION, top_k=500)
            )
        except Exception as exc:
            self._degraded = True
            await self._publish("user_task.failed", "legacy_import", trace_id, "failed")
            self._raise(exc, "legacy_import", trace_id)
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
                task_id = "ut_legacy_" + hashlib.sha256(legacy_id.encode()).hexdigest()[:24]
                priority = {"高": UserTaskPriority.HIGH, "低": UserTaskPriority.LOW}.get(
                    content.get("priority"), UserTaskPriority.MEDIUM
                )
                await self.create(
                    task_id=task_id, title=title, description=str(content.get("raw_text", "")),
                    priority=priority, source="legacy_decision_memory", trace_id=trace_id,
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
        if result.failed:
            await self._publish("user_task.failed", "legacy_import", trace_id, "degraded")
        await self._publish(
            "user_task.legacy_imported", "migration", trace_id,
            "degraded" if result.failed else "ok",
        )
        return result

    async def health(self) -> dict[str, object]:
        health = await self._repository.health_check()
        if health["status"] == "healthy" and self._degraded:
            health = {"status": "degraded", "legacy_import_failures": True}
        return health
