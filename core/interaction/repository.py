"""SQLite persistence for the canonical Interaction aggregate and facts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from core.database import DatabaseManager
from core.database.connection import transaction
from core.interaction.models import (
    Approval,
    AuditEvidence,
    Confirmation,
    Execution,
    Interaction,
    Preview,
    Recovery,
    VerifiedResult,
)

Fact = Preview | Confirmation | Approval | Execution | VerifiedResult | Recovery
ModelT = TypeVar("ModelT", bound=BaseModel)


class SQLiteInteractionRepository:
    """Stores aggregate snapshots and immutable/revisioned facts atomically."""

    LOGICAL_NAME = "interactions"

    def __init__(self, manager: DatabaseManager, db_path: str | Path) -> None:
        self._manager = manager
        self._path = manager.bind_path(self.LOGICAL_NAME, db_path)

    async def initialize(self) -> None:
        with (
            self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
            transaction(conn),
        ):
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS interaction_records (
                        interaction_id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        lifecycle_state TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_interaction_workspace
                    ON interaction_records(tenant_id, workspace_id, namespace, interaction_id);
                    CREATE TABLE IF NOT EXISTS interaction_facts (
                        fact_id TEXT PRIMARY KEY,
                        interaction_id TEXT NOT NULL,
                        fact_type TEXT NOT NULL,
                        fact_revision INTEGER NOT NULL,
                        payload TEXT NOT NULL,
                        FOREIGN KEY(interaction_id) REFERENCES interaction_records(interaction_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_interaction_facts
                    ON interaction_facts(interaction_id, fact_type, fact_revision DESC);
                    CREATE TABLE IF NOT EXISTS interaction_idempotency (
                        tenant_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        payload_digest TEXT NOT NULL,
                        interaction_id TEXT NOT NULL,
                        result_payload TEXT NOT NULL,
                        PRIMARY KEY(tenant_id, workspace_id, namespace, operation, idempotency_key)
                    );
                    CREATE TABLE IF NOT EXISTS interaction_audit (
                        audit_id TEXT PRIMARY KEY,
                        interaction_id TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        occurred_at TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        FOREIGN KEY(interaction_id) REFERENCES interaction_records(interaction_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_interaction_audit
                    ON interaction_audit(interaction_id, revision, occurred_at, audit_id);
                    """
                )

    @staticmethod
    def _dump(model: BaseModel) -> str:
        return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _load(model: type[ModelT], payload: str) -> ModelT:
        return model.model_validate_json(payload)

    async def idempotent_result(
        self, scope: tuple[str, str, str], operation: str, key: str, digest: str
    ) -> Interaction | None:
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            row = conn.execute(
                """SELECT payload_digest, result_payload FROM interaction_idempotency
                WHERE tenant_id=? AND workspace_id=? AND namespace=?
                AND operation=? AND idempotency_key=?""",
                (*scope, operation, key),
            ).fetchone()
        if row is None:
            return None
        if row["payload_digest"] != digest:
            raise ValueError("idempotency conflict")
        return self._load(Interaction, row["result_payload"])

    async def create(
        self,
        interaction: Interaction,
        audit: AuditEvidence,
        *,
        operation: str,
        idempotency_key: str,
        payload_digest: str,
    ) -> None:
        with (
            self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
            transaction(conn),
        ):
                conn.execute(
                    """INSERT INTO interaction_records
                    (interaction_id,tenant_id,workspace_id,namespace,revision,lifecycle_state,payload)
                    VALUES(?,?,?,?,?,?,?)""",
                    (
                        interaction.interaction_id, interaction.tenant_id,
                        interaction.workspace_id, interaction.namespace,
                        interaction.revision, interaction.lifecycle_state.value,
                        self._dump(interaction),
                    ),
                )
                self._insert_audit(conn, audit)
                self._insert_idempotency(
                    conn, interaction, operation, idempotency_key, payload_digest
                )

    async def transition(
        self,
        interaction: Interaction,
        expected_revision: int,
        facts: Iterable[Fact],
        audits: Iterable[AuditEvidence],
        *,
        operation: str,
        idempotency_key: str,
        payload_digest: str,
    ) -> None:
        with (
            self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
            transaction(conn),
        ):
                cursor = conn.execute(
                    """UPDATE interaction_records SET revision=?, lifecycle_state=?, payload=?
                    WHERE interaction_id=? AND tenant_id=? AND workspace_id=? AND namespace=?
                    AND revision=?""",
                    (
                        interaction.revision, interaction.lifecycle_state.value,
                        self._dump(interaction), interaction.interaction_id,
                        interaction.tenant_id, interaction.workspace_id,
                        interaction.namespace, expected_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("revision or workspace conflict")
                for fact in facts:
                    fact_id = next(
                        str(value) for name, value in fact if name.endswith("_id") and name != "interaction_id"
                    )
                    fact_revision = getattr(fact, "preview_revision", interaction.revision)
                    conn.execute(
                        """INSERT OR REPLACE INTO interaction_facts
                        (fact_id,interaction_id,fact_type,fact_revision,payload)
                        VALUES(?,?,?,?,?)""",
                        (fact_id, interaction.interaction_id, fact.__class__.__name__, fact_revision, self._dump(fact)),
                    )
                for audit in audits:
                    self._insert_audit(conn, audit)
                self._insert_idempotency(
                    conn, interaction, operation, idempotency_key, payload_digest
                )

    def _insert_idempotency(self, conn, interaction, operation, key, digest) -> None:
        cursor = conn.execute(
            """INSERT INTO interaction_idempotency
            (tenant_id,workspace_id,namespace,operation,idempotency_key,payload_digest,interaction_id,result_payload)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id,workspace_id,namespace,operation,idempotency_key)
            DO UPDATE SET interaction_id=excluded.interaction_id,
                          result_payload=excluded.result_payload
            WHERE interaction_idempotency.payload_digest=excluded.payload_digest""",
            (
                interaction.tenant_id, interaction.workspace_id, interaction.namespace,
                operation, key, digest, interaction.interaction_id, self._dump(interaction),
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("idempotency conflict")

    def _insert_audit(self, conn, audit: AuditEvidence) -> None:
        conn.execute(
            "INSERT INTO interaction_audit(audit_id,interaction_id,revision,occurred_at,payload) VALUES(?,?,?,?,?)",
            (audit.audit_id, audit.interaction_id, audit.revision, audit.occurred_at.isoformat(), self._dump(audit)),
        )

    async def get(self, scope: tuple[str, str, str], interaction_id: str) -> Interaction | None:
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            row = conn.execute(
                """SELECT payload FROM interaction_records WHERE interaction_id=?
                AND tenant_id=? AND workspace_id=? AND namespace=?""",
                (interaction_id, *scope),
            ).fetchone()
        return None if row is None else self._load(Interaction, row["payload"])

    async def fact(self, interaction_id: str, fact_type: type[ModelT], fact_id: str | None) -> ModelT | None:
        if fact_id is None:
            return None
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            row = conn.execute(
                "SELECT payload FROM interaction_facts WHERE interaction_id=? AND fact_type=? AND fact_id=?",
                (interaction_id, fact_type.__name__, fact_id),
            ).fetchone()
        return None if row is None else self._load(fact_type, row["payload"])

    async def audits(self, scope: tuple[str, str, str], interaction_id: str) -> list[AuditEvidence]:
        if await self.get(scope, interaction_id) is None:
            return []
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            rows = conn.execute(
                "SELECT payload FROM interaction_audit WHERE interaction_id=? ORDER BY revision,occurred_at,audit_id",
                (interaction_id,),
            ).fetchall()
        return [self._load(AuditEvidence, row["payload"]) for row in rows]
