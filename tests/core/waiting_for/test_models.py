from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from core.waiting_for import (
    WaitingFor,
    WaitingForEvent,
    WaitingForEventType,
    WaitingForStatus,
)
from core.workspace.models import WorkspaceKey


NOW = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)


def _item(**changes):
    values = {
        "workspace_key": WorkspaceKey(),
        "subject": "  蜂蜡检测方案  ",
        "waiting_on": " 张经理 ",
        "context": " 等待最终检测项目 ",
        "source": " test ",
        "created_at": NOW,
        "updated_at": NOW,
        "timezone": "Asia/Shanghai",
    }
    values.update(changes)
    return WaitingFor(**values)


def test_item_trims_text_normalizes_time_and_derives_attention():
    item = _item(
        expected_by=NOW - timedelta(minutes=1),
        next_review_at=NOW,
    )

    assert item.subject == "蜂蜡检测方案"
    assert item.waiting_on == "张经理"
    assert item.context == "等待最终检测项目"
    assert item.created_at == NOW
    assert item.review_due(NOW) is True
    assert item.expected_overdue(NOW) is True
    assert item.attention_due(NOW) is True


@pytest.mark.parametrize("field", ["subject", "waiting_on"])
def test_required_text_rejects_blank(field):
    with pytest.raises(ValidationError):
        _item(**{field: "   "})


def test_naive_datetime_and_invalid_timezone_are_rejected():
    with pytest.raises(ValidationError):
        _item(created_at=datetime(2026, 7, 22, 8, 0))
    with pytest.raises(ValidationError):
        _item(timezone="Mars/Olympus")


def test_terminal_state_fields_must_be_consistent():
    with pytest.raises(ValidationError):
        _item(status=WaitingForStatus.RESOLVED)
    resolved = _item(
        status=WaitingForStatus.RESOLVED,
        resolved_at=NOW,
        resolution_note="已确认",
    )
    cancelled = _item(status=WaitingForStatus.CANCELLED, cancelled_at=NOW)

    assert resolved.resolution_note == "已确认"
    assert cancelled.cancelled_at == NOW
    assert resolved.review_due(NOW + timedelta(days=1)) is False


@pytest.mark.parametrize(
    "metadata",
    [
        {"api_key": "nope"},
        {"nested": {"authorization": "nope"}},
        {"items": [{"token": "nope"}]},
    ],
)
def test_sensitive_metadata_is_rejected_recursively(metadata):
    with pytest.raises(ValidationError):
        _item(metadata=metadata)


def test_metadata_must_be_json_serializable():
    with pytest.raises(ValidationError):
        _item(metadata={"invalid": object()})


def test_event_is_immutable_and_validates_sequence_and_time():
    item = _item()
    event = WaitingForEvent(
        waiting_for_id=item.id,
        workspace_key=item.workspace_key,
        sequence=1,
        event_type=WaitingForEventType.CREATED,
        occurred_at=NOW,
        source="test",
    )

    with pytest.raises(ValidationError):
        event.sequence = 2
    with pytest.raises(ValidationError):
        WaitingForEvent(
            waiting_for_id=item.id,
            workspace_key=item.workspace_key,
            sequence=0,
            event_type=WaitingForEventType.CREATED,
            occurred_at=NOW,
            source="test",
        )
