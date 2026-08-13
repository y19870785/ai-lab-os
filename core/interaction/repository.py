"""SQLite persistence for the canonical Interaction aggregate and facts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from core.database import DatabaseManager
from core.database.connection import transaction
from core.interaction.models import (
    Approval,
    AuditEvidence,
    CanonicalCommitEvidence,
    Confirmation,
    Execution,
    Interaction,
    Preview,
    Recovery,
    VerifiedResult,
)

Fact = (
    Preview | Confirmation | Approval | Execution | VerifiedResult
    | CanonicalCommitEvidence | Recovery
)
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
                    CREATE TABLE IF NOT EXISTS trusted_ingress_evidence (
                        evidence_id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        payload_digest TEXT NOT NULL,
                        accepted_at TEXT NOT NULL,
                        verification_key_id TEXT NOT NULL,
                        verification_status TEXT NOT NULL,
                        consumption_status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        consumed_at TEXT,
                        consumed_interaction_id TEXT,
                        consumed_preview_id TEXT,
                        consumed_preview_revision INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS interaction_confirmation_challenges (
                        challenge_id TEXT PRIMARY KEY,
                        interaction_id TEXT NOT NULL,
                        preview_id TEXT NOT NULL,
                        preview_revision INTEGER NOT NULL,
                        interaction_revision INTEGER NOT NULL,
                        challenge_digest TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        consumed_at TEXT
                    );
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
    ) -> Interaction:
        with (
            self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
            transaction(conn),
        ):
                existing = self._claim_create_idempotency(
                    conn, interaction, operation, idempotency_key, payload_digest
                )
                if existing is not None:
                    return existing
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
                return interaction

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
        trusted_evidence_consumption: dict[str, object] | None = None,
    ) -> None:
        with (
            self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
            transaction(conn),
        ):
                if trusted_evidence_consumption is not None:
                    evidence_cursor = conn.execute(
                        """UPDATE trusted_ingress_evidence
                        SET consumption_status='CONSUMED', revision=revision+1,
                            consumed_at=?, consumed_interaction_id=?,
                            consumed_preview_id=?, consumed_preview_revision=?
                        WHERE evidence_id=? AND consumption_status='UNUSED'
                        AND revision=?""",
                        (
                            trusted_evidence_consumption["consumed_at"],
                            interaction.interaction_id,
                            trusted_evidence_consumption["preview_id"],
                            trusted_evidence_consumption["preview_revision"],
                            trusted_evidence_consumption["evidence_id"],
                            trusted_evidence_consumption["evidence_revision"],
                        ),
                    )
                    challenge_cursor = conn.execute(
                        """UPDATE interaction_confirmation_challenges
                        SET status='CONSUMED', consumed_at=?
                        WHERE challenge_id=? AND interaction_id=? AND preview_id=?
                        AND preview_revision=? AND interaction_revision=?
                        AND status='ACTIVE'""",
                        (
                            trusted_evidence_consumption["consumed_at"],
                            trusted_evidence_consumption["challenge_id"],
                            interaction.interaction_id,
                            trusted_evidence_consumption["preview_id"],
                            trusted_evidence_consumption["preview_revision"],
                            expected_revision,
                        ),
                    )
                    if evidence_cursor.rowcount != 1 or challenge_cursor.rowcount != 1:
                        raise ValueError("trusted evidence consumption conflict")
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

    async def store_trusted_ingress_evidence(
        self, *, evidence_id: str, payload: str, payload_digest: str,
        accepted_at: str, verification_key_id: str,
    ) -> None:
        """Persist one verified immutable envelope; duplicate identity is idempotent."""

        with (
            self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
            transaction(conn),
        ):
            cursor = conn.execute(
                """INSERT INTO trusted_ingress_evidence
                (evidence_id,payload,payload_digest,accepted_at,verification_key_id,
                 verification_status,consumption_status,revision)
                VALUES(?,?,?,?,?,'VERIFIED','UNUSED',1)
                ON CONFLICT(evidence_id) DO NOTHING""",
                (evidence_id, payload, payload_digest, accepted_at, verification_key_id),
            )
            if cursor.rowcount == 0:
                row = conn.execute(
                    """SELECT payload_digest FROM trusted_ingress_evidence
                    WHERE evidence_id=?""",
                    (evidence_id,),
                ).fetchone()
                if row is None or row["payload_digest"] != payload_digest:
                    raise ValueError("trusted evidence identity conflict")

    async def trusted_ingress_evidence(self, evidence_id: str) -> dict[str, object] | None:
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            row = conn.execute(
                "SELECT * FROM trusted_ingress_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
        return None if row is None else dict(row)

    async def store_confirmation_challenge(
        self, *, challenge_id: str, interaction_id: str, preview_id: str,
        preview_revision: int, interaction_revision: int, challenge_digest: str,
        created_at: str, expires_at: str,
    ) -> None:
        with (
            self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
            transaction(conn),
        ):
            conn.execute(
                """INSERT INTO interaction_confirmation_challenges
                (challenge_id,interaction_id,preview_id,preview_revision,
                 interaction_revision,challenge_digest,created_at,expires_at,status)
                VALUES(?,?,?,?,?,?,?,?,'ACTIVE')""",
                (challenge_id, interaction_id, preview_id, preview_revision,
                 interaction_revision, challenge_digest, created_at, expires_at),
            )

    async def confirmation_challenge(
        self, interaction_id: str, preview_id: str,
    ) -> dict[str, object] | None:
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            row = conn.execute(
                """SELECT * FROM interaction_confirmation_challenges
                WHERE interaction_id=? AND preview_id=?
                ORDER BY created_at DESC LIMIT 1""",
                (interaction_id, preview_id),
            ).fetchone()
        return None if row is None else dict(row)

    def _insert_idempotency(self, conn, interaction, operation, key, digest) -> None:
        cursor = conn.execute(
            """INSERT INTO interaction_idempotency
            (tenant_id,workspace_id,namespace,operation,idempotency_key,payload_digest,interaction_id,result_payload)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id,workspace_id,namespace,operation,idempotency_key)
            DO NOTHING""",
            (
                interaction.tenant_id, interaction.workspace_id, interaction.namespace,
                operation, key, digest, interaction.interaction_id, self._dump(interaction),
            ),
        )
        if cursor.rowcount == 1:
            return
        row = conn.execute(
            """SELECT payload_digest,interaction_id FROM interaction_idempotency
            WHERE tenant_id=? AND workspace_id=? AND namespace=?
            AND operation=? AND idempotency_key=?""",
            (
                interaction.tenant_id, interaction.workspace_id, interaction.namespace,
                operation, key,
            ),
        ).fetchone()
        if (row is None or row["payload_digest"] != digest
                or row["interaction_id"] != interaction.interaction_id):
            raise ValueError("idempotency conflict")
        conn.execute(
            """UPDATE interaction_idempotency SET result_payload=?
            WHERE tenant_id=? AND workspace_id=? AND namespace=?
            AND operation=? AND idempotency_key=? AND payload_digest=?
            AND interaction_id=?""",
            (
                self._dump(interaction), interaction.tenant_id,
                interaction.workspace_id, interaction.namespace, operation, key,
                digest, interaction.interaction_id,
            ),
        )

    def _claim_create_idempotency(
        self, conn, interaction: Interaction, operation: str, key: str, digest: str
    ) -> Interaction | None:
        """Atomically claim create identity before inserting the aggregate."""

        try:
            conn.execute(
                """INSERT INTO interaction_idempotency
                (tenant_id,workspace_id,namespace,operation,idempotency_key,
                 payload_digest,interaction_id,result_payload)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    interaction.tenant_id, interaction.workspace_id,
                    interaction.namespace, operation, key, digest,
                    interaction.interaction_id, self._dump(interaction),
                ),
            )
            return None
        except sqlite3.IntegrityError:
            row = conn.execute(
                """SELECT payload_digest,result_payload FROM interaction_idempotency
                WHERE tenant_id=? AND workspace_id=? AND namespace=?
                AND operation=? AND idempotency_key=?""",
                (
                    interaction.tenant_id, interaction.workspace_id,
                    interaction.namespace, operation, key,
                ),
            ).fetchone()
            if row is None or row["payload_digest"] != digest:
                raise ValueError("idempotency conflict") from None
            return self._load(Interaction, row["result_payload"])

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
