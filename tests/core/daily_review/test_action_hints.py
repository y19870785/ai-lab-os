"""Deterministic, side-effect-free Action Hint contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

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


def _item(
    reason_code: str,
    source_type: str = "user_task",
    status: str = "active",
) -> DailyReviewItem:
    return DailyReviewItem(
        source_type=source_type,
        source_id="ut_1234567890abcdef1234567890abcdef",
        title="Review item",
        status=status,
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
    item = _item("inbox.pending", "inbox", "pending").model_copy(
        update={"source_id": "inbox_1234567890abcdef1234567890abcdef"}
    )
    hints = build_action_hints(_review(item))
    assert [hint.allowed_action for hint in hints] == [
        "resolve_to_task",
        "resolve_to_reminder",
        "resolve_to_work_log",
        "resolve_to_waiting_for",
        "resolve_as_note",
        "dismiss",
    ]
    assert all(not hint.requires_revision for hint in hints)
    assert all(hint.requires_confirmation for hint in hints)
    assert all(hint.requires_durable_claim for hint in hints)
    assert all(hint.saga_contract == "InboxResolutionClaim" for hint in hints)
    assert all(hint.available_entrypoints for hint in hints)


@pytest.mark.parametrize(
    ("source_type", "status", "reason_code"),
    [
        ("user_task", "completed", "user_task.overdue"),
        ("waiting_for", "resolved", "waiting_for.review_due"),
        ("reminder", "triggered", "reminder.due_soon"),
        ("reminder", "scheduled", "reminder.failed"),
        ("inbox", "resolved", "inbox.pending"),
        ("work_log", "completed", "user_task.overdue"),
    ],
)
def test_wrong_source_status_or_reason_is_not_actionable(
    source_type, status, reason_code
):
    assert build_action_hints(
        _review(_item(reason_code, source_type, status))
    ) == ()


def test_hint_generation_cannot_write_publish_schedule_or_call_provider(
    monkeypatch,
):
    from core.bus.bus import MemoryBus
    from core.providers.llm.protocol import LLMProvider
    from core.scheduler.runtime import SchedulerRuntime
    from core.user_tasks.repository import SQLiteUserTaskRepository

    def fail_on_call(*_args, **_kwargs):
        raise AssertionError("Action Hint attempted a forbidden side effect")

    monkeypatch.setattr(SQLiteUserTaskRepository, "update", fail_on_call)
    monkeypatch.setattr(MemoryBus, "publish", fail_on_call)
    monkeypatch.setattr(SchedulerRuntime, "schedule", fail_on_call)
    monkeypatch.setattr(LLMProvider, "generate", fail_on_call)

    hints = build_action_hints(
        _review(_item("user_task.overdue", "user_task", "active"))
    )
    assert [hint.allowed_action for hint in hints] == ["complete", "cancel"]
