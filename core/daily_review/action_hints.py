"""Pure deterministic Action Hint presentation for Daily Review facts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from core.daily_review.models import DailyReview, DailyReviewItem


class ActionHint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str
    source_id: str
    status: str
    reason_code: str
    allowed_action: str
    required_arguments: tuple[str, ...]
    requires_revision: bool
    requires_confirmation: bool
    available_entrypoints: tuple[str, ...]


_MAPPINGS: dict[str, tuple[tuple[str, tuple[str, ...], bool, bool, tuple[str, ...]], ...]] = {
    "user_task.overdue": (
        (
            "complete",
            ("source_id", "expected_revision"),
            True,
            True,
            ("api:POST /daily-review/actions/user-tasks/{id}/complete",),
        ),
        (
            "cancel",
            ("source_id", "expected_revision"),
            True,
            True,
            ("api:POST /daily-review/actions/user-tasks/{id}/cancel",),
        ),
    ),
    "user_task.due_soon": (
        (
            "complete",
            ("source_id", "expected_revision"),
            True,
            True,
            ("api:POST /daily-review/actions/user-tasks/{id}/complete",),
        ),
    ),
    "waiting_for.expected_overdue": (
        (
            "follow_up",
            ("source_id", "expected_revision", "note"),
            True,
            True,
            (
                "api:POST /waiting-for/{id}/follow-ups",
                "cli:waiting-for follow-up",
            ),
        ),
    ),
    "waiting_for.review_due": (
        (
            "follow_up",
            ("source_id", "expected_revision", "note"),
            True,
            True,
            (
                "api:POST /waiting-for/{id}/follow-ups",
                "cli:waiting-for follow-up",
            ),
        ),
    ),
    "reminder.due_soon": (
        (
            "reschedule",
            ("source_id", "expected_revision", "scheduled_for", "timezone"),
            True,
            True,
            (
                "api:PATCH /reminders/{id}",
                "cli:reminder-reschedule",
            ),
        ),
    ),
    "reminder.failed": (
        (
            "reschedule",
            ("source_id", "expected_revision", "scheduled_for", "timezone"),
            True,
            True,
            (
                "api:PATCH /reminders/{id}",
                "cli:reminder-reschedule",
            ),
        ),
    ),
    "inbox.pending": (
        (
            "resolve",
            ("source_id", "target_type", "confirmation_fields"),
            False,
            True,
            (
                "api:POST /inbox/{id}/resolve-*",
                "cli:inbox resolve-*",
            ),
        ),
        (
            "dismiss",
            ("source_id",),
            False,
            True,
            (
                "api:POST /inbox/{id}/dismiss",
                "cli:inbox dismiss",
            ),
        ),
    ),
}


def _for_item(item: DailyReviewItem) -> tuple[ActionHint, ...]:
    mappings = _MAPPINGS.get(item.reason_code, ())
    return tuple(
        ActionHint(
            source_type=item.source_type.value,
            source_id=item.source_id,
            status=item.status,
            reason_code=item.reason_code,
            allowed_action=action,
            required_arguments=arguments,
            requires_revision=requires_revision,
            requires_confirmation=requires_confirmation,
            available_entrypoints=entrypoints,
        )
        for (
            action,
            arguments,
            requires_revision,
            requires_confirmation,
            entrypoints,
        ) in mappings
    )


def build_action_hints(review: DailyReview) -> tuple[ActionHint, ...]:
    """Map the already-paged Review without writes, events, or reordering."""

    sections = (
        review.blocked,
        review.follow_ups,
        review.in_progress,
        review.completed,
        review.informational,
        review.pending_inbox,
    )
    return tuple(
        hint
        for section in sections
        for item in section.items
        for hint in _for_item(item)
    )
