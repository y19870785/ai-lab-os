"""Application service for capture-to-action Inbox workflows."""

from __future__ import annotations

import asyncio
import hashlib
import weakref
from datetime import datetime
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from core.bus.event import Event
from core.clock import Clock
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.inbox.exceptions import (
    InboxItemNotFoundError,
    InboxRepositoryError,
    InboxRevisionConflictError,
    InboxWorkspaceMismatchError,
)
from core.inbox.models import (
    InboxItem,
    InboxPage,
    InboxResolvedType,
    InboxStatus,
    InboxSuggestedType,
    canonical_workspace,
)
from core.inbox.repository import SQLiteInboxRepository
from core.memory.models import MemoryType
from core.user_tasks import UserTaskPriority
from core.workspace.models import WorkspaceKey


class InboxService:
    """Captures first, then resolves only through an explicit operation."""

    COMPONENT = "inbox"

    def __init__(
        self,
        repository: SQLiteInboxRepository,
        *,
        clock: Clock,
        user_tasks=None,
        reminder_orchestrator=None,
        memory_manager=None,
        bus=None,
        timezone_name: str = "UTC",
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._user_tasks = user_tasks
        self._reminder_orchestrator = reminder_orchestrator
        self._memory = memory_manager
        self._bus = bus
        self._timezone_name = timezone_name
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

    async def initialize(self) -> None:
        try:
            await self._repository.initialize()
        except Exception as exc:
            self._raise("inbox.resolve_failed", ErrorCategory.PERSISTENCE_FAILURE, "initialize", exc)

    async def close(self) -> None:
        await self._repository.close()

    @staticmethod
    def _workspace_dict(workspace_key: WorkspaceKey) -> dict[str, str]:
        workspace = canonical_workspace(workspace_key)
        return {
            "tenant_id": workspace.tenant_id,
            "workspace_id": workspace.workspace_id,
            "namespace": workspace.namespace,
        }

    @staticmethod
    def _workspace_scope(workspace_key: WorkspaceKey) -> str:
        workspace = InboxService._workspace_dict(workspace_key)
        return "/".join(
            (workspace["tenant_id"], workspace["workspace_id"], workspace["namespace"])
        )

    @staticmethod
    def _target_id(prefix: str, item_id: str) -> str:
        digest = hashlib.sha256(f"{prefix}|{item_id}".encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"

    @staticmethod
    def _raise(
        code: str,
        category: ErrorCategory,
        operation: str,
        exc: Exception | None = None,
        *,
        trace_id: str = "",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        messages = {
            "inbox.not_found": "Inbox item was not found",
            "inbox.invalid_content": "Inbox content is invalid",
            "inbox.invalid_status": "Inbox status is invalid",
            "inbox.already_resolved": "Inbox item has already been resolved",
            "inbox.resolve_failed": "Inbox item resolution failed",
            "inbox.workspace_mismatch": "Inbox item belongs to another workspace",
        }
        failure = FailureInfo(
            code=code,
            category=category,
            message=messages[code],
            component=InboxService.COMPONENT,
            operation=operation,
            retryable=retryable,
            trace_id=trace_id,
            cause_type=exc.__class__.__name__ if exc else "",
            details=details or {},
        )
        raise FailureException(failure) from exc

    async def _publish(self, event_type: str, item: InboxItem) -> None:
        if self._bus is None or not getattr(self._bus, "is_running", False):
            return
        workspace = self._workspace_dict(item.workspace_key)
        await self._bus.publish(
            event_type,
            Event(
                event_type=event_type,
                timestamp=self._clock.now(),
                source=self.COMPONENT,
                payload={
                    "inbox_item_id": item.id,
                    "workspace_key": workspace,
                    "source": item.source,
                    "status": item.status.value,
                    "resolved_type": item.resolved_type.value if item.resolved_type else None,
                    "resolved_target_id": item.resolved_target_id,
                },
                metadata={"trace_id": item.workspace_key.trace_id},
            ),
        )

    async def capture(
        self,
        *,
        workspace_key: WorkspaceKey,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
        suggested_type: InboxSuggestedType = InboxSuggestedType.UNKNOWN,
    ) -> InboxItem:
        now = self._clock.now()
        try:
            item = InboxItem(
                workspace_key=canonical_workspace(workspace_key),
                content=content,
                source=source,
                suggested_type=suggested_type,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )
            item = await self._repository.save(item)
        except (ValidationError, ValueError) as exc:
            self._raise(
                "inbox.invalid_content",
                ErrorCategory.VALIDATION,
                "capture",
                exc,
                trace_id=workspace_key.trace_id,
            )
        except Exception as exc:
            self._raise(
                "inbox.resolve_failed",
                ErrorCategory.PERSISTENCE_FAILURE,
                "capture",
                exc,
                trace_id=workspace_key.trace_id,
                retryable=True,
            )
        await self._publish("inbox.captured", item)
        return item

    async def list(
        self,
        *,
        workspace_key: WorkspaceKey,
        status: str | InboxStatus = InboxStatus.PENDING,
        limit: int = 50,
        offset: int = 0,
    ) -> InboxPage:
        try:
            parsed_status = None if status == "all" else InboxStatus(status)
            if limit < 1 or limit > 200 or offset < 0:
                raise ValueError("invalid pagination")
            return await self._repository.list(
                workspace_key,
                status=parsed_status,
                limit=limit,
                offset=offset,
            )
        except (ValueError, ValidationError) as exc:
            self._raise(
                "inbox.invalid_status",
                ErrorCategory.VALIDATION,
                "list",
                exc,
                trace_id=workspace_key.trace_id,
            )
        except Exception as exc:
            self._raise(
                "inbox.resolve_failed",
                ErrorCategory.PERSISTENCE_FAILURE,
                "list",
                exc,
                trace_id=workspace_key.trace_id,
                retryable=True,
            )

    async def get(self, *, workspace_key: WorkspaceKey, inbox_item_id: str) -> InboxItem:
        try:
            return await self._repository.get(workspace_key, inbox_item_id)
        except InboxItemNotFoundError as exc:
            self._raise(
                "inbox.not_found",
                ErrorCategory.NOT_FOUND,
                "get",
                exc,
                trace_id=workspace_key.trace_id,
            )
        except InboxWorkspaceMismatchError as exc:
            self._raise(
                "inbox.workspace_mismatch",
                ErrorCategory.PERMISSION_DENIED,
                "get",
                exc,
                trace_id=workspace_key.trace_id,
            )
        except Exception as exc:
            self._raise(
                "inbox.resolve_failed",
                ErrorCategory.PERSISTENCE_FAILURE,
                "get",
                exc,
                trace_id=workspace_key.trace_id,
                retryable=True,
            )

    async def _pending(self, workspace_key: WorkspaceKey, inbox_item_id: str) -> InboxItem:
        item = await self.get(workspace_key=workspace_key, inbox_item_id=inbox_item_id)
        if item.status != InboxStatus.PENDING:
            self._raise(
                "inbox.already_resolved",
                ErrorCategory.CONFLICT,
                "resolve",
                trace_id=workspace_key.trace_id,
                details={
                    "status": item.status.value,
                    "resolved_type": item.resolved_type.value if item.resolved_type else None,
                    "resolved_target_id": item.resolved_target_id,
                },
            )
        return item

    async def _resolve(
        self,
        *,
        workspace_key: WorkspaceKey,
        inbox_item_id: str,
        resolved_type: InboxResolvedType,
        create_target: Callable[[InboxItem], Awaitable[str | None]],
    ) -> InboxItem:
        lock = self._locks.setdefault(inbox_item_id, asyncio.Lock())
        async with lock:
            item = await self._pending(workspace_key, inbox_item_id)
            try:
                target_id = await create_target(item)
                now = self._clock.now()
                resolved = item.model_copy(
                    update={
                        "status": InboxStatus.RESOLVED,
                        "updated_at": now,
                        "resolved_at": now,
                        "resolved_type": resolved_type,
                        "resolved_target_id": target_id,
                    }
                )
                resolved = InboxItem.model_validate(resolved.model_dump())
                resolved = await self._repository.resolve(
                    resolved, expected_revision=item.revision
                )
            except FailureException as exc:
                await self._publish("inbox.resolve_failed", item)
                self._raise(
                    "inbox.resolve_failed",
                    exc.failure.category,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                    details={"dependency_code": exc.failure.code},
                    retryable=exc.failure.retryable,
                )
            except InboxRevisionConflictError as exc:
                current = await self.get(
                    workspace_key=workspace_key, inbox_item_id=inbox_item_id
                )
                if current.status != InboxStatus.PENDING:
                    self._raise(
                        "inbox.already_resolved",
                        ErrorCategory.CONFLICT,
                        "resolve",
                        exc,
                        trace_id=workspace_key.trace_id,
                        details={
                            "status": current.status.value,
                            "resolved_type": (
                                current.resolved_type.value
                                if current.resolved_type else None
                            ),
                            "resolved_target_id": current.resolved_target_id,
                        },
                    )
                await self._publish("inbox.resolve_failed", item)
                self._raise(
                    "inbox.resolve_failed",
                    ErrorCategory.CONFLICT,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                    retryable=True,
                )
            except InboxRepositoryError as exc:
                await self._publish("inbox.resolve_failed", item)
                self._raise(
                    "inbox.resolve_failed",
                    ErrorCategory.PERSISTENCE_FAILURE,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                    details={"resolved_target_id": locals().get("target_id")},
                    retryable=True,
                )
            except (ValidationError, ValueError) as exc:
                await self._publish("inbox.resolve_failed", item)
                self._raise(
                    "inbox.resolve_failed",
                    ErrorCategory.VALIDATION,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                )
            except Exception as exc:
                await self._publish("inbox.resolve_failed", item)
                self._raise(
                    "inbox.resolve_failed",
                    ErrorCategory.INTERNAL,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                )
            await self._publish("inbox.resolved", resolved)
            return resolved

    async def resolve_to_task(
        self,
        *,
        workspace_key: WorkspaceKey,
        inbox_item_id: str,
        title: str,
        description: str = "",
        due_at: datetime | None = None,
        priority: UserTaskPriority = UserTaskPriority.MEDIUM,
    ) -> InboxItem:
        async def create(item: InboxItem) -> str:
            if self._user_tasks is None:
                raise RuntimeError("UserTask service is not configured")
            task_id = self._target_id("ut_inbox", item.id)
            metadata = {
                "workspace": self._workspace_dict(workspace_key),
                "inbox_item_id": item.id,
                "inbox_source": item.source,
            }
            try:
                task = await self._user_tasks.create(
                    task_id=task_id,
                    title=title,
                    description=description,
                    priority=priority,
                    due_at=due_at,
                    timezone=self._timezone_name,
                    created_at=self._clock.now(),
                    source="inbox",
                    trace_id=workspace_key.trace_id,
                    metadata=metadata,
                )
            except FailureException as exc:
                if exc.failure.category != ErrorCategory.CONFLICT:
                    raise
                task = await self._user_tasks.get(task_id, workspace_key.trace_id)
                if task.metadata.get("inbox_item_id") != item.id:
                    raise
            return task.id

        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.USER_TASK,
            create_target=create,
        )

    async def resolve_to_reminder(
        self,
        *,
        workspace_key: WorkspaceKey,
        inbox_item_id: str,
        title: str,
        scheduled_at: datetime,
        description: str = "",
        priority: UserTaskPriority = UserTaskPriority.MEDIUM,
        timezone_name: str | None = None,
    ) -> InboxItem:
        async def create(item: InboxItem) -> str:
            if self._reminder_orchestrator is None:
                raise RuntimeError("Reminder service is not configured")
            workspace = self._workspace_dict(workspace_key)
            result = await self._reminder_orchestrator.create_for_task(
                title=title,
                due_at=scheduled_at,
                timezone_name=timezone_name or self._timezone_name,
                priority=priority,
                description=description,
                session_id=workspace_key.session_id,
                trace_id=workspace_key.trace_id,
                workspace_scope=self._workspace_scope(workspace_key),
                idempotency_key=f"inbox:{item.id}:reminder",
                workspace=workspace,
            )
            return result.reminder_id

        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.REMINDER,
            create_target=create,
        )

    async def resolve_to_work_log(
        self,
        *,
        workspace_key: WorkspaceKey,
        inbox_item_id: str,
        title: str,
        description: str = "",
    ) -> InboxItem:
        async def create(item: InboxItem) -> str:
            if self._memory is None:
                raise RuntimeError("Memory service is not configured")
            memory_id = self._target_id("inbox_wl", item.id)
            workspace = self._workspace_dict(workspace_key)
            local_date = self._clock.now().astimezone(ZoneInfo(self._timezone_name)).date()
            return await self._memory.save_memory(
                MemoryType.EPISODIC,
                {
                    "type": "work_log",
                    "raw_text": description or item.content,
                    "date": local_date.isoformat(),
                    "subject": title,
                    "status": "completed",
                    "tags": ["inbox"],
                    "metadata": workspace,
                },
                importance=0.6,
                item_id=memory_id,
                metadata={
                    "source": "inbox",
                    "inbox_item_id": item.id,
                    "workspace_id": workspace["workspace_id"],
                },
            )

        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.WORK_LOG,
            create_target=create,
        )

    async def resolve_as_note(
        self, *, workspace_key: WorkspaceKey, inbox_item_id: str
    ) -> InboxItem:
        async def create(_item: InboxItem) -> None:
            return None

        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.NOTE,
            create_target=create,
        )

    async def dismiss(
        self, *, workspace_key: WorkspaceKey, inbox_item_id: str
    ) -> InboxItem:
        lock = self._locks.setdefault(inbox_item_id, asyncio.Lock())
        async with lock:
            item = await self._pending(workspace_key, inbox_item_id)
            now = self._clock.now()
            dismissed = item.model_copy(
                update={
                    "status": InboxStatus.DISMISSED,
                    "updated_at": now,
                    "resolved_at": now,
                    "resolved_type": InboxResolvedType.DISMISSED,
                }
            )
            dismissed = InboxItem.model_validate(dismissed.model_dump())
            try:
                dismissed = await self._repository.dismiss(
                    dismissed, expected_revision=item.revision
                )
            except Exception as exc:
                self._raise(
                    "inbox.resolve_failed",
                    ErrorCategory.PERSISTENCE_FAILURE,
                    "dismiss",
                    exc,
                    trace_id=workspace_key.trace_id,
                    retryable=True,
                )
            await self._publish("inbox.dismissed", dismissed)
            return dismissed
