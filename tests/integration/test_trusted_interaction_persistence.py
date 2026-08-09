"""Persistence, restart and Composition Root tests for trusted interactions."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.database import DatabaseManager
from core.interaction import (
    InteractionService,
    LifecycleState,
    SQLiteInteractionRepository,
)
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock
from tests.helpers.interaction import (
    ReferenceExecutionPort,
    ReferenceVerificationPort,
    acknowledged,
    verified,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")
NOW = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)
WORKSPACE = WorkspaceKey(
    tenant_id="tenant-a", workspace_id="workspace-a", namespace="business",
    user_id="owner-a", trace_id="trace-1",
)


def build(path: Path, execution, verification, clock):
    manager = DatabaseManager(path)
    repository = SQLiteInteractionRepository(manager, path / "interactions.db")
    return InteractionService(repository, clock, execution, verification), manager


async def test_acknowledgement_requires_verified_result_and_survives_restart(tmp_path: Path):
    clock = MutableClock(NOW)
    executor = ReferenceExecutionPort(acknowledged())
    first, manager = build(tmp_path, executor, ReferenceVerificationPort(), clock)
    await first.initialize()
    interaction = await first.create_interaction(
        workspace=WORKSPACE, actor_id="owner-a", operation="quote.request",
        risk_level="high", policy_reference="policy-1", request_id="request-1",
        trace_id="trace-1", idempotency_key="create",
    )
    preview = await first.preview(
        workspace=WORKSPACE, actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=1, normalized_parameters={"sku": "A"},
        mutation_summary="create quote request", expires_in=timedelta(hours=1),
        idempotency_key="preview",
    )
    status = await first.status(workspace=WORKSPACE, actor_id="owner-a",
                                interaction_id=interaction.interaction_id)
    await first.confirm(
        workspace=WORKSPACE, actor_id="owner-a", interaction_id=interaction.interaction_id,
        preview_id=preview.preview_id, preview_revision=preview.preview_revision,
        expected_revision=status.interaction.revision, idempotency_key="confirm",
    )
    status = await first.status(workspace=WORKSPACE, actor_id="owner-a",
                                interaction_id=interaction.interaction_id)
    status = await first.start_execution(
        workspace=WORKSPACE, actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=status.interaction.revision, idempotency_key="execute",
    )
    assert status.interaction.lifecycle_state == LifecycleState.VERIFYING
    assert status.verified_result is None
    assert len(executor.requests) == 1
    manager.close_all()

    second, second_manager = build(
        tmp_path, ReferenceExecutionPort(), ReferenceVerificationPort(verified()), clock
    )
    await second.initialize()
    restored = await second.status(workspace=WORKSPACE, actor_id="owner-a",
                                   interaction_id=interaction.interaction_id)
    assert restored.interaction.lifecycle_state == LifecycleState.VERIFYING
    restored = await second.verify(
        workspace=WORKSPACE, actor_id="owner-a", interaction_id=interaction.interaction_id,
        expected_revision=restored.interaction.revision, idempotency_key="verify",
    )
    assert restored.interaction.lifecycle_state == LifecycleState.SUCCEEDED
    assert restored.verified_result is not None
    assert restored.verified_result.canonical_commit_succeeded is True
    second_manager.close_all()


async def test_composition_root_uses_disabled_ports_and_manager_owned_database(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path), clock=MutableClock(NOW))
    await system.start()
    try:
        assert system.interaction_service is not None
        assert system.interaction_repository is not None
        assert system.database_manager.connection_count > 0
    finally:
        await system.shutdown()
    assert system.database_manager.connection_count == 0


async def test_additive_schema_initialization_is_repeatable_and_preserves_existing_data(
    tmp_path: Path,
):
    db_path = tmp_path / "interactions.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE legacy_sentinel(value TEXT NOT NULL)")
    connection.execute("INSERT INTO legacy_sentinel VALUES ('preserved')")
    connection.commit()
    connection.close()

    service, manager = build(
        tmp_path, ReferenceExecutionPort(), ReferenceVerificationPort(),
        MutableClock(NOW),
    )
    await service.initialize()
    await service.initialize()
    with manager.lease("interactions", db_path) as managed:
        assert managed.execute("SELECT value FROM legacy_sentinel").fetchone()[0] == "preserved"
        tables = {
            row[0] for row in managed.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {
        "interaction_records", "interaction_facts", "interaction_idempotency",
        "interaction_audit",
    } <= tables
    manager.close_all()
