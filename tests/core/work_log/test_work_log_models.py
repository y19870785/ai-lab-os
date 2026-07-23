"""Work Log domain contract tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.work_log import (
    WorkLogContextKind,
    WorkLogContextRef,
    WorkLogCreateCommand,
    WorkLogQuery,
    WorkLogSource,
)


def test_create_normalizes_tags_and_accepts_context_refs():
    command = WorkLogCreateCommand(
        subject="  完成验货  ",
        raw_text="完成验货",
        tags=["蜂蜡", " 蜂蜡 ", "QA"],
        source=WorkLogSource.API,
        context_refs=[
            WorkLogContextRef(
                kind=WorkLogContextKind.INBOX, target_id="inbox_abc"
            )
        ],
    )
    assert command.subject == "完成验货"
    assert command.tags == ("蜂蜡", "QA")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timezone", "Not/AZone"),
        ("occurred_at", datetime(2026, 7, 23)),
        ("context_refs", [{"kind": "reminder", "target_id": "ut_wrong"}]),
    ],
)
def test_create_rejects_invalid_time_and_context(field, value):
    with pytest.raises(ValidationError):
        WorkLogCreateCommand(
            subject="x",
            raw_text="x",
            source=WorkLogSource.CLI,
            **{field: value},
        )


def test_query_enforces_range_limit_and_sort():
    with pytest.raises(ValidationError):
        WorkLogQuery(limit=201)
    with pytest.raises(ValidationError):
        WorkLogQuery(
            date_from=datetime(2026, 7, 24, tzinfo=timezone.utc),
            date_to=datetime(2026, 7, 23, tzinfo=timezone.utc),
        )
    with pytest.raises(ValidationError):
        WorkLogQuery(sort="importance")
    with pytest.raises(ValidationError):
        WorkLogQuery(context_ref="inbox_wl_not_a_context_ref")
