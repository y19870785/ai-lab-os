"""Deterministic, read-only aggregation for Daily Review."""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from core.clock import Clock
from core.daily_review.models import (
    DEFAULT_DAILY_REVIEW_LIMIT,
    DEFAULT_DAILY_REVIEW_OFFSET,
    DailyReview,
    DailyReviewDate,
    DailyReviewItem,
    DailyReviewPage,
    DailyReviewQuery,
    DailyReviewSection,
    DailyReviewSourceStatus,
    DailyReviewSourceType,
    DailyReviewWorkspace,
)
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.inbox import InboxStatus
from core.reminders import ReminderInboxStatus
from core.user_tasks import UserTaskQuery, UserTaskStatus
from core.waiting_for import WaitingForStatus, WaitingForView
from core.work_log import WorkLogQuery, WorkLogStatus
from core.workspace.models import WorkspaceKey

_SECTION_PRIORITY = {
    "blocked": 0,
    "follow_ups": 1,
    "in_progress": 2,
    "completed": 3,
    "informational": 4,
    "pending_inbox": 5,
}
_SECTION_NAMES = tuple(_SECTION_PRIORITY)
_SOURCE_PRIORITY = {
    DailyReviewSourceType.WORK_LOG: 0,
    DailyReviewSourceType.USER_TASK: 1,
    DailyReviewSourceType.WAITING_FOR: 2,
    DailyReviewSourceType.REMINDER: 3,
    DailyReviewSourceType.INBOX: 4,
}
_SOURCE_PREFIXES = {
    DailyReviewSourceType.WORK_LOG: ("wl_", "wl_legacy_"),
    DailyReviewSourceType.USER_TASK: ("ut_",),
    DailyReviewSourceType.WAITING_FOR: ("wf_",),
    DailyReviewSourceType.REMINDER: ("rem_",),
    DailyReviewSourceType.INBOX: ("inbox_",),
}


class _SourceContractError(RuntimeError):
    """Signal an invalid enabled-source page or projection."""


@dataclass(frozen=True)
class _Candidate:
    section: str
    severity: int
    item: DailyReviewItem

    @property
    def identity(self) -> tuple[DailyReviewSourceType, str]:
        return self.item.source_type, self.item.source_id


class DailyReviewService:
    """Build one structured review from the five canonical service boundaries."""

    COMPONENT = "daily_review"

    def __init__(
        self,
        *,
        work_log_service,
        waiting_for_service,
        reminder_inbox,
        inbox_service,
        user_task_service,
        clock: Clock,
        timezone_name: str,
        enabled: bool = True,
        user_tasks_enabled: bool = True,
        reminders_enabled: bool = True,
    ) -> None:
        self._work_logs = work_log_service
        self._waiting_for = waiting_for_service
        self._reminders = reminder_inbox
        self._inbox = inbox_service
        self._user_tasks = user_task_service
        self._clock = clock
        self._timezone_name = timezone_name
        self._enabled = enabled
        self._user_tasks_enabled = user_tasks_enabled
        self._reminders_enabled = reminders_enabled

    def query_from_input(
        self,
        *,
        review_date: str | DailyReviewDate,
        limit: int = DEFAULT_DAILY_REVIEW_LIMIT,
        offset: int = DEFAULT_DAILY_REVIEW_OFFSET,
        trace_id: str = "",
    ) -> DailyReviewQuery:
        """Own date and pagination parsing before any source is read."""

        try:
            parsed_date = DailyReviewDate(review_date)
        except (TypeError, ValueError) as exc:
            self._raise(
                code="daily_review.date_invalid",
                category=ErrorCategory.VALIDATION,
                message="Daily Review date is invalid",
                trace_id=trace_id,
                cause_type=type(exc).__name__,
            )
        try:
            return DailyReviewQuery(
                review_date=parsed_date,
                limit=limit,
                offset=offset,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            self._raise(
                code="daily_review.query_invalid",
                category=ErrorCategory.VALIDATION,
                message="Daily Review query is invalid",
                trace_id=trace_id,
                cause_type=type(exc).__name__,
            )

    async def get(
        self,
        *,
        workspace_key: WorkspaceKey,
        query: DailyReviewQuery,
    ) -> DailyReview:
        if not self._enabled:
            self._raise(
                code="daily_review.unavailable",
                category=ErrorCategory.DISABLED,
                message="Daily Review is disabled",
                trace_id=getattr(workspace_key, "trace_id", ""),
            )

        workspace = self._normalize_workspace(workspace_key)
        zone = self._zone(workspace.trace_id)
        instant = self._instant(workspace.trace_id)
        target_date = instant.astimezone(zone).date()
        if query.review_date == DailyReviewDate.YESTERDAY:
            target_date -= timedelta(days=1)
        start_local = datetime.combine(target_date, time.min, tzinfo=zone)
        end_local = datetime.combine(
            target_date + timedelta(days=1),
            time.min,
            tzinfo=zone,
        )
        period_start = start_local.astimezone(UTC)
        period_end = end_local.astimezone(UTC)
        due_soon_end = instant + timedelta(hours=24)

        statuses: dict[DailyReviewSourceType, DailyReviewSourceStatus] = {}
        candidates: list[_Candidate] = []

        await self._evaluate(
            DailyReviewSourceType.WORK_LOG,
            self._work_logs,
            statuses,
            candidates,
            lambda: self._collect_work_logs(
                workspace,
                period_start=period_start,
                period_end=period_end,
            ),
        )
        await self._evaluate(
            DailyReviewSourceType.WAITING_FOR,
            self._waiting_for,
            statuses,
            candidates,
            lambda: self._collect_waiting_for(
                workspace,
                period_start=period_start,
                period_end=period_end,
                as_of=instant,
            ),
        )
        await self._evaluate(
            DailyReviewSourceType.REMINDER,
            self._reminders,
            statuses,
            candidates,
            lambda: self._collect_reminders(
                workspace,
                period_start=period_start,
                period_end=period_end,
                as_of=instant,
                due_soon_end=due_soon_end,
            ),
            configured_enabled=self._reminders_enabled,
        )
        await self._evaluate(
            DailyReviewSourceType.INBOX,
            self._inbox,
            statuses,
            candidates,
            lambda: self._collect_inbox(workspace, as_of=instant),
        )
        await self._evaluate(
            DailyReviewSourceType.USER_TASK,
            self._user_tasks,
            statuses,
            candidates,
            lambda: self._collect_user_tasks(
                workspace,
                period_start=period_start,
                period_end=period_end,
                as_of=instant,
                due_soon_end=due_soon_end,
            ),
            configured_enabled=self._user_tasks_enabled,
        )

        return self._finalize(
            workspace=workspace,
            query=query,
            target_date=target_date,
            period_start=period_start,
            period_end=period_end,
            instant=instant,
            statuses=statuses,
            candidates=candidates,
        )

    async def _evaluate(
        self,
        source: DailyReviewSourceType,
        service: Any,
        statuses: dict[DailyReviewSourceType, DailyReviewSourceStatus],
        output: list[_Candidate],
        loader: Callable[[], Awaitable[list[_Candidate]]],
        *,
        configured_enabled: bool = True,
    ) -> None:
        if not configured_enabled:
            statuses[source] = DailyReviewSourceStatus.DISABLED
            return
        if service is None:
            statuses[source] = DailyReviewSourceStatus.NOT_CONFIGURED
            return
        try:
            output.extend(await loader())
        except FailureException as exc:
            self._raise_source(source, exc)
        except Exception as exc:  # noqa: BLE001 - fail-closed source boundary
            self._raise_source(source, exc)
        statuses[source] = DailyReviewSourceStatus.AVAILABLE

    async def _collect_work_logs(
        self,
        workspace: WorkspaceKey,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> list[_Candidate]:
        page_size = 200

        async def fetch(offset: int) -> tuple[Sequence[Any], bool]:
            page = await self._work_logs.list(
                workspace_key=workspace,
                query=WorkLogQuery(
                    date_from=period_start,
                    date_to=period_end,
                    limit=page_size,
                    offset=offset,
                ),
            )
            return page.items, page.has_more

        records = await self._walk_pages(
            source=DailyReviewSourceType.WORK_LOG,
            page_size=page_size,
            fetch=fetch,
            identity=lambda item: item.id,
            max_offset=10_000,
        )
        section_by_status = {
            WorkLogStatus.COMPLETED: "completed",
            WorkLogStatus.IN_PROGRESS: "in_progress",
            WorkLogStatus.BLOCKED: "blocked",
            WorkLogStatus.INFORMATIONAL: "informational",
        }
        result: list[_Candidate] = []
        for record in records:
            if not self._in_period(record.occurred_at, period_start, period_end):
                continue
            section = section_by_status[record.status]
            result.append(self._candidate(
                section=section,
                severity=100,
                source=DailyReviewSourceType.WORK_LOG,
                source_id=record.id,
                title=record.subject,
                status=record.status.value,
                reason_code=f"work_log.{record.status.value}",
                effective_at=record.occurred_at,
                relevant_time_fields={"occurred_at": record.occurred_at},
            ))
        return result

    async def _collect_waiting_for(
        self,
        workspace: WorkspaceKey,
        *,
        period_start: datetime,
        period_end: datetime,
        as_of: datetime,
    ) -> list[_Candidate]:
        page_size = 200

        async def fetch(offset: int) -> tuple[Sequence[Any], bool]:
            page = await self._waiting_for.list(
                workspace_key=workspace,
                view=WaitingForView.ALL,
                limit=page_size,
                offset=offset,
                as_of=as_of,
            )
            return page.items, page.has_more

        items = await self._walk_pages(
            source=DailyReviewSourceType.WAITING_FOR,
            page_size=page_size,
            fetch=fetch,
            identity=lambda item: item.id,
        )
        result: list[_Candidate] = []
        for item in items:
            if (
                item.resolved_at is not None
                and self._in_period(item.resolved_at, period_start, period_end)
            ):
                result.append(self._candidate(
                    section="completed",
                    severity=100,
                    source=DailyReviewSourceType.WAITING_FOR,
                    source_id=item.id,
                    title=item.subject,
                    status=item.status.value,
                    reason_code="waiting_for.resolved",
                    effective_at=item.resolved_at,
                    relevant_time_fields={"resolved_at": item.resolved_at},
                ))
            if (
                item.cancelled_at is not None
                and self._in_period(item.cancelled_at, period_start, period_end)
            ):
                result.append(self._candidate(
                    section="informational",
                    severity=100,
                    source=DailyReviewSourceType.WAITING_FOR,
                    source_id=item.id,
                    title=item.subject,
                    status=item.status.value,
                    reason_code="waiting_for.cancelled",
                    effective_at=item.cancelled_at,
                    relevant_time_fields={"cancelled_at": item.cancelled_at},
                ))
            if item.status != WaitingForStatus.OPEN:
                continue
            if item.expected_by is not None and item.expected_by < as_of:
                result.append(self._candidate(
                    section="follow_ups",
                    severity=10,
                    source=DailyReviewSourceType.WAITING_FOR,
                    source_id=item.id,
                    title=item.subject,
                    status=item.status.value,
                    reason_code="waiting_for.expected_overdue",
                    effective_at=item.expected_by,
                    relevant_time_fields={"expected_by": item.expected_by},
                ))
            if item.next_review_at is not None and item.next_review_at <= as_of:
                result.append(self._candidate(
                    section="follow_ups",
                    severity=20,
                    source=DailyReviewSourceType.WAITING_FOR,
                    source_id=item.id,
                    title=item.subject,
                    status=item.status.value,
                    reason_code="waiting_for.review_due",
                    effective_at=item.next_review_at,
                    relevant_time_fields={"next_review_at": item.next_review_at},
                ))
        return result

    async def _collect_reminders(
        self,
        workspace: WorkspaceKey,
        *,
        period_start: datetime,
        period_end: datetime,
        as_of: datetime,
        due_soon_end: datetime,
    ) -> list[_Candidate]:
        page_size = 100

        async def fetch(offset: int) -> tuple[Sequence[Any], bool]:
            page = await self._reminders.list(
                workspace_key=workspace,
                statuses=None,
                time_scope=None,
                view=None,
                limit=page_size,
                offset=offset,
                trace_id=workspace.trace_id,
            )
            return page.items, page.has_more

        items = await self._walk_pages(
            source=DailyReviewSourceType.REMINDER,
            page_size=page_size,
            fetch=fetch,
            identity=lambda item: item.reminder_id,
        )
        result: list[_Candidate] = []
        for item in items:
            status = item.status
            if (
                item.triggered_at is not None
                and self._in_period(item.triggered_at, period_start, period_end)
            ):
                result.append(self._candidate(
                    section="completed",
                    severity=100,
                    source=DailyReviewSourceType.REMINDER,
                    source_id=item.reminder_id,
                    title=item.task_title,
                    status=status.value,
                    reason_code="reminder.triggered",
                    effective_at=item.triggered_at,
                    relevant_time_fields={"triggered_at": item.triggered_at},
                ))
            if status == ReminderInboxStatus.FAILED:
                result.append(self._candidate(
                    section="follow_ups",
                    severity=10,
                    source=DailyReviewSourceType.REMINDER,
                    source_id=item.reminder_id,
                    title=item.task_title,
                    status=status.value,
                    reason_code="reminder.failed",
                    effective_at=item.scheduled_for,
                    relevant_time_fields={"scheduled_for": item.scheduled_for},
                ))
            if status == ReminderInboxStatus.RETRYING:
                result.append(self._candidate(
                    section="follow_ups",
                    severity=20,
                    source=DailyReviewSourceType.REMINDER,
                    source_id=item.reminder_id,
                    title=item.task_title,
                    status=status.value,
                    reason_code="reminder.retrying",
                    effective_at=item.scheduled_for,
                    relevant_time_fields={"scheduled_for": item.scheduled_for},
                ))
            if (
                status in {
                    ReminderInboxStatus.SCHEDULED,
                    ReminderInboxStatus.RETRYING,
                }
                and as_of <= item.scheduled_for < due_soon_end
            ):
                result.append(self._candidate(
                    section="follow_ups",
                    severity=40,
                    source=DailyReviewSourceType.REMINDER,
                    source_id=item.reminder_id,
                    title=item.task_title,
                    status=status.value,
                    reason_code="reminder.due_soon",
                    effective_at=item.scheduled_for,
                    relevant_time_fields={"scheduled_for": item.scheduled_for},
                ))
        return result

    async def _collect_inbox(
        self,
        workspace: WorkspaceKey,
        *,
        as_of: datetime,
    ) -> list[_Candidate]:
        page_size = 200

        async def fetch(offset: int) -> tuple[Sequence[Any], bool]:
            page = await self._inbox.list(
                workspace_key=workspace,
                status=InboxStatus.PENDING,
                limit=page_size,
                offset=offset,
            )
            return page.items, page.has_more

        items = await self._walk_pages(
            source=DailyReviewSourceType.INBOX,
            page_size=page_size,
            fetch=fetch,
            identity=lambda item: item.id,
        )
        return [
            self._candidate(
                section="pending_inbox",
                severity=50,
                source=DailyReviewSourceType.INBOX,
                source_id=item.id,
                title=item.content,
                status=item.status.value,
                reason_code="inbox.pending",
                effective_at=item.created_at,
                relevant_time_fields={"created_at": item.created_at},
            )
            for item in items
            if item.status == InboxStatus.PENDING and item.created_at <= as_of
        ]

    async def _collect_user_tasks(
        self,
        workspace: WorkspaceKey,
        *,
        period_start: datetime,
        period_end: datetime,
        as_of: datetime,
        due_soon_end: datetime,
    ) -> list[_Candidate]:
        completed = await self._walk_user_tasks(
            workspace,
            query_factory=lambda offset: UserTaskQuery(
                status=UserTaskStatus.COMPLETED,
                completed_from=period_start,
                completed_to=period_end,
                limit=500,
                offset=offset,
            ),
            as_of=as_of,
        )
        cancelled = await self._walk_user_tasks(
            workspace,
            query_factory=lambda offset: UserTaskQuery(
                status=UserTaskStatus.CANCELLED,
                cancelled_from=period_start,
                cancelled_to=period_end,
                limit=500,
                offset=offset,
            ),
            as_of=as_of,
        )
        overdue = await self._walk_user_tasks(
            workspace,
            query_factory=lambda offset: UserTaskQuery(
                status=UserTaskStatus.ACTIVE,
                overdue=True,
                limit=500,
                offset=offset,
            ),
            as_of=as_of,
        )
        due_soon = await self._walk_user_tasks(
            workspace,
            query_factory=lambda offset: UserTaskQuery(
                status=UserTaskStatus.ACTIVE,
                due_from=as_of,
                due_to=due_soon_end,
                limit=500,
                offset=offset,
            ),
            as_of=as_of,
        )

        result: list[_Candidate] = []
        for task in completed:
            if (
                task.completed_at is not None
                and self._in_period(task.completed_at, period_start, period_end)
            ):
                result.append(self._candidate(
                    section="completed",
                    severity=100,
                    source=DailyReviewSourceType.USER_TASK,
                    source_id=task.id,
                    title=task.title,
                    status=task.status.value,
                    reason_code="user_task.completed",
                    effective_at=task.completed_at,
                    relevant_time_fields={"completed_at": task.completed_at},
                ))
        for task in cancelled:
            if (
                task.cancelled_at is not None
                and self._in_period(task.cancelled_at, period_start, period_end)
            ):
                result.append(self._candidate(
                    section="informational",
                    severity=100,
                    source=DailyReviewSourceType.USER_TASK,
                    source_id=task.id,
                    title=task.title,
                    status=task.status.value,
                    reason_code="user_task.cancelled",
                    effective_at=task.cancelled_at,
                    relevant_time_fields={"cancelled_at": task.cancelled_at},
                ))
        for task in overdue:
            if (
                task.status == UserTaskStatus.ACTIVE
                and task.due_at is not None
                and task.due_at < as_of
            ):
                result.append(self._candidate(
                    section="follow_ups",
                    severity=10,
                    source=DailyReviewSourceType.USER_TASK,
                    source_id=task.id,
                    title=task.title,
                    status=task.status.value,
                    reason_code="user_task.overdue",
                    effective_at=task.due_at,
                    relevant_time_fields={"due_at": task.due_at},
                ))
        for task in due_soon:
            if (
                task.status == UserTaskStatus.ACTIVE
                and task.due_at is not None
                and as_of <= task.due_at < due_soon_end
            ):
                result.append(self._candidate(
                    section="follow_ups",
                    severity=40,
                    source=DailyReviewSourceType.USER_TASK,
                    source_id=task.id,
                    title=task.title,
                    status=task.status.value,
                    reason_code="user_task.due_soon",
                    effective_at=task.due_at,
                    relevant_time_fields={"due_at": task.due_at},
                ))
        return result

    async def _walk_user_tasks(
        self,
        workspace: WorkspaceKey,
        *,
        query_factory: Callable[[int], UserTaskQuery],
        as_of: datetime,
    ) -> list[Any]:
        page_size = 500

        async def fetch(offset: int) -> tuple[Sequence[Any], bool]:
            items = await self._user_tasks.list(
                workspace_key=workspace,
                query=query_factory(offset),
                trace_id=workspace.trace_id,
                as_of=as_of,
            )
            return items, len(items) == page_size

        return await self._walk_pages(
            source=DailyReviewSourceType.USER_TASK,
            page_size=page_size,
            fetch=fetch,
            identity=lambda item: item.id,
        )

    async def _walk_pages(
        self,
        *,
        source: DailyReviewSourceType,
        page_size: int,
        fetch: Callable[[int], Awaitable[tuple[Sequence[Any], bool]]],
        identity: Callable[[Any], str],
        max_offset: int | None = None,
    ) -> list[Any]:
        offset = 0
        result: list[Any] = []
        page_signatures: set[tuple[str, ...]] = set()
        while True:
            if max_offset is not None and offset > max_offset:
                raise _SourceContractError(
                    f"{source.value} pagination cannot advance"
                )
            items, has_more = await fetch(offset)
            page_items = list(items)
            if len(page_items) > page_size:
                raise _SourceContractError(
                    f"{source.value} page exceeds requested size"
                )
            signature = tuple(identity(item) for item in page_items)
            if signature and signature in page_signatures:
                raise _SourceContractError(
                    f"{source.value} repeated the same page"
                )
            if signature:
                page_signatures.add(signature)
            result.extend(page_items)
            if not has_more:
                return result
            if not page_items:
                raise _SourceContractError(
                    f"{source.value} returned an empty page with has_more"
                )
            next_offset = offset + len(page_items)
            if next_offset <= offset:
                raise _SourceContractError(
                    f"{source.value} pagination did not advance"
                )
            offset = next_offset

    def _candidate(
        self,
        *,
        section: str,
        severity: int,
        source: DailyReviewSourceType,
        source_id: str,
        title: str,
        status: str,
        reason_code: str,
        effective_at: datetime | None,
        relevant_time_fields: dict[str, datetime],
    ) -> _Candidate:
        if section not in _SECTION_PRIORITY:
            raise _SourceContractError("Daily Review section is invalid")
        prefixes = _SOURCE_PREFIXES[source]
        if not source_id.startswith(prefixes):
            raise _SourceContractError(
                f"{source.value} canonical id prefix is invalid"
            )
        return _Candidate(
            section=section,
            severity=severity,
            item=DailyReviewItem(
                source_type=source,
                source_id=source_id,
                title=title,
                status=status,
                reason_code=reason_code,
                effective_at=effective_at,
                relevant_time_fields=relevant_time_fields,
            ),
        )

    def _finalize(
        self,
        *,
        workspace: WorkspaceKey,
        query: DailyReviewQuery,
        target_date,
        period_start: datetime,
        period_end: datetime,
        instant: datetime,
        statuses: dict[DailyReviewSourceType, DailyReviewSourceStatus],
        candidates: list[_Candidate],
    ) -> DailyReview:
        selected: dict[tuple[DailyReviewSourceType, str], _Candidate] = {}
        for candidate in candidates:
            current = selected.get(candidate.identity)
            if current is None or self._selection_key(candidate) < self._selection_key(
                current
            ):
                selected[candidate.identity] = candidate

        ordered = sorted(selected.values(), key=self._sort_key)
        totals = Counter(candidate.section for candidate in ordered)
        page_candidates = ordered[query.offset:query.offset + query.limit]
        page_by_section: dict[str, list[DailyReviewItem]] = {
            section: [] for section in _SECTION_NAMES
        }
        for candidate in page_candidates:
            page_by_section[candidate.section].append(candidate.item)

        sections = {
            section: DailyReviewSection(
                section_total_count=totals[section],
                page_item_count=len(page_by_section[section]),
                items=tuple(page_by_section[section]),
            )
            for section in _SECTION_NAMES
        }
        page_count = len(page_candidates)
        total_count = len(ordered)
        return DailyReview(
            workspace=DailyReviewWorkspace(
                tenant_id=workspace.tenant_id,
                workspace_id=workspace.workspace_id,
                namespace=workspace.namespace,
            ),
            review_date=target_date,
            timezone=self._timezone_name,
            period_start=period_start,
            period_end=period_end,
            generated_at=instant,
            as_of=instant,
            source_status=statuses,
            page=DailyReviewPage(
                count=page_count,
                total_count=total_count,
                limit=query.limit,
                offset=query.offset,
                has_more=query.offset + page_count < total_count,
            ),
            **sections,
        )

    @staticmethod
    def _selection_key(candidate: _Candidate) -> tuple[int, int, str]:
        return (
            _SECTION_PRIORITY[candidate.section],
            candidate.severity,
            candidate.item.reason_code,
        )

    @staticmethod
    def _sort_key(candidate: _Candidate) -> tuple[Any, ...]:
        effective = candidate.item.effective_at
        return (
            _SECTION_PRIORITY[candidate.section],
            candidate.severity,
            effective is None,
            effective or datetime.max.replace(tzinfo=UTC),
            _SOURCE_PRIORITY[candidate.item.source_type],
            candidate.item.source_id,
        )

    @staticmethod
    def _in_period(value: datetime, start: datetime, end: datetime) -> bool:
        return start <= value < end

    def _normalize_workspace(self, value: WorkspaceKey) -> WorkspaceKey:
        if not isinstance(value, WorkspaceKey):
            self._raise(
                code="daily_review.workspace_invalid",
                category=ErrorCategory.VALIDATION,
                message="Daily Review workspace is invalid",
            )
        try:
            return value.model_copy(update={
                "tenant_id": str(value.tenant_id or "").strip() or "default",
                "workspace_id": str(value.workspace_id or "").strip() or "default",
                "namespace": str(value.namespace or "").strip() or "default",
            })
        except Exception as exc:  # noqa: BLE001 - validation boundary
            self._raise(
                code="daily_review.workspace_invalid",
                category=ErrorCategory.VALIDATION,
                message="Daily Review workspace is invalid",
                trace_id=getattr(value, "trace_id", ""),
                cause_type=type(exc).__name__,
            )

    def _zone(self, trace_id: str) -> ZoneInfo:
        try:
            return ZoneInfo(self._timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            self._raise(
                code="daily_review.timezone_invalid",
                category=ErrorCategory.VALIDATION,
                message="Daily Review timezone is invalid",
                trace_id=trace_id,
                cause_type=type(exc).__name__,
            )

    def _instant(self, trace_id: str) -> datetime:
        try:
            value = self._clock.now()
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("clock instant must be timezone-aware")
            return value.astimezone(UTC)
        except Exception as exc:  # noqa: BLE001 - injected clock boundary
            self._raise(
                code="daily_review.date_invalid",
                category=ErrorCategory.VALIDATION,
                message="Daily Review date cannot be determined",
                trace_id=trace_id,
                cause_type=type(exc).__name__,
            )

    def _raise_source(
        self,
        source: DailyReviewSourceType,
        exc: Exception,
    ) -> None:
        if isinstance(exc, FailureException):
            upstream_code = exc.failure.code
            upstream_category = exc.failure.category.value
            cause_type = exc.failure.cause_type or type(exc).__name__
            trace_id = exc.failure.trace_id
        else:
            upstream_code = f"{source.value}.unhandled_failure"
            upstream_category = ErrorCategory.INTERNAL.value
            cause_type = type(exc).__name__
            trace_id = ""
        self._raise(
            code="daily_review.source_failed",
            category=ErrorCategory.DEPENDENCY_FAILURE,
            message="Daily Review source failed",
            trace_id=trace_id,
            cause_type=cause_type,
            details={
                "source": source.value,
                "upstream_code": upstream_code,
                "upstream_category": upstream_category,
            },
        )

    @staticmethod
    def _raise(
        *,
        code: str,
        category: ErrorCategory,
        message: str,
        trace_id: str = "",
        cause_type: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        raise FailureException(FailureInfo(
            code=code,
            category=category,
            message=message,
            component="daily_review",
            operation="get",
            retryable=category == ErrorCategory.DEPENDENCY_FAILURE,
            trace_id=trace_id,
            cause_type=cause_type,
            details=details or {},
        ))
