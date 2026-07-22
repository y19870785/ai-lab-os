"""Application service for the canonical Waiting-For lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ValidationError

from core.bus.event import Event
from core.clock import Clock
from core.errors import ErrorCategory, FailureException, FailureInfo, RuntimeStatus
from core.waiting_for.exceptions import (
    WaitingForConflictError,
    WaitingForNotFoundError,
    WaitingForWorkspaceMismatchError,
)
from core.waiting_for.models import (
    WaitingFor,
    WaitingForEvent,
    WaitingForEventPage,
    WaitingForEventType,
    WaitingForMutationResult,
    WaitingForPage,
    WaitingForStatus,
    WaitingForView,
    canonical_workspace,
)
from core.waiting_for.repository import SQLiteWaitingForRepository
from core.workspace.models import WorkspaceKey


class WaitingForService:
    """Own validation, lifecycle rules, failure mapping, and safe event emission."""

    COMPONENT = "waiting_for"

    def __init__(
        self,
        repository: SQLiteWaitingForRepository,
        *,
        bus,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._bus = bus
        self._clock = clock
        self._event_bus_failure: FailureInfo | None = None

    async def initialize(self) -> None:
        try:
            await self._repository.initialize()
        except Exception as exc:
            self._raise_persistence("initialize", exc)

    async def close(self) -> None:
        await self._repository.close()

    async def health(self) -> dict[str, object]:
        repository_health = await self._repository.health_check()
        if repository_health["status"] != RuntimeStatus.OK.value:
            return repository_health
        if self._event_bus_failure is not None:
            return {
                "status": RuntimeStatus.DEGRADED.value,
                "failure": self._event_bus_failure.to_dict(),
            }
        return {"status": RuntimeStatus.OK.value}

    async def create(
        self,
        *,
        workspace_key: WorkspaceKey,
        subject: str,
        waiting_on: str,
        context: str = "",
        expected_by: datetime | None = None,
        next_review_at: datetime | None = None,
        timezone: str = "UTC",
        linked_user_task_id: str | None = None,
        linked_reminder_id: str | None = None,
        source: str,
        trace_id: str = "",
        metadata: dict[str, Any] | None = None,
        waiting_for_id: str | None = None,
    ) -> WaitingForMutationResult:
        now = self._clock.now()
        try:
            values: dict[str, Any] = {
                "workspace_key": canonical_workspace(workspace_key),
                "subject": subject,
                "waiting_on": waiting_on,
                "context": context,
                "expected_by": expected_by,
                "next_review_at": next_review_at,
                "timezone": timezone,
                "linked_user_task_id": linked_user_task_id,
                "linked_reminder_id": linked_reminder_id,
                "source": source,
                "created_at": now,
                "updated_at": now,
                "metadata": metadata or {},
            }
            if waiting_for_id is not None:
                values["id"] = waiting_for_id
            item = WaitingFor(**values)
            event = WaitingForEvent(
                waiting_for_id=item.id,
                workspace_key=item.workspace_key,
                sequence=1,
                event_type=WaitingForEventType.CREATED,
                occurred_at=now,
                source=source,
                trace_id=trace_id or workspace_key.trace_id,
            )
            await self._repository.create(item, event)
        except (ValidationError, ValueError) as exc:
            self._raise_validation("create", exc, trace_id or workspace_key.trace_id)
        except WaitingForConflictError as exc:
            self._raise_conflict("create", exc, trace_id or workspace_key.trace_id)
        except Exception as exc:
            self._raise_persistence("create", exc, trace_id or workspace_key.trace_id)
        await self._publish(item, event)
        return WaitingForMutationResult(item=item, event=event)

    async def get(
        self, *, workspace_key: WorkspaceKey, waiting_for_id: str
    ) -> WaitingFor:
        try:
            return await self._repository.get(workspace_key, waiting_for_id)
        except (WaitingForNotFoundError, WaitingForWorkspaceMismatchError) as exc:
            self._raise_not_found("get", exc, workspace_key.trace_id)
        except Exception as exc:
            self._raise_persistence("get", exc, workspace_key.trace_id)

    async def list(
        self,
        *,
        workspace_key: WorkspaceKey,
        view: str | WaitingForView = WaitingForView.OPEN,
        limit: int = 50,
        offset: int = 0,
    ) -> WaitingForPage:
        try:
            parsed_view = WaitingForView(view)
            if limit < 1 or limit > 200 or offset < 0:
                raise ValueError("invalid pagination")
            return await self._repository.list(
                workspace_key,
                view=parsed_view,
                now=self._clock.now(),
                limit=limit,
                offset=offset,
            )
        except (ValidationError, ValueError) as exc:
            self._raise_validation("list", exc, workspace_key.trace_id)
        except Exception as exc:
            self._raise_persistence("list", exc, workspace_key.trace_id)

    async def list_events(
        self,
        *,
        workspace_key: WorkspaceKey,
        waiting_for_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> WaitingForEventPage:
        if limit < 1 or limit > 200 or offset < 0:
            self._raise_validation(
                "events", ValueError("invalid pagination"), workspace_key.trace_id
            )
        try:
            return await self._repository.list_events(
                workspace_key, waiting_for_id, limit=limit, offset=offset
            )
        except (WaitingForNotFoundError, WaitingForWorkspaceMismatchError) as exc:
            self._raise_not_found("events", exc, workspace_key.trace_id)
        except Exception as exc:
            self._raise_persistence("events", exc, workspace_key.trace_id)

    async def record_follow_up(
        self,
        *,
        workspace_key: WorkspaceKey,
        waiting_for_id: str,
        expected_revision: int,
        note: str,
        next_review_at: datetime | None = None,
        source: str,
        trace_id: str = "",
    ) -> WaitingForMutationResult:
        note = self._required_note(note, "follow_up", trace_id or workspace_key.trace_id)
        current = await self.get(
            workspace_key=workspace_key, waiting_for_id=waiting_for_id
        )
        self._require_open(current, "follow_up", trace_id or workspace_key.trace_id)
        event_metadata: dict[str, Any] = {}
        if next_review_at is not None:
            event_metadata = {
                "previous_next_review_at": (
                    current.next_review_at.isoformat() if current.next_review_at else None
                ),
                "next_review_at": next_review_at.isoformat(),
            }
        return await self._mutate(
            workspace_key=workspace_key,
            current=current,
            expected_revision=expected_revision,
            operation="follow_up",
            event_type=WaitingForEventType.FOLLOWED_UP,
            note=note,
            source=source,
            trace_id=trace_id,
            updates={"next_review_at": next_review_at or current.next_review_at},
            event_metadata=event_metadata,
        )

    async def snooze(
        self,
        *,
        workspace_key: WorkspaceKey,
        waiting_for_id: str,
        expected_revision: int,
        next_review_at: datetime,
        note: str = "",
        source: str,
        trace_id: str = "",
    ) -> WaitingForMutationResult:
        current = await self.get(
            workspace_key=workspace_key, waiting_for_id=waiting_for_id
        )
        self._require_open(current, "snooze", trace_id or workspace_key.trace_id)
        return await self._mutate(
            workspace_key=workspace_key,
            current=current,
            expected_revision=expected_revision,
            operation="snooze",
            event_type=WaitingForEventType.SNOOZED,
            note=note,
            source=source,
            trace_id=trace_id,
            updates={"next_review_at": next_review_at},
            event_metadata={
                "previous_next_review_at": (
                    current.next_review_at.isoformat() if current.next_review_at else None
                ),
                "next_review_at": next_review_at.isoformat(),
            },
        )

    async def resolve(
        self,
        *,
        workspace_key: WorkspaceKey,
        waiting_for_id: str,
        expected_revision: int,
        resolution_note: str,
        source: str,
        trace_id: str = "",
    ) -> WaitingForMutationResult:
        resolution_note = self._required_note(
            resolution_note, "resolve", trace_id or workspace_key.trace_id
        )
        current = await self.get(
            workspace_key=workspace_key, waiting_for_id=waiting_for_id
        )
        self._require_open(current, "resolve", trace_id or workspace_key.trace_id)
        now = self._clock.now()
        return await self._mutate(
            workspace_key=workspace_key,
            current=current,
            expected_revision=expected_revision,
            operation="resolve",
            event_type=WaitingForEventType.RESOLVED,
            note=resolution_note,
            source=source,
            trace_id=trace_id,
            updates={
                "status": WaitingForStatus.RESOLVED,
                "resolved_at": now,
                "cancelled_at": None,
                "resolution_note": resolution_note,
                "next_review_at": None,
            },
        )

    async def cancel(
        self,
        *,
        workspace_key: WorkspaceKey,
        waiting_for_id: str,
        expected_revision: int,
        note: str,
        source: str,
        trace_id: str = "",
    ) -> WaitingForMutationResult:
        note = self._required_note(note, "cancel", trace_id or workspace_key.trace_id)
        current = await self.get(
            workspace_key=workspace_key, waiting_for_id=waiting_for_id
        )
        self._require_open(current, "cancel", trace_id or workspace_key.trace_id)
        now = self._clock.now()
        return await self._mutate(
            workspace_key=workspace_key,
            current=current,
            expected_revision=expected_revision,
            operation="cancel",
            event_type=WaitingForEventType.CANCELLED,
            note=note,
            source=source,
            trace_id=trace_id,
            updates={
                "status": WaitingForStatus.CANCELLED,
                "cancelled_at": now,
                "resolved_at": None,
                "resolution_note": "",
                "next_review_at": None,
            },
        )

    async def reopen(
        self,
        *,
        workspace_key: WorkspaceKey,
        waiting_for_id: str,
        expected_revision: int,
        note: str,
        next_review_at: datetime | None = None,
        source: str,
        trace_id: str = "",
    ) -> WaitingForMutationResult:
        note = self._required_note(note, "reopen", trace_id or workspace_key.trace_id)
        current = await self.get(
            workspace_key=workspace_key, waiting_for_id=waiting_for_id
        )
        if current.status == WaitingForStatus.OPEN:
            self._raise_conflict(
                "reopen", ValueError("item is already open"), trace_id or workspace_key.trace_id
            )
        return await self._mutate(
            workspace_key=workspace_key,
            current=current,
            expected_revision=expected_revision,
            operation="reopen",
            event_type=WaitingForEventType.REOPENED,
            note=note,
            source=source,
            trace_id=trace_id,
            updates={
                "status": WaitingForStatus.OPEN,
                "resolved_at": None,
                "cancelled_at": None,
                "resolution_note": "",
                "next_review_at": next_review_at,
            },
        )

    async def _mutate(
        self,
        *,
        workspace_key: WorkspaceKey,
        current: WaitingFor,
        expected_revision: int,
        operation: str,
        event_type: WaitingForEventType,
        note: str,
        source: str,
        trace_id: str,
        updates: dict[str, Any],
        event_metadata: dict[str, Any] | None = None,
    ) -> WaitingForMutationResult:
        request_trace = trace_id or workspace_key.trace_id
        if expected_revision != current.revision:
            self._raise_conflict(
                operation, ValueError("revision conflict"), request_trace
            )
        now = self._clock.now()
        try:
            values = current.model_dump()
            values.update(updates)
            values.update({"updated_at": now, "revision": current.revision + 1})
            updated = WaitingFor.model_validate(values)
            event = WaitingForEvent(
                waiting_for_id=current.id,
                workspace_key=current.workspace_key,
                sequence=updated.revision,
                event_type=event_type,
                occurred_at=now,
                note=note,
                source=source,
                trace_id=request_trace,
                metadata=event_metadata or {},
            )
            await self._repository.mutate(
                workspace_key,
                updated=updated,
                event=event,
                expected_revision=expected_revision,
            )
        except (ValidationError, ValueError) as exc:
            self._raise_validation(operation, exc, request_trace)
        except WaitingForConflictError as exc:
            self._raise_conflict(operation, exc, request_trace)
        except (WaitingForNotFoundError, WaitingForWorkspaceMismatchError) as exc:
            self._raise_not_found(operation, exc, request_trace)
        except Exception as exc:
            self._raise_persistence(operation, exc, request_trace)
        await self._publish(updated, event)
        return WaitingForMutationResult(item=updated, event=event)

    def _require_open(self, item: WaitingFor, operation: str, trace_id: str) -> None:
        if item.status != WaitingForStatus.OPEN:
            self._raise_conflict(
                operation, ValueError("terminal item cannot be mutated"), trace_id
            )

    def _required_note(self, note: str, operation: str, trace_id: str) -> str:
        note = note.strip()
        if not note:
            self._raise_validation(operation, ValueError("note is required"), trace_id)
        if len(note) > 4_000:
            self._raise_validation(operation, ValueError("note is too long"), trace_id)
        return note

    async def _publish(self, item: WaitingFor, event: WaitingForEvent) -> None:
        if self._bus is None or not getattr(self._bus, "is_running", False):
            return
        try:
            await self._bus.publish(
                f"waiting_for.{event.event_type.value}",
                Event(
                    event_type=f"waiting_for.{event.event_type.value}",
                    timestamp=event.occurred_at,
                    source=self.COMPONENT,
                    payload={
                        "waiting_for_id": item.id,
                        "event_id": event.id,
                        "event_type": event.event_type.value,
                        "status": item.status.value,
                        "revision": item.revision,
                    },
                    metadata={
                        "trace_id": event.trace_id,
                        "component": self.COMPONENT,
                    },
                ),
            )
            self._event_bus_failure = None
        except Exception as exc:
            self._event_bus_failure = FailureInfo(
                code="waiting_for.event_bus.publish_failed",
                category=ErrorCategory.DEPENDENCY_FAILURE,
                message="Waiting-For event publication failed",
                component=self.COMPONENT,
                operation="publish",
                retryable=True,
                trace_id=event.trace_id,
                cause_type=exc.__class__.__name__,
            )

    @staticmethod
    def _raise_failure(
        *,
        code: str,
        category: ErrorCategory,
        operation: str,
        message: str,
        exc: Exception,
        trace_id: str,
        retryable: bool = False,
    ) -> None:
        raise FailureException(
            FailureInfo(
                code=code,
                category=category,
                message=message,
                component=WaitingForService.COMPONENT,
                operation=operation,
                retryable=retryable,
                trace_id=trace_id,
                cause_type=exc.__class__.__name__,
            )
        ) from exc

    @classmethod
    def _raise_validation(cls, operation: str, exc: Exception, trace_id: str = "") -> None:
        cls._raise_failure(
            code=f"waiting_for.{operation}.validation",
            category=ErrorCategory.VALIDATION,
            operation=operation,
            message="Waiting-For request is invalid",
            exc=exc,
            trace_id=trace_id,
        )

    @classmethod
    def _raise_conflict(cls, operation: str, exc: Exception, trace_id: str = "") -> None:
        cls._raise_failure(
            code=f"waiting_for.{operation}.conflict",
            category=ErrorCategory.CONFLICT,
            operation=operation,
            message="Waiting-For state or revision conflict",
            exc=exc,
            trace_id=trace_id,
        )

    @classmethod
    def _raise_not_found(cls, operation: str, exc: Exception, trace_id: str = "") -> None:
        cls._raise_failure(
            code=f"waiting_for.{operation}.not_found",
            category=ErrorCategory.NOT_FOUND,
            operation=operation,
            message="Waiting-For item was not found",
            exc=exc,
            trace_id=trace_id,
        )

    @classmethod
    def _raise_persistence(cls, operation: str, exc: Exception, trace_id: str = "") -> None:
        cls._raise_failure(
            code=f"waiting_for.{operation}.persistence_failure",
            category=ErrorCategory.PERSISTENCE_FAILURE,
            operation=operation,
            message="Waiting-For persistence failed",
            exc=exc,
            trace_id=trace_id,
            retryable=True,
        )
