"""Daily Review query and structured-output model contracts."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from core.daily_review import (
    DailyReview,
    DailyReviewItem,
    DailyReviewPage,
    DailyReviewQuery,
    DailyReviewSection,
    DailyReviewSourceStatus,
    DailyReviewSourceType,
    DailyReviewWorkspace,
)


def test_query_defaults_are_frozen_and_forbid_extra_fields():
    query = DailyReviewQuery(review_date="today")

    assert query.model_dump(mode="json") == {
        "review_date": "today",
        "limit": 50,
        "offset": 0,
    }
    with pytest.raises(ValidationError):
        DailyReviewQuery(review_date="today", extra_value=True)
    with pytest.raises(ValidationError):
        query.limit = 10


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"review_date": "tomorrow"}, "review_date"),
        ({"review_date": "today", "limit": 0}, "limit"),
        ({"review_date": "today", "limit": 101}, "limit"),
        ({"review_date": "today", "offset": -1}, "offset"),
    ],
)
def test_query_rejects_invalid_contract(values, field):
    with pytest.raises(ValidationError) as exc_info:
        DailyReviewQuery(**values)
    assert field in str(exc_info.value)


def test_workspace_normalizes_only_the_isolation_triple():
    workspace = DailyReviewWorkspace(
        tenant_id="",
        workspace_id="  ",
        namespace=None,
    )

    assert workspace.model_dump() == {
        "tenant_id": "default",
        "workspace_id": "default",
        "namespace": "default",
    }


def test_item_requires_aware_times_and_section_count_matches():
    with pytest.raises(ValidationError):
        DailyReviewItem(
            source_type="user_task",
            source_id="ut_bad_time",
            title="Task",
            status="active",
            reason_code="user_task.overdue",
            effective_at=datetime(2026, 7, 26),  # noqa: DTZ001
            relevant_time_fields={},
        )

    item = DailyReviewItem(
        source_type="user_task",
        source_id="ut_valid",
        title="Task",
        status="active",
        reason_code="user_task.overdue",
        effective_at=datetime(2026, 7, 26, tzinfo=UTC),
        relevant_time_fields={"due_at": datetime(2026, 7, 26, tzinfo=UTC)},
    )
    with pytest.raises(ValidationError):
        DailyReviewSection(
            section_total_count=1,
            page_item_count=0,
            items=(item,),
        )


def test_review_validates_complete_source_and_page_totals():
    empty = DailyReviewSection(
        section_total_count=0,
        page_item_count=0,
    )
    source_status = {
        source: DailyReviewSourceStatus.AVAILABLE
        for source in DailyReviewSourceType
    }
    review = DailyReview(
        workspace=DailyReviewWorkspace(
            tenant_id="t",
            workspace_id="w",
            namespace="n",
        ),
        review_date=date(2026, 7, 26),
        timezone="UTC",
        period_start=datetime(2026, 7, 26, tzinfo=UTC),
        period_end=datetime(2026, 7, 27, tzinfo=UTC),
        generated_at=datetime(2026, 7, 27, tzinfo=UTC),
        as_of=datetime(2026, 7, 27, tzinfo=UTC),
        source_status=source_status,
        page=DailyReviewPage(
            count=0,
            total_count=0,
            limit=50,
            offset=0,
            has_more=False,
        ),
        completed=empty,
        in_progress=empty,
        blocked=empty,
        informational=empty,
        follow_ups=empty,
        pending_inbox=empty,
    )

    assert review.source_status[DailyReviewSourceType.INBOX] == "available"
