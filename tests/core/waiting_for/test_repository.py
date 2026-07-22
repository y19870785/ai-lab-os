from datetime import datetime, timedelta, timezone

import pytest

from core.database import DatabaseManager
from core.waiting_for import (
    SQLiteWaitingForRepository,
    WaitingFor,
    WaitingForConflictError,
    WaitingForEvent,
    WaitingForEventType,
    WaitingForView,
    WaitingForWorkspaceMismatchError,
)
from core.waiting_for.exceptions import WaitingForPersistenceError
from core.workspace.models import WorkspaceKey


NOW = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)


def _snapshot(workspace, item_id, *, minute=0, **changes):
    values = {
        "id": item_id,
        "workspace_key": workspace,
        "subject": f"subject {item_id}",
        "waiting_on": "external owner",
        "source": "test",
        "created_at": NOW + timedelta(minutes=minute),
        "updated_at": NOW + timedelta(minutes=minute),
        "timezone": "Asia/Shanghai",
    }
    values.update(changes)
    return WaitingFor(**values)


def _event(item, event_type=WaitingForEventType.CREATED, note=""):
    return WaitingForEvent(
        waiting_for_id=item.id,
        workspace_key=item.workspace_key,
        sequence=item.revision,
        event_type=event_type,
        occurred_at=item.updated_at,
        note=note,
        source="test",
    )


@pytest.mark.asyncio
async def test_schema_indexes_create_get_workspace_and_restart(tmp_path):
    path = tmp_path / "followups.db"
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, path)
    await repository.initialize()
    alpha = WorkspaceKey(workspace_id="alpha")
    beta = WorkspaceKey(workspace_id="beta")
    item = _snapshot(alpha, "wf_restart")

    await repository.create(item, _event(item))
    assert (await repository.get(alpha, item.id)).subject == item.subject
    with pytest.raises(WaitingForWorkspaceMismatchError):
        await repository.get(beta, item.id)

    with manager.lease("waiting_for") as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
    assert {"waiting_for_items", "waiting_for_events"} <= tables
    assert {
        "idx_waiting_for_workspace_status_review",
        "idx_waiting_for_linked_task",
        "idx_waiting_for_linked_reminder",
        "idx_waiting_for_events_workspace_item_sequence",
    } <= indexes
    await repository.close()

    restarted_manager = DatabaseManager(tmp_path)
    restarted = SQLiteWaitingForRepository(restarted_manager, path)
    await restarted.initialize()
    assert (await restarted.get(alpha, item.id)).revision == 1
    history = await restarted.list_events(alpha, item.id, limit=10, offset=0)
    assert [event.event_type for event in history.items] == [
        WaitingForEventType.CREATED
    ]


@pytest.mark.asyncio
async def test_create_is_atomic_when_event_insert_fails(tmp_path, monkeypatch):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, tmp_path / "followups.db")
    await repository.initialize()
    item = _snapshot(WorkspaceKey(), "wf_atomic_create")

    def fail_event(_conn, _event):
        raise RuntimeError("injected event failure")

    monkeypatch.setattr(repository, "_insert_event", fail_event)
    with pytest.raises(WaitingForPersistenceError):
        await repository.create(item, _event(item))

    with manager.lease("waiting_for") as conn:
        assert conn.execute("SELECT COUNT(*) FROM waiting_for_items").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM waiting_for_events").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_stable_pagination_and_derived_views_are_workspace_scoped(tmp_path):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, tmp_path / "followups.db")
    await repository.initialize()
    alpha = WorkspaceKey(workspace_id="alpha")
    beta = WorkspaceKey(workspace_id="beta")
    items = [
        _snapshot(alpha, "wf_a", next_review_at=NOW - timedelta(minutes=1)),
        _snapshot(alpha, "wf_b", expected_by=NOW - timedelta(minutes=1)),
        _snapshot(alpha, "wf_c", minute=1),
        _snapshot(beta, "wf_foreign", next_review_at=NOW - timedelta(days=1)),
    ]
    for item in items:
        await repository.create(item, _event(item))

    first = await repository.list(
        alpha, view=WaitingForView.OPEN, now=NOW, limit=2, offset=0
    )
    second = await repository.list(
        alpha, view=WaitingForView.OPEN, now=NOW, limit=2, offset=2
    )
    attention = await repository.list(
        alpha, view=WaitingForView.ATTENTION, now=NOW, limit=10, offset=0
    )

    assert [item.id for item in first.items] == ["wf_a", "wf_b"]
    assert first.has_more is True
    assert [item.id for item in second.items] == ["wf_c"]
    assert {item.id for item in attention.items} == {"wf_a", "wf_b"}
    assert all(item.id != "wf_foreign" for item in first.items + second.items)


@pytest.mark.asyncio
async def test_cas_mutation_is_atomic_and_conflict_adds_no_event(tmp_path, monkeypatch):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, tmp_path / "followups.db")
    await repository.initialize()
    workspace = WorkspaceKey()
    item = _snapshot(workspace, "wf_atomic_mutation")
    await repository.create(item, _event(item))
    updated = WaitingFor.model_validate(
        {
            **item.model_dump(),
            "updated_at": NOW + timedelta(minutes=1),
            "next_review_at": NOW + timedelta(days=1),
            "revision": 2,
        }
    )
    mutation_event = _event(updated, WaitingForEventType.SNOOZED, "later")

    original_insert = repository._insert_event

    def fail_second_event(conn, event):
        if event.sequence == 2:
            raise RuntimeError("injected event failure")
        original_insert(conn, event)

    monkeypatch.setattr(repository, "_insert_event", fail_second_event)
    with pytest.raises(WaitingForPersistenceError):
        await repository.mutate(
            workspace, updated=updated, event=mutation_event, expected_revision=1
        )
    stored = await repository.get(workspace, item.id)
    history = await repository.list_events(workspace, item.id, limit=10, offset=0)
    assert stored.revision == 1
    assert stored.next_review_at is None
    assert [event.sequence for event in history.items] == [1]

    monkeypatch.setattr(repository, "_insert_event", original_insert)
    await repository.mutate(
        workspace, updated=updated, event=mutation_event, expected_revision=1
    )
    with pytest.raises(WaitingForConflictError):
        await repository.mutate(
            workspace, updated=updated, event=mutation_event, expected_revision=1
        )
    history = await repository.list_events(workspace, item.id, limit=10, offset=0)
    assert [event.sequence for event in history.items] == [1, 2]


@pytest.mark.asyncio
async def test_duplicate_id_is_a_conflict(tmp_path):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, tmp_path / "followups.db")
    await repository.initialize()
    item = _snapshot(WorkspaceKey(), "wf_duplicate")
    await repository.create(item, _event(item))

    with pytest.raises(WaitingForConflictError):
        await repository.create(item, _event(item))


@pytest.mark.asyncio
async def test_create_rejects_workspace_and_created_event_invariant_mismatches(tmp_path):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, tmp_path / "followups.db")
    await repository.initialize()
    alpha = WorkspaceKey(workspace_id="alpha")
    beta = WorkspaceKey(workspace_id="beta")
    item = _snapshot(alpha, "wf_create_invariant")
    foreign_event = _event(item).model_copy(update={"workspace_key": beta})

    with pytest.raises(WaitingForConflictError):
        await repository.create(item, foreign_event)
    with manager.lease("waiting_for") as conn:
        assert conn.execute("SELECT COUNT(*) FROM waiting_for_items").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM waiting_for_events").fetchone()[0] == 0

    wrong_type = _event(item, WaitingForEventType.FOLLOWED_UP)
    with pytest.raises(WaitingForConflictError):
        await repository.create(item, wrong_type)


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_part", ["updated", "event"])
async def test_mutation_rejects_workspace_mismatch_without_state_change(
    tmp_path, foreign_part
):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteWaitingForRepository(manager, tmp_path / "followups.db")
    await repository.initialize()
    alpha = WorkspaceKey(workspace_id="alpha")
    beta = WorkspaceKey(workspace_id="beta")
    item = _snapshot(alpha, f"wf_mutation_{foreign_part}")
    await repository.create(item, _event(item))
    updated = item.model_copy(
        update={"revision": 2, "updated_at": NOW + timedelta(minutes=1)}
    )
    event = _event(updated, WaitingForEventType.FOLLOWED_UP)
    if foreign_part == "updated":
        updated = updated.model_copy(update={"workspace_key": beta})
    else:
        event = event.model_copy(update={"workspace_key": beta})

    with pytest.raises(WaitingForConflictError):
        await repository.mutate(
            alpha, updated=updated, event=event, expected_revision=1
        )
    stored = await repository.get(alpha, item.id)
    history = await repository.list_events(alpha, item.id, limit=10, offset=0)
    assert stored.revision == 1
    assert [value.sequence for value in history.items] == [1]
