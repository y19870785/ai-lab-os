from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from core.inbox import InboxItem, InboxResolvedType, InboxStatus
from core.workspace.models import WorkspaceKey


NOW = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)


def _item(**changes):
    values = {
        "workspace_key": WorkspaceKey(),
        "content": "  跟进包装供应商  ",
        "source": "cli",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return InboxItem(**values)


def test_pending_item_is_trimmed_and_uses_aware_utc_times():
    item = _item()

    assert item.content == "跟进包装供应商"
    assert item.status == InboxStatus.PENDING
    assert item.created_at == NOW
    assert item.resolved_type is None


@pytest.mark.parametrize("content", ["", "   "])
def test_blank_content_is_rejected(content):
    with pytest.raises(ValidationError):
        _item(content=content)


def test_naive_time_is_rejected():
    with pytest.raises(ValidationError):
        _item(created_at=datetime(2026, 7, 19, 4, 0))


def test_resolved_fields_must_match_status():
    with pytest.raises(ValidationError):
        _item(resolved_type=InboxResolvedType.NOTE)

    resolved = _item(
        status=InboxStatus.RESOLVED,
        updated_at=NOW + timedelta(minutes=1),
        resolved_at=NOW + timedelta(minutes=1),
        resolved_type=InboxResolvedType.USER_TASK,
        resolved_target_id="ut_123",
    )
    assert resolved.resolved_target_id == "ut_123"


def test_note_and_dismissed_resolution_do_not_require_target():
    note = _item(
        status=InboxStatus.RESOLVED,
        resolved_at=NOW,
        resolved_type=InboxResolvedType.NOTE,
    )
    dismissed = _item(
        status=InboxStatus.DISMISSED,
        resolved_at=NOW,
        resolved_type=InboxResolvedType.DISMISSED,
    )

    assert note.resolved_target_id is None
    assert dismissed.resolved_target_id is None


def test_sensitive_metadata_key_is_rejected():
    with pytest.raises(ValidationError):
        _item(metadata={"api_key": "must-not-be-stored"})


def test_metadata_must_be_json_serializable():
    with pytest.raises(ValidationError):
        _item(metadata={"invalid": object()})
