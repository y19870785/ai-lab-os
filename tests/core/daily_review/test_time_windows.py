"""Local calendar, as-of, DST, and validation-order contracts."""

from datetime import UTC, datetime

import pytest

from core.daily_review import DailyReviewQuery
from core.errors import ErrorCategory, FailureException
from tests.core.daily_review.helpers import (
    WORKSPACE,
    FrozenCountingClock,
    empty_sources,
    make_service,
)


@pytest.mark.asyncio
async def test_today_and_yesterday_use_one_clock_instant():
    clock = FrozenCountingClock(datetime(2026, 7, 27, 1, tzinfo=UTC))
    service = make_service(clock, timezone_name="Asia/Shanghai")

    today = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today"),
    )
    assert today.review_date.isoformat() == "2026-07-27"
    assert today.period_start == datetime(2026, 7, 26, 16, tzinfo=UTC)
    assert today.period_end == datetime(2026, 7, 27, 16, tzinfo=UTC)
    assert today.generated_at == today.as_of == clock.instant
    assert clock.calls == 1

    yesterday = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="yesterday"),
    )
    assert yesterday.review_date.isoformat() == "2026-07-26"
    assert yesterday.period_start == datetime(2026, 7, 25, 16, tzinfo=UTC)
    assert yesterday.period_end == datetime(2026, 7, 26, 16, tzinfo=UTC)
    assert clock.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("instant", "target_date", "hours"),
    [
        (
            datetime(2026, 3, 8, 16, tzinfo=UTC),
            "2026-03-08",
            23,
        ),
        (
            datetime(2026, 11, 1, 17, tzinfo=UTC),
            "2026-11-01",
            25,
        ),
    ],
)
async def test_new_york_dst_uses_independent_local_midnights(
    instant,
    target_date,
    hours,
):
    service = make_service(
        FrozenCountingClock(instant),
        timezone_name="America/New_York",
    )

    review = await service.get(
        workspace_key=WORKSPACE,
        query=DailyReviewQuery(review_date="today"),
    )

    assert review.review_date.isoformat() == target_date
    assert (review.period_end - review.period_start).total_seconds() == hours * 3600


def test_date_and_pagination_validation_do_not_read_sources():
    sources = empty_sources()
    service = make_service(
        FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC)),
        sources,
    )

    with pytest.raises(FailureException) as date_failure:
        service.query_from_input(review_date="tomorrow")
    assert date_failure.value.failure.code == "daily_review.date_invalid"
    assert date_failure.value.failure.category == ErrorCategory.VALIDATION

    for values in (
        {"review_date": "today", "limit": 0},
        {"review_date": "today", "limit": 101},
        {"review_date": "today", "offset": -1},
    ):
        with pytest.raises(FailureException) as query_failure:
            service.query_from_input(**values)
        assert query_failure.value.failure.code == "daily_review.query_invalid"
        assert query_failure.value.failure.category == ErrorCategory.VALIDATION

    assert sources.work_logs.calls == []
    assert sources.waiting_for.calls == []
    assert sources.reminders.calls == []
    assert sources.inbox.calls == []
    assert sources.user_tasks.calls == []


@pytest.mark.asyncio
async def test_invalid_timezone_fails_before_clock_and_sources():
    sources = empty_sources()
    clock = FrozenCountingClock(datetime(2026, 7, 27, tzinfo=UTC))
    service = make_service(clock, sources, timezone_name="Invalid/Timezone")

    with pytest.raises(FailureException) as exc_info:
        await service.get(
            workspace_key=WORKSPACE,
            query=DailyReviewQuery(review_date="today"),
        )

    failure = exc_info.value.failure
    assert failure.code == "daily_review.timezone_invalid"
    assert failure.category == ErrorCategory.VALIDATION
    assert clock.calls == 0
    assert sources.work_logs.calls == []
