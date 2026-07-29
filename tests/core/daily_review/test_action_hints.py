"""Deterministic, side-effect-free Action Hint contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime

from core.daily_review import (
    DailyReview,
    DailyReviewItem,
    DailyReviewPage,
    DailyReviewSection,
    DailyReviewSourceStatus,
    DailyReviewSourceType,
    DailyReviewWorkspace,
    build_action_hints,
)


def _review(*items: DailyReviewItem) -> DailyReview:
    empty = DailyReviewSection(section_total_count=0, page_item_count=0)
    blocked = DailyReviewSection(
        section_total_count=len(items),
        page_item_count=len(items),
        items=items,
    )
    instant = datetime(2026, 7, 30, tzinfo=UTC)
    return DailyReview(
        workspace=DailyReviewWorkspace(
            tenant_id="tenant",
            workspace_id="workspace",
            namespace="daily",
        ),
        review_date=date(2026, 7, 30),
        timezone="UTC",
        period_start=instant,
        period_end=datetime(2026, 7, 31, tzinfo=UTC),
        generated_at=instant,
        as_of=instant,
        source_status={
            source: DailyReviewSourceStatus.AVAILABLE
            for source in DailyReviewSourceType
        },
        page=DailyReviewPage(
            count=len(items),
            total_count=len(items),
            limit=50,
            offset=0,
            has_more=False,
        ),
        completed=empty,
        in_progress=empty,
        blocked=blocked,
        informational=empty,
        follow_ups=empty,
        pending_inbox=empty,
    )


def _item(reason_code: str, source_type: str = "user_task") -> DailyReviewItem:
    return DailyReviewItem(
        source_type=source_type,
        source_id="ut_1234567890abcdef1234567890abcdef",
        title="Review item",
        status="active",
        reason_code=reason_code,
        effective_at=datetime(2026, 7, 30, tzinfo=UTC),
    )


def test_user_task_hints_are_deterministic_and_truthful():
    review = _review(_item("user_task.overdue"))
    before = review.model_dump(mode="json")

    first = build_action_hints(review)
    second = build_action_hints(review)

    assert first == second
    assert [hint.allowed_action for hint in first] == ["complete", "cancel"]
    assert all(hint.requires_revision for hint in first)
    assert all(hint.requires_confirmation for hint in first)
    assert all(hint.available_entrypoints for hint in first)
    assert all(
        "daily-review/actions/user-tasks" in hint.available_entrypoints[0]
        for hint in first
    )
    assert review.model_dump(mode="json") == before


def test_unsupported_and_work_log_mutations_are_not_invented():
    unsupported = _review(_item("work_log.completed", "work_log"))
    assert build_action_hints(unsupported) == ()


def test_inbox_hint_uses_real_saga_entrypoints_without_revision():
    item = _item("inbox.pending", "inbox").model_copy(
        update={"source_id": "inbox_1234567890abcdef1234567890abcdef"}
    )
    hints = build_action_hints(_review(item))
    assert [hint.allowed_action for hint in hints] == ["resolve", "dismiss"]
    assert all(not hint.requires_revision for hint in hints)
    assert all(hint.requires_confirmation for hint in hints)
    assert all(hint.available_entrypoints for hint in hints)
