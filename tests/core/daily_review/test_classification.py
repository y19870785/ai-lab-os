"""Deterministic date-fact and current follow-up classification."""

from datetime import UTC, datetime, timedelta

import pytest

from core.daily_review import DailyReviewQuery
from core.reminders import ReminderInboxStatus
from core.user_tasks import UserTaskStatus
from core.waiting_for import WaitingForStatus
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
async def test_all_date_fact_and_follow_up_reasons_are_mapped():
    as_of = datetime(2026, 7, 27, 12, tzinfo=UTC)
    sources = SourceSet(
        work_logs=PagedService([
            work_log(
                "wl_11111111111111111111111111111111",
                occurred_at=as_of.replace(hour=1),
                status=WorkLogStatus.COMPLETED,
            ),
            work_log(
                "wl_22222222222222222222222222222222",
                occurred_at=as_of.replace(hour=2),
                status=WorkLogStatus.IN_PROGRESS,
            ),
            work_log(
                "wl_33333333333333333333333333333333",
                occurred_at=as_of.replace(hour=3),
                status=WorkLogStatus.BLOCKED,
            ),
            work_log(
                "wl_44444444444444444444444444444444",
                occurred_at=as_of.replace(hour=4),
                status=WorkLogStatus.INFORMATIONAL,
            ),
        ]),
        waiting_for=PagedService([
            waiting_for(
                "wf_resolved",
                now=as_of - timedelta(days=2),
                status=WaitingForStatus.RESOLVED,
                resolved_at=as_of.replace(hour=5),
            ),
            waiting_for(
                "wf_cancelled",
                now=as_of - timedelta(days=2),
                status=WaitingForStatus.CANCELLED,
                cancelled_at=as_of.replace(hour=6),
            ),
            waiting_for(
                "wf_both_reasons",
                now=as_of - timedelta(days=2),
                expected_by=as_of - timedelta(hours=2),
                next_review_at=as_of - timedelta(hours=1),
            ),
            waiting_for(
                "wf_review",
                now=as_of - timedelta(days=2),
                next_review_at=as_of,
            ),
        ]),
        reminders=PagedService([
            reminder(
                "rem_triggered",
                scheduled_for=as_of.replace(hour=7),
                status=ReminderInboxStatus.TRIGGERED,
                triggered_at=as_of.replace(hour=8),
            ),
            reminder(
                "rem_failed",
                scheduled_for=as_of - timedelta(hours=3),
                status=ReminderInboxStatus.FAILED,
            ),
            reminder(
                "rem_retry",
                scheduled_for=as_of + timedelta(hours=2),
                status=ReminderInboxStatus.RETRYING,
            ),
            reminder(
                "rem_soon",
                scheduled_for=as_of + timedelta(hours=3),
                status=ReminderInboxStatus.SCHEDULED,
            ),
        ]),
        inbox=PagedService([
            inbox("inbox_old", created_at=as_of - timedelta(days=10)),
            inbox("inbox_future", created_at=as_of + timedelta(minutes=1)),
        ]),
        user_tasks=UserTaskServiceDouble([
            user_task(
                "ut_completed",
                now=as_of - timedelta(days=2),
                status=UserTaskStatus.COMPLETED,
                completed_at=as_of.replace(hour=9),
            ),
            user_task(
                "ut_cancelled",
                now=as_of - timedelta(days=2),
                status=UserTaskStatus.CANCELLED,
                cancelled_at=as_of.replace(hour=10),
            ),
            user_task(
                "ut_overdue",
                now=as_of - timedelta(days=2),
                due_at=as_of - timedelta(minutes=1),
            ),
            user_task(
                "ut_due_now",
                now=as_of - timedelta(days=2),
                due_at=as_of,
            ),
        ]),
    )
    service = make_service(FrozenCountingClock(as_of), sources)

    review = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today", limit=100),
    )

    reasons = {
        item.reason_code
        for section in (
            review.completed,
            review.in_progress,
            review.blocked,
            review.informational,
            review.follow_ups,
            review.pending_inbox,
        )
        for item in section.items
    }
    assert reasons == {
        "work_log.completed",
        "work_log.in_progress",
        "work_log.blocked",
        "work_log.informational",
        "user_task.completed",
        "user_task.cancelled",
        "reminder.triggered",
        "waiting_for.resolved",
        "waiting_for.cancelled",
        "user_task.overdue",
        "user_task.due_soon",
        "waiting_for.expected_overdue",
        "waiting_for.review_due",
        "reminder.failed",
        "reminder.retrying",
        "reminder.due_soon",
        "inbox.pending",
    }
    assert "inbox_future" not in {
        item.source_id for item in review.pending_inbox.items
    }
    assert {
        item.reason_code for item in review.follow_ups.items
        if item.source_id == "wf_both_reasons"
    } == {"waiting_for.expected_overdue"}
    assert {
        item.reason_code for item in review.follow_ups.items
        if item.source_id == "rem_retry"
    } == {"reminder.retrying"}
    assert review.pending_inbox.items[0].source_id == "inbox_old"


@pytest.mark.asyncio
async def test_half_open_fact_window_includes_start_and_excludes_end():
    as_of = datetime(2026, 7, 27, 12, tzinfo=UTC)
    sources = SourceSet(
        work_logs=PagedService([
            work_log(
                "wl_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                occurred_at=datetime(2026, 7, 27, tzinfo=UTC),
            ),
            work_log(
                "wl_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                occurred_at=datetime(2026, 7, 28, tzinfo=UTC),
            ),
        ]),
        waiting_for=PagedService(),
        reminders=PagedService(),
        inbox=PagedService(),
        user_tasks=UserTaskServiceDouble(),
    )

    review = await make_service(
        FrozenCountingClock(as_of),
        sources,
    ).get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today"),
    )

    assert [item.source_id for item in review.completed.items] == [
        "wl_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ]


@pytest.mark.asyncio
async def test_yesterday_facts_use_period_but_open_views_use_current_as_of():
    as_of = datetime(2026, 7, 27, 12, tzinfo=UTC)
    sources = SourceSet(
        work_logs=PagedService([
            work_log(
                "wl_cccccccccccccccccccccccccccccccc",
                occurred_at=datetime(2026, 7, 26, 18, tzinfo=UTC),
            ),
        ]),
        waiting_for=PagedService(),
        reminders=PagedService([
            reminder(
                "rem_current_retry",
                scheduled_for=as_of + timedelta(hours=2),
                status=ReminderInboxStatus.RETRYING,
            ),
        ]),
        inbox=PagedService([
            inbox("inbox_very_old", created_at=as_of - timedelta(days=30)),
        ]),
        user_tasks=UserTaskServiceDouble([
            user_task(
                "ut_current_overdue",
                now=as_of - timedelta(days=3),
                due_at=as_of - timedelta(hours=1),
            ),
        ]),
    )

    review = await make_service(
        FrozenCountingClock(as_of),
        sources,
    ).get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="yesterday"),
    )

    assert review.review_date.isoformat() == "2026-07-26"
    assert [item.source_id for item in review.completed.items] == [
        "wl_cccccccccccccccccccccccccccccccc"
    ]
    assert {item.source_id for item in review.follow_ups.items} == {
        "ut_current_overdue",
        "rem_current_retry",
    }
    assert [item.source_id for item in review.pending_inbox.items] == [
        "inbox_very_old"
    ]
