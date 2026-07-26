"""Source availability, full traversal, and fail-closed behavior."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from core.daily_review import (
    DailyReviewQuery,
    DailyReviewSourceStatus,
    DailyReviewSourceType,
)
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.inbox import InboxItem, InboxStatus
from core.work_log import WorkLogStatus
from tests.core.daily_review.helpers import (
    WORKSPACE,
    FailingService,
    FrozenCountingClock,
    PagedService,
    SourceSet,
    empty_sources,
    make_service,
)


@pytest.mark.asyncio
async def test_disabled_not_configured_and_available_are_distinct():
    clock = FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC))
    sources = SourceSet(
        work_logs=None,
        waiting_for=None,
        reminders=None,
        inbox=None,
        user_tasks=None,
    )

    review = await make_service(
        clock,
        sources,
        user_tasks_enabled=False,
        reminders_enabled=False,
    ).get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today"),
    )

    assert review.source_status == {
        DailyReviewSourceType.WORK_LOG: DailyReviewSourceStatus.NOT_CONFIGURED,
        DailyReviewSourceType.WAITING_FOR: DailyReviewSourceStatus.NOT_CONFIGURED,
        DailyReviewSourceType.REMINDER: DailyReviewSourceStatus.DISABLED,
        DailyReviewSourceType.INBOX: DailyReviewSourceStatus.NOT_CONFIGURED,
        DailyReviewSourceType.USER_TASK: DailyReviewSourceStatus.DISABLED,
    }
    available = await make_service(
        FrozenCountingClock(clock.instant),
        empty_sources(),
    ).get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today"),
    )
    assert set(available.source_status.values()) == {
        DailyReviewSourceStatus.AVAILABLE
    }


@pytest.mark.asyncio
async def test_explicitly_disabled_source_is_not_read_even_when_service_exists():
    clock = FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC))
    sources = empty_sources()
    service = make_service(
        clock,
        sources,
        user_tasks_enabled=False,
        reminders_enabled=False,
    )

    review = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today"),
    )

    assert review.source_status[DailyReviewSourceType.USER_TASK] == (
        DailyReviewSourceStatus.DISABLED
    )
    assert review.source_status[DailyReviewSourceType.REMINDER] == (
        DailyReviewSourceStatus.DISABLED
    )
    assert sources.user_tasks.calls == []
    assert sources.reminders.calls == []


@pytest.mark.asyncio
async def test_daily_review_disabled_is_not_not_configured_and_reads_nothing():
    clock = FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC))
    sources = empty_sources()

    with pytest.raises(FailureException) as exc_info:
        await make_service(
            clock,
            sources,
            enabled=False,
        ).get(
            workspace_key=WORKSPACE,
            query=DailyReviewQuery(review_date="today"),
        )

    failure = exc_info.value.failure
    assert failure.code == "daily_review.unavailable"
    assert failure.category == ErrorCategory.DISABLED
    assert clock.calls == 0
    assert sources.work_logs.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "source_name"),
    [
        ("work_logs", "work_log"),
        ("waiting_for", "waiting_for"),
        ("reminders", "reminder"),
        ("inbox", "inbox"),
        ("user_tasks", "user_task"),
    ],
)
async def test_each_enabled_source_runtime_failure_fails_closed(
    field_name,
    source_name,
):
    sources = empty_sources()
    setattr(
        sources,
        field_name,
        FailingService(RuntimeError("database path C:/secret/body")),
    )
    service = make_service(
        FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC)),
        sources,
    )

    with pytest.raises(FailureException) as exc_info:
        await service.get(
            workspace_key=WORKSPACE,
            query=DailyReviewQuery(review_date="today"),
        )

    failure = exc_info.value.failure
    assert failure.code == "daily_review.source_failed"
    assert failure.category == ErrorCategory.DEPENDENCY_FAILURE
    assert failure.details == {
        "source": source_name,
        "upstream_code": f"{source_name}.unhandled_failure",
        "upstream_category": "internal",
    }
    serialized = failure.model_dump_json()
    assert "C:/secret" not in serialized
    assert "database path" not in serialized


@pytest.mark.asyncio
async def test_upstream_failure_preserves_only_safe_contract_fields():
    upstream = FailureException(FailureInfo(
        code="work_log.repository_failed",
        category=ErrorCategory.PERSISTENCE_FAILURE,
        message="raw sqlite failure",
        component="work_log",
        operation="list",
        details={"metadata": "secret", "sql": "select *"},
    ))
    sources = empty_sources()
    sources.work_logs = FailingService(upstream)

    with pytest.raises(FailureException) as exc_info:
        await make_service(
            FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC)),
            sources,
        ).get(
            workspace_key=WORKSPACE,
            query=DailyReviewQuery(review_date="today"),
        )

    assert exc_info.value.failure.details == {
        "source": "work_log",
        "upstream_code": "work_log.repository_failed",
        "upstream_category": "persistence_failure",
    }


@pytest.mark.asyncio
async def test_source_pagination_reads_beyond_one_page_without_candidate_cap():
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    inbox_items = [
        InboxItem(
            id=f"inbox_{index:04d}",
            workspace_key=WORKSPACE,
            content=f"item-{index}",
            source="test",
            status=InboxStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        for index in range(205)
    ]
    sources = empty_sources()
    sources.inbox = PagedService(inbox_items)

    review = await make_service(
        FrozenCountingClock(now),
        sources,
    ).get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today", limit=100),
    )

    assert review.page.total_count == 205
    assert review.pending_inbox.section_total_count == 205
    assert [call["offset"] for call in sources.inbox.calls] == [0, 200]


class _EmptyHasMoreService:
    async def list(self, **kwargs):
        return SimpleNamespace(items=(), has_more=True)


@pytest.mark.asyncio
async def test_invalid_source_page_contract_fails_closed():
    sources = empty_sources()
    sources.work_logs = _EmptyHasMoreService()

    with pytest.raises(FailureException) as exc_info:
        await make_service(
            FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC)),
            sources,
        ).get(
            workspace_key=WORKSPACE,
            query=DailyReviewQuery(review_date="today"),
        )

    failure = exc_info.value.failure
    assert failure.code == "daily_review.source_failed"
    assert failure.details["source"] == "work_log"


@pytest.mark.asyncio
async def test_noncanonical_source_id_fails_closed():
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    sources = empty_sources()
    sources.work_logs = PagedService([
        SimpleNamespace(
            id="random-memory-id",
            occurred_at=now,
            status=WorkLogStatus.COMPLETED,
            subject="untraceable projection",
        ),
    ])

    with pytest.raises(FailureException) as exc_info:
        await make_service(
            FrozenCountingClock(now),
            sources,
        ).get(
            workspace_key=WORKSPACE,
            query=DailyReviewQuery(review_date="today"),
        )

    failure = exc_info.value.failure
    assert failure.code == "daily_review.source_failed"
    assert failure.details["source"] == "work_log"
