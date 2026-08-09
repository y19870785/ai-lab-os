"""Persistence, restart and Composition Root tests for trusted interactions."""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.database import DatabaseManager
from core.errors import FailureException
from core.interaction import (
    InteractionService,
    LifecycleState,
    SQLiteInteractionRepository,
)
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock
from tests.helpers.interaction import (
    ReferenceCanonicalCommitAuthority,
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


def build(path: Path, execution, verification, clock, canonical_commit=None):
    manager = DatabaseManager(path)
    repository = SQLiteInteractionRepository(manager, path / "interactions.db")
    return InteractionService(
        repository, clock, execution, verification,
        canonical_commit or ReferenceCanonicalCommitAuthority(clock),
    ), manager


class SimulatedProcessCrash(BaseException):
    """Escapes the port Exception boundary like an abrupt process termination."""


class CrashAfterIntentPort:
    def __init__(self) -> None:
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        raise SimulatedProcessCrash("crash after durable execution intent")


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
    assert restored.verified_result.canonical_commit_evidence_id is not None
    assert restored.canonical_commit_evidence is not None
    assert restored.canonical_commit_evidence.outcome == "COMMITTED"
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


async def test_create_idempotency_claim_is_atomic_across_independent_connections(
    tmp_path: Path,
):
    clock = MutableClock(NOW)
    first, first_manager = build(
        tmp_path, ReferenceExecutionPort(), ReferenceVerificationPort(), clock
    )
    second, second_manager = build(
        tmp_path, ReferenceExecutionPort(), ReferenceVerificationPort(), clock
    )
    await first.initialize()
    await second.initialize()
    barrier = threading.Barrier(2)
    first_create = first._repository.create
    second_create = second._repository.create

    async def race(original, *args, **kwargs):
        barrier.wait(timeout=5)
        return await original(*args, **kwargs)

    first._repository.create = lambda *args, **kwargs: race(
        first_create, *args, **kwargs
    )
    second._repository.create = lambda *args, **kwargs: race(
        second_create, *args, **kwargs
    )

    def submit(service):
        return asyncio.run(service.create_interaction(
            workspace=WORKSPACE,
            actor_id="owner-a",
            operation="quote.request",
            risk_level="high",
            policy_reference="policy-1",
            request_id="request-race",
            trace_id="trace-1",
            idempotency_key="create-race",
        ))

    with ThreadPoolExecutor(max_workers=2) as pool:
        left_future = pool.submit(submit, first)
        right_future = pool.submit(submit, second)
        left = left_future.result(timeout=10)
        right = right_future.result(timeout=10)

    first._repository.create = first_create
    second._repository.create = second_create
    assert left.interaction_id == right.interaction_id
    with first_manager.lease("interactions", tmp_path / "interactions.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM interaction_records").fetchone()[0] == 1
        claim = conn.execute(
            "SELECT interaction_id FROM interaction_idempotency WHERE operation='create'"
        ).fetchone()
    assert claim[0] == left.interaction_id
    with pytest.raises(FailureException) as conflict:
        await second.create_interaction(
            workspace=WORKSPACE,
            actor_id="owner-a",
            operation="quote.cancel",
            risk_level="high",
            policy_reference="policy-1",
            request_id="request-race",
            trace_id="trace-1",
            idempotency_key="create-race",
        )
    assert conflict.value.failure.code == "interaction.idempotency_conflict"
    with first_manager.lease("interactions", tmp_path / "interactions.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM interaction_records").fetchone()[0] == 1
    first_manager.close_all()
    second_manager.close_all()


async def test_execution_intent_crash_reconciles_after_composition_root_restart(
    tmp_path: Path,
):
    clock = MutableClock(NOW)
    crashing_port = CrashAfterIntentPort()
    first = await create_system(
        make_test_settings(tmp_path),
        clock=clock,
        interaction_execution_port=crashing_port,
    )
    await first.start()
    service = first.interaction_service
    interaction = await service.create_interaction(
        workspace=WORKSPACE, actor_id="owner-a", operation="quote.request",
        risk_level="high", policy_reference="policy-1", request_id="request-crash",
        trace_id="trace-1", idempotency_key="create-crash",
    )
    preview = await service.preview(
        workspace=WORKSPACE, actor_id="owner-a",
        interaction_id=interaction.interaction_id, expected_revision=1,
        normalized_parameters={"sku": "A"}, mutation_summary="create quote request",
        expires_in=timedelta(hours=1), idempotency_key="preview-crash",
    )
    current = await service.status(
        workspace=WORKSPACE, actor_id="owner-a",
        interaction_id=interaction.interaction_id,
    )
    await service.confirm(
        workspace=WORKSPACE, actor_id="owner-a",
        interaction_id=interaction.interaction_id, preview_id=preview.preview_id,
        preview_revision=preview.preview_revision,
        expected_revision=current.interaction.revision,
        idempotency_key="confirm-crash",
    )
    authorized = await service.status(
        workspace=WORKSPACE, actor_id="owner-a",
        interaction_id=interaction.interaction_id,
    )
    with pytest.raises(SimulatedProcessCrash):
        await service.start_execution(
            workspace=WORKSPACE, actor_id="owner-a",
            interaction_id=interaction.interaction_id,
            expected_revision=authorized.interaction.revision,
            idempotency_key="execute-crash",
        )
    crashed = await service.status(
        workspace=WORKSPACE, actor_id="owner-a",
        interaction_id=interaction.interaction_id,
    )
    original_execution_id = crashed.execution.execution_id
    assert crashed.interaction.lifecycle_state == LifecycleState.EXECUTING
    assert crashed.execution.attempt == 1
    await first.shutdown()

    replacement_executor = ReferenceExecutionPort()
    second = await create_system(
        make_test_settings(tmp_path),
        clock=clock,
        interaction_execution_port=replacement_executor,
        interaction_verification_port=ReferenceVerificationPort(verified()),
        interaction_canonical_commit_authority=ReferenceCanonicalCommitAuthority(clock),
    )
    await second.start()
    try:
        restored = await second.interaction_service.status(
            workspace=WORKSPACE, actor_id="owner-a",
            interaction_id=interaction.interaction_id,
        )
        assert restored.interaction.lifecycle_state == LifecycleState.EXECUTING
        final = await second.interaction_service.recover(
            workspace=WORKSPACE, actor_id="owner-a",
            interaction_id=interaction.interaction_id,
            expected_revision=restored.interaction.revision,
            idempotency_key="recover-crash",
        )
        assert final.interaction.lifecycle_state == LifecycleState.SUCCEEDED
        assert final.execution.execution_id == original_execution_id
        assert final.execution.attempt == 1
        assert replacement_executor.requests == []
        replay = await second.interaction_service.start_execution(
            workspace=WORKSPACE, actor_id="owner-a",
            interaction_id=interaction.interaction_id,
            expected_revision=authorized.interaction.revision,
            idempotency_key="execute-crash",
        )
        assert replay.interaction.lifecycle_state == LifecycleState.SUCCEEDED
        assert replacement_executor.requests == []
    finally:
        await second.shutdown()
