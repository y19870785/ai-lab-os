"""Pure deterministic Action Hint presentation for Daily Review facts."""

from __future__ import annotations

from dataclasses import dataclass

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
    requires_idempotency_key: bool
    requires_confirmation: bool
    requires_durable_claim: bool
    saga_contract: str | None
    available_entrypoints: tuple[str, ...]


@dataclass(frozen=True)
class _HintSpec:
    action: str
    arguments: tuple[str, ...]
    entrypoints: tuple[str, ...]
    requires_revision: bool = False
    requires_idempotency_key: bool = False
    requires_confirmation: bool = True
    requires_durable_claim: bool = False
    saga_contract: str | None = None


def _inbox(
    action: str,
    arguments: tuple[str, ...],
    api_path: str,
    cli_command: str,
) -> _HintSpec:
    return _HintSpec(
        action=action,
        arguments=arguments,
        entrypoints=(f"api:POST {api_path}", f"cli:{cli_command}"),
        requires_durable_claim=True,
        saga_contract="InboxResolutionClaim",
    )


_DECISIONS: dict[tuple[str, str, str], tuple[_HintSpec, ...]] = {
    ("user_task", "active", "user_task.overdue"): (
        _HintSpec(
            action="complete",
            arguments=("source_id", "expected_revision"),
            requires_revision=True,
            entrypoints=(
                "api:POST /daily-review/actions/user-tasks/{id}/complete",
            ),
        ),
        _HintSpec(
            action="cancel",
            arguments=("source_id", "expected_revision"),
            requires_revision=True,
            entrypoints=(
                "api:POST /daily-review/actions/user-tasks/{id}/cancel",
            ),
        ),
    ),
    ("user_task", "active", "user_task.due_soon"): (
        _HintSpec(
            action="complete",
            arguments=("source_id", "expected_revision"),
            requires_revision=True,
            entrypoints=(
                "api:POST /daily-review/actions/user-tasks/{id}/complete",
            ),
        ),
    ),
    ("waiting_for", "open", "waiting_for.expected_overdue"): (
        _HintSpec(
            action="follow_up",
            arguments=("source_id", "expected_revision", "note"),
            requires_revision=True,
            entrypoints=(
                "api:POST /waiting-for/{id}/follow-ups",
                "cli:waiting-for follow-up",
            ),
        ),
    ),
    ("waiting_for", "open", "waiting_for.review_due"): (
        _HintSpec(
            action="follow_up",
            arguments=("source_id", "expected_revision", "note"),
            requires_revision=True,
            entrypoints=(
                "api:POST /waiting-for/{id}/follow-ups",
                "cli:waiting-for follow-up",
            ),
        ),
    ),
    ("reminder", "failed", "reminder.failed"): (
        _HintSpec(
            action="reschedule",
            arguments=(
                "source_id",
                "expected_revision",
                "scheduled_for",
                "timezone",
            ),
            requires_revision=True,
            requires_idempotency_key=False,
            entrypoints=(
                "api:PATCH /reminders/{id}",
                "cli:reminder-reschedule",
            ),
            saga_contract="ReminderSchedulerBridge",
        ),
    ),
    **{
        ("reminder", status, "reminder.due_soon"): (
            _HintSpec(
                action="reschedule",
                arguments=(
                    "source_id",
                    "expected_revision",
                    "scheduled_for",
                    "timezone",
                ),
                requires_revision=True,
                requires_idempotency_key=False,
                entrypoints=(
                    "api:PATCH /reminders/{id}",
                    "cli:reminder-reschedule",
                ),
                saga_contract="ReminderSchedulerBridge",
            ),
        )
        for status in ("scheduled", "retrying")
    },
    ("inbox", "pending", "inbox.pending"): (
        _inbox(
            "resolve_to_task",
            ("source_id", "title"),
            "/inbox/{id}/resolve/task",
            "inbox resolve-task",
        ),
        _inbox(
            "resolve_to_reminder",
            ("source_id", "title", "scheduled_at", "timezone"),
            "/inbox/{id}/resolve/reminder",
            "inbox resolve-reminder",
        ),
        _inbox(
            "resolve_to_work_log",
            ("source_id", "title"),
            "/inbox/{id}/resolve/work-log",
            "inbox resolve-work-log",
        ),
        _inbox(
            "resolve_to_waiting_for",
            (
                "source_id",
                "subject",
                "waiting_on",
                "next_review_at",
                "timezone",
            ),
            "/inbox/{id}/resolve/waiting-for",
            "inbox resolve-waiting-for",
        ),
        _inbox(
            "resolve_as_note",
            ("source_id",),
            "/inbox/{id}/resolve/note",
            "inbox resolve-note",
        ),
        _inbox(
            "dismiss",
            ("source_id",),
            "/inbox/{id}/dismiss",
            "inbox dismiss",
        ),
    ),
}


def _for_item(item: DailyReviewItem) -> tuple[ActionHint, ...]:
    key = (
        item.source_type.value,
        item.status.strip().lower(),
        item.reason_code,
    )
    return tuple(
        ActionHint(
            source_type=item.source_type.value,
            source_id=item.source_id,
            status=item.status,
            reason_code=item.reason_code,
            allowed_action=spec.action,
            required_arguments=spec.arguments,
            requires_revision=spec.requires_revision,
            requires_idempotency_key=spec.requires_idempotency_key,
            requires_confirmation=spec.requires_confirmation,
            requires_durable_claim=spec.requires_durable_claim,
            saga_contract=spec.saga_contract,
            available_entrypoints=spec.entrypoints,
        )
        for spec in _DECISIONS.get(key, ())
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
