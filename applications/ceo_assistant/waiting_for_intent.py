"""Deterministic Waiting-For parsing for CEO Assistant read and write boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from core.clock import Clock
from core.errors import ErrorCategory, FailureException, FailureInfo

from applications.ceo_assistant.reminder_intent import TaskReminderIntentParser


_WAITING_FOR_ID = re.compile(r"\bwf_[A-Za-z0-9_]+\b")
_INBOX_ID = re.compile(r"\binbox_[A-Za-z0-9_]+\b")
_ISO_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})"
)
_CONFIRM_FIELDS = re.compile(
    r"(?:等待|等)\s*(?P<waiting_on>[^，,。\n:：]+?)\s*回复\s*"
    r"(?P<subject>.+?)(?=今天|明天|\d{4}-\d{2}-\d{2}T|$)",
    re.DOTALL,
)


@dataclass(frozen=True)
class WaitingForConfirmation:
    inbox_item_id: str
    subject: str
    waiting_on: str
    next_review_at: datetime
    timezone: str


def extract_waiting_for_id(text: str) -> str | None:
    match = _WAITING_FOR_ID.search(text)
    return match.group(0) if match else None


def extract_inbox_id(text: str) -> str | None:
    match = _INBOX_ID.search(text)
    return match.group(0) if match else None


def extract_waiting_for_capture_content(text: str) -> str | None:
    """Recognize narrow ambiguous capture wording without matching read queries."""

    stripped = text.strip()
    if any(marker in stripped for marker in ("查看", "哪些", "谁回复", "催办的事项")):
        return None
    if stripped.startswith(("等", "等待")) and "回复" in stripped:
        return stripped
    if "还没回复" in stripped:
        return stripped
    if stripped.startswith("先记下来") and "等" in stripped:
        return stripped
    return None


def parse_waiting_for_time(text: str, timezone_name: str, clock: Clock) -> datetime:
    """Parse only an explicit ISO offset or the existing deterministic CN subset."""

    iso = _ISO_DATETIME.search(text)
    if iso:
        value = datetime.fromisoformat(iso.group(0).replace("Z", "+00:00"))
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(timezone.utc)

    parsed = TaskReminderIntentParser(timezone_name, clock).parse(text)
    if parsed.due_at is not None:
        return parsed.due_at
    raise FailureException(
        FailureInfo(
            code="waiting_for.time_unsupported",
            category=ErrorCategory.VALIDATION,
            message="Waiting-For time is not supported",
            component="waiting_for.intent",
            operation="parse_time",
            retryable=False,
        )
    )


def parse_waiting_for_confirmation(
    text: str, timezone_name: str, clock: Clock
) -> WaitingForConfirmation:
    inbox_item_id = extract_inbox_id(text)
    fields = _CONFIRM_FIELDS.search(text)
    missing = []
    if inbox_item_id is None:
        missing.append("inbox_item_id")
    if fields is None:
        missing.extend(("subject", "waiting_on"))
    if missing:
        raise FailureException(
            FailureInfo(
                code="inbox.waiting_for.fields_missing",
                category=ErrorCategory.VALIDATION,
                message="Waiting-For confirmation fields are missing",
                component="waiting_for.intent",
                operation="parse_confirmation",
                retryable=False,
                details={
                    "missing_fields": missing,
                    "confirmation_template": (
                        "把 inbox_x 整理成等待事项：等待<对象>回复<事项>，"
                        "明天下午三点再看"
                    ),
                },
            )
        )
    assert inbox_item_id is not None and fields is not None
    waiting_on = fields.group("waiting_on").strip(" ，,。:：\n")
    subject = fields.group("subject").strip(" ，,。:：\n")
    next_review_at = parse_waiting_for_time(text, timezone_name, clock)
    return WaitingForConfirmation(
        inbox_item_id=inbox_item_id,
        subject=subject,
        waiting_on=waiting_on,
        next_review_at=next_review_at,
        timezone=timezone_name,
    )


def extract_action_note(text: str) -> str:
    parts = re.split(r"[：:]", text, maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""
