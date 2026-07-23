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
    InboxResolutionClaimConflictError,
    InboxRevisionConflictError,
    InboxWorkspaceMismatchError,
)
from core.inbox.models import (
    InboxItem,
    InboxPage,
    InboxResolutionClaim,
    InboxResolutionClaimState,
    InboxResolvedType,
    InboxStatus,
    InboxSuggestedType,
    canonical_workspace,
)
from core.inbox.repository import SQLiteInboxRepository
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
        work_log_service=None,
        waiting_for_service=None,
        bus=None,
        timezone_name: str = "UTC",
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._user_tasks = user_tasks
        self._reminder_orchestrator = reminder_orchestrator
        self._memory = memory_manager
        self._work_logs = work_log_service
        self._waiting_for = waiting_for_service
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
            "inbox.waiting_for.fields_missing": "Waiting-For confirmation fields are missing",
            "inbox.waiting_for.timezone_invalid": "Waiting-For timezone is invalid",
            "inbox.waiting_for.unavailable": "Waiting-For service is unavailable",
            "inbox.waiting_for.source_mismatch": "Waiting-For source metadata does not match the Inbox item",
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

    @staticmethod
    def _claim_details(claim: InboxResolutionClaim) -> dict[str, Any]:
        return {
            "claimed_type": claim.resolved_type.value,
            "target_id": claim.target_id,
            "claim_state": claim.state.value,
            "resolved_type": claim.resolved_type.value,
            "resolved_target_id": claim.target_id,
        }

    def _raise_claim_conflict(
        self,
        claim: InboxResolutionClaim,
        workspace_key: WorkspaceKey,
        exc: Exception | None = None,
    ) -> None:
        self._raise(
            "inbox.already_resolved",
            ErrorCategory.CONFLICT,
            "resolve",
            exc,
            trace_id=workspace_key.trace_id,
            details=self._claim_details(claim),
        )

    async def _resolve(
        self,
        *,
        workspace_key: WorkspaceKey,
        inbox_item_id: str,
        resolved_type: InboxResolvedType,
        target_key: str | None,
        reserved_target_id: str | None,
        create_target: Callable[
            [InboxItem, InboxResolutionClaim], Awaitable[str]
        ] | None,
        return_completed: bool = False,
    ) -> InboxItem:
        """Resolve through a durable claim; the in-memory lock is only an optimization."""

        lock = self._locks.setdefault(inbox_item_id, asyncio.Lock())
        async with lock:
            try:
                claim = await self._repository.claim_resolution(
                    workspace_key,
                    inbox_item_id,
                    resolved_type=resolved_type,
                    target_key=target_key,
                    target_id=reserved_target_id,
                    now=self._clock.now(),
                )
            except InboxItemNotFoundError as exc:
                self._raise(
                    "inbox.not_found",
                    ErrorCategory.NOT_FOUND,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                )
            except InboxWorkspaceMismatchError as exc:
                self._raise(
                    "inbox.workspace_mismatch",
                    ErrorCategory.PERMISSION_DENIED,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                )
            except InboxRevisionConflictError as exc:
                item = await self.get(
                    workspace_key=workspace_key, inbox_item_id=inbox_item_id
                )
                self._raise(
                    "inbox.already_resolved",
                    ErrorCategory.CONFLICT,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                    details={
                        "claimed_type": (
                            item.resolved_type.value if item.resolved_type else None
                        ),
                        "target_id": item.resolved_target_id,
                        "claim_state": "missing",
                    },
                )
            except InboxRepositoryError as exc:
                self._raise(
                    "inbox.resolve_failed",
                    ErrorCategory.PERSISTENCE_FAILURE,
                    "claim_resolution",
                    exc,
                    trace_id=workspace_key.trace_id,
                    retryable=True,
                )

            if claim.resolved_type != resolved_type:
                self._raise_claim_conflict(claim, workspace_key)
            if claim.state == InboxResolutionClaimState.COMPLETED:
                completed = await self.get(
                    workspace_key=workspace_key, inbox_item_id=inbox_item_id
                )
                if (
                    return_completed
                    and completed.resolved_type == resolved_type
                    and completed.resolved_target_id == claim.target_id
                ):
                    return completed
                self._raise_claim_conflict(claim, workspace_key)

            item = await self.get(
                workspace_key=workspace_key, inbox_item_id=inbox_item_id
            )
            if item.status != InboxStatus.PENDING:
                current = await self._repository.get_resolution_claim(
                    workspace_key, inbox_item_id
                )
                self._raise_claim_conflict(current, workspace_key)

            try:
                claim = await self._repository.get_resolution_claim(
                    workspace_key, inbox_item_id
                )
                if create_target is not None and (
                    claim.state == InboxResolutionClaimState.CLAIMED
                ):
                    target_id = await create_target(item, claim)
                    claim = await self._repository.record_target_created(
                        workspace_key,
                        inbox_item_id,
                        resolved_type=resolved_type,
                        target_id=target_id,
                        now=self._clock.now(),
                    )
                resolved, claim = await self._repository.complete_resolution(
                    workspace_key,
                    inbox_item_id,
                    resolved_type=resolved_type,
                    now=self._clock.now(),
                )
            except FailureException as exc:
                await self._publish("inbox.resolve_failed", item)
                if resolved_type == InboxResolvedType.WAITING_FOR:
                    raise
                self._raise(
                    "inbox.resolve_failed",
                    exc.failure.category,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                    details={"dependency_code": exc.failure.code},
                    retryable=exc.failure.retryable,
                )
            except (InboxResolutionClaimConflictError, InboxRevisionConflictError) as exc:
                current = await self._repository.get_resolution_claim(
                    workspace_key, inbox_item_id
                )
                if current.resolved_type != resolved_type or (
                    current.state == InboxResolutionClaimState.COMPLETED
                ):
                    self._raise_claim_conflict(current, workspace_key, exc)
                await self._publish("inbox.resolve_failed", item)
                self._raise(
                    "inbox.resolve_failed",
                    ErrorCategory.CONFLICT,
                    "resolve",
                    exc,
                    trace_id=workspace_key.trace_id,
                    details=self._claim_details(current),
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
                    details=self._claim_details(claim),
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
            await self._publish(
                "inbox.dismissed"
                if resolved_type == InboxResolvedType.DISMISSED
                else "inbox.resolved",
                resolved,
            )
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
        task_id = self._target_id("ut_inbox", inbox_item_id)

        async def create(item: InboxItem, claim: InboxResolutionClaim) -> str:
            if self._user_tasks is None:
                raise RuntimeError("UserTask service is not configured")
            task_id = claim.target_key
            if not task_id:
                raise RuntimeError("UserTask claim target is missing")
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
            target_key=task_id,
            reserved_target_id=task_id,
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
        idempotency_key = f"inbox:{inbox_item_id}:reminder"

        async def create(item: InboxItem, claim: InboxResolutionClaim) -> str:
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
                idempotency_key=claim.target_key or idempotency_key,
                workspace=workspace,
            )
            return result.reminder_id

        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.REMINDER,
            target_key=idempotency_key,
            reserved_target_id=None,
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
        work_log_id = (
            "wl_"
            + hashlib.sha256(
                f"work_log|{inbox_item_id}".encode("utf-8")
            ).hexdigest()[:32]
        )

        async def create(item: InboxItem, claim: InboxResolutionClaim) -> str:
            if self._work_logs is None:
                raise RuntimeError("Work Log service is not configured")
            reserved_id = claim.target_key
            if not reserved_id:
                raise RuntimeError("Work Log claim target is missing")
            record = await self._work_logs.create_from_inbox(
                workspace_key=workspace_key,
                inbox_item_id=item.id,
                subject=title,
                raw_text=description or item.content,
                reserved_id=reserved_id,
            )
            return (
                reserved_id
                if reserved_id.startswith("inbox_wl_")
                else record.id
            )

        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.WORK_LOG,
            target_key=work_log_id,
            reserved_target_id=work_log_id,
            create_target=create,
            return_completed=True,
        )

    async def resolve_to_waiting_for(
        self,
        *,
        workspace_key: WorkspaceKey,
        inbox_item_id: str,
        subject: str,
        waiting_on: str,
        context: str = "",
        expected_by: datetime | None = None,
        next_review_at: datetime | None = None,
        timezone: str | None = None,
    ) -> InboxItem:
        """Confirm one Inbox item into one deterministic canonical Waiting-For."""

        subject = subject.strip()
        waiting_on = waiting_on.strip()
        missing = []
        if not subject:
            missing.append("subject")
        if not waiting_on:
            missing.append("waiting_on")
        if expected_by is None and next_review_at is None:
            missing.append("expected_by_or_next_review_at")
        if missing:
            self._raise(
                "inbox.waiting_for.fields_missing",
                ErrorCategory.VALIDATION,
                "resolve_to_waiting_for",
                trace_id=workspace_key.trace_id,
                details={
                    "missing_fields": missing,
                    "confirmation_template": (
                        "python -m cli inbox resolve-waiting-for "
                        f"{inbox_item_id} --subject <事项> --waiting-on <对象> "
                        "--next-review-at <ISO-8601> --timezone <IANA>"
                    ),
                },
            )
        timezone_name = timezone or self._timezone_name
        try:
            ZoneInfo(timezone_name)
        except (ValueError, KeyError) as exc:
            self._raise(
                "inbox.waiting_for.timezone_invalid",
                ErrorCategory.VALIDATION,
                "resolve_to_waiting_for",
                exc,
                trace_id=workspace_key.trace_id,
                details={"timezone": timezone_name},
            )
        if self._waiting_for is None:
            self._raise(
                "inbox.waiting_for.unavailable",
                ErrorCategory.UNAVAILABLE,
                "resolve_to_waiting_for",
                trace_id=workspace_key.trace_id,
            )

        target_id = self._target_id("wf_inbox", inbox_item_id)

        async def create(item: InboxItem, claim: InboxResolutionClaim) -> str:
            metadata = {
                "inbox_item_id": item.id,
                "inbox_source": item.source,
            }
            try:
                result = await self._waiting_for.create(
                    workspace_key=workspace_key,
                    subject=subject,
                    waiting_on=waiting_on,
                    context=context,
                    expected_by=expected_by,
                    next_review_at=next_review_at,
                    timezone=timezone_name,
                    source="inbox",
                    trace_id=workspace_key.trace_id,
                    metadata=metadata,
                    waiting_for_id=claim.target_key or target_id,
                )
                return result.item.id
            except FailureException as exc:
                if exc.failure.category != ErrorCategory.CONFLICT:
                    raise
                existing = await self._waiting_for.get(
                    workspace_key=workspace_key,
                    waiting_for_id=claim.target_key or target_id,
                )
                if (
                    existing.metadata.get("inbox_item_id") != item.id
                    or existing.metadata.get("inbox_source") != item.source
                ):
                    self._raise(
                        "inbox.waiting_for.source_mismatch",
                        ErrorCategory.CONFLICT,
                        "resolve_to_waiting_for",
                        exc,
                        trace_id=workspace_key.trace_id,
                        details={
                            "waiting_for_id": existing.id,
                            "inbox_item_id": item.id,
                        },
                    )
                return existing.id

        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.WAITING_FOR,
            target_key=target_id,
            reserved_target_id=target_id,
            create_target=create,
            return_completed=True,
        )

    async def resolve_as_note(
        self, *, workspace_key: WorkspaceKey, inbox_item_id: str
    ) -> InboxItem:
        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.NOTE,
            target_key=None,
            reserved_target_id=None,
            create_target=None,
        )

    async def dismiss(
        self, *, workspace_key: WorkspaceKey, inbox_item_id: str
    ) -> InboxItem:
        return await self._resolve(
            workspace_key=workspace_key,
            inbox_item_id=inbox_item_id,
            resolved_type=InboxResolvedType.DISMISSED,
            target_key=None,
            reserved_target_id=None,
            create_target=None,
        )
