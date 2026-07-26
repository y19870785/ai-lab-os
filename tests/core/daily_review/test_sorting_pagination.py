"""Canonical identity, stable ordering, and one global page."""

from datetime import UTC, datetime, timedelta

import pytest

from core.daily_review import DailyReviewQuery
from core.reminders import ReminderInboxStatus
from core.work_log import WorkLogStatus
from tests.core.daily_review.helpers import (
    WORKSPACE,
    FrozenCountingClock,
    PagedService,
    SourceSet,
    UserTaskServiceDouble,
    inbox,
    make_service,
    reminder,
    user_task,
    waiting_for,
    work_log,
)


@pytest.mark.asyncio
async def test_sort_uses_section_severity_time_source_and_canonical_id():
    as_of = datetime(2026, 7, 27, 12, tzinfo=UTC)
    common_time = as_of - timedelta(hours=1)
    duplicate_blocked = work_log(
        "wl_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        occurred_at=common_time,
        status=WorkLogStatus.BLOCKED,
    )
    sources = SourceSet(
        work_logs=PagedService([duplicate_blocked, duplicate_blocked]),
        waiting_for=PagedService([
            waiting_for(
                "wf_expected",
                now=as_of - timedelta(days=1),
                expected_by=common_time,
                next_review_at=common_time,
            ),
        ]),
        reminders=PagedService([
            reminder(
                "rem_failed",
                scheduled_for=common_time,
                status=ReminderInboxStatus.FAILED,
            ),
        ]),
        inbox=PagedService([
            inbox("inbox_pending", created_at=common_time),
        ]),
        user_tasks=UserTaskServiceDouble([
            user_task(
                "ut_overdue",
                now=as_of - timedelta(days=1),
                due_at=common_time,
            ),
        ]),
    )

    review = await make_service(
        FrozenCountingClock(as_of),
        sources,
    ).get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today", limit=100),
    )

    all_ids = [
        item.source_id
        for section in (
            review.blocked,
            review.follow_ups,
            review.in_progress,
            review.completed,
            review.informational,
            review.pending_inbox,
        )
        for item in section.items
    ]
    assert all_ids == [
        "wl_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "ut_overdue",
        "wf_expected",
        "rem_failed",
        "inbox_pending",
    ]
    assert review.page.total_count == len(all_ids)
    assert [item.reason_code for item in review.follow_ups.items] == [
        "user_task.overdue",
        "waiting_for.expected_overdue",
        "reminder.failed",
    ]


@pytest.mark.asyncio
async def test_global_pagination_keeps_full_section_totals_and_no_duplicates():
    as_of = datetime(2026, 7, 27, 12, tzinfo=UTC)
    sources = SourceSet(
        work_logs=PagedService([
            work_log(
                f"wl_{index:032x}",
                occurred_at=as_of.replace(hour=index),
                status=WorkLogStatus.COMPLETED,
            )
            for index in range(1, 5)
        ]),
        waiting_for=PagedService(),
        reminders=PagedService(),
        inbox=PagedService([
            inbox(f"inbox_{index}", created_at=as_of - timedelta(days=index))
            for index in range(1, 4)
        ]),
        user_tasks=UserTaskServiceDouble(),
    )
    service = make_service(FrozenCountingClock(as_of), sources)

    first = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today", limit=3, offset=0),
    )
    second = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today", limit=3, offset=3),
    )
    last = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today", limit=3, offset=6),
    )
    ids = [
        item.source_id
        for review in (first, second, last)
        for section in (
            review.completed,
            review.pending_inbox,
        )
        for item in section.items
    ]

    assert len(ids) == len(set(ids)) == 7
    assert first.page.model_dump() == {
        "count": 3,
        "total_count": 7,
        "limit": 3,
        "offset": 0,
        "has_more": True,
    }
    assert second.page.count == 3
    assert second.page.has_more is True
    assert last.page.count == 1
    assert last.page.has_more is False
    for review in (first, second, last):
        assert review.completed.section_total_count == 4
        assert review.pending_inbox.section_total_count == 3
        assert review.page.count == (
            review.completed.page_item_count
            + review.pending_inbox.page_item_count
        )


@pytest.mark.asyncio
async def test_offset_beyond_total_returns_empty_sections_with_full_totals():
    as_of = datetime(2026, 7, 27, 12, tzinfo=UTC)
    sources = SourceSet(
        work_logs=PagedService(),
        waiting_for=PagedService(),
        reminders=PagedService(),
        inbox=PagedService([
            inbox("inbox_only", created_at=as_of - timedelta(days=5)),
        ]),
        user_tasks=UserTaskServiceDouble(),
    )

    review = await make_service(
        FrozenCountingClock(as_of),
        sources,
    ).get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today", limit=50, offset=10),
    )

    assert review.page.model_dump() == {
        "count": 0,
        "total_count": 1,
        "limit": 50,
        "offset": 10,
        "has_more": False,
    }
    assert review.pending_inbox.section_total_count == 1
    for section in (
        review.completed,
        review.in_progress,
        review.blocked,
        review.informational,
        review.follow_ups,
        review.pending_inbox,
    ):
        assert section.items == ()
        assert section.page_item_count == 0


def test_default_and_explicit_query_are_identical():
    assert DailyReviewQuery(review_date="today") == DailyReviewQuery(
        review_date="today",
        limit=50,
        offset=0,
    )
    assert DailyReviewQuery(review_date="yesterday") == DailyReviewQuery(
        review_date="yesterday",
        limit=50,
        offset=0,
    )
