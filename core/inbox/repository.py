"""SQLite persistence for workspace-scoped Inbox items."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.database import DatabaseManager
from core.database.connection import transaction
from core.errors import RuntimeStatus
from core.inbox.exceptions import (
    InboxItemNotFoundError,
    InboxRepositoryError,
    InboxResolutionClaimConflictError,
    InboxResolutionClaimNotFoundError,
    InboxRevisionConflictError,
    InboxWorkspaceMismatchError,
)
from core.inbox.models import (
    InboxItem,
    InboxPage,
    InboxResolutionClaim,
    InboxResolutionClaimState,
    InboxResolvedType,
    InboxStatus,
    canonical_workspace,
)
from core.workspace.models import WorkspaceKey


class SQLiteInboxRepository:
    """Owns Inbox schema operations while borrowing DatabaseManager connections."""

    LOGICAL_NAME = "inbox"

    def __init__(self, database_manager: DatabaseManager, db_path: str | Path) -> None:
        self._manager = database_manager
        self._path = self._manager.bind_path(self.LOGICAL_NAME, db_path)
        self._initialized = False
        self._last_error: str | None = None

    async def initialize(self) -> None:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS inbox_items (
                            id TEXT PRIMARY KEY,
                            tenant_id TEXT NOT NULL,
                            workspace_id TEXT NOT NULL,
                            namespace TEXT NOT NULL,
                            content TEXT NOT NULL,
                            source TEXT NOT NULL,
                            status TEXT NOT NULL,
                            suggested_type TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            resolved_at TEXT,
                            resolved_type TEXT,
                            resolved_target_id TEXT,
                            metadata TEXT NOT NULL,
                            revision INTEGER NOT NULL
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_inbox_workspace_status_created
                        ON inbox_items(
                            tenant_id, workspace_id, namespace,
                            status, created_at DESC, id DESC
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_inbox_resolved_target
                        ON inbox_items(resolved_target_id)
                        WHERE resolved_target_id IS NOT NULL
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS inbox_resolution_claims (
                            inbox_item_id TEXT PRIMARY KEY,
                            tenant_id TEXT NOT NULL,
                            workspace_id TEXT NOT NULL,
                            namespace TEXT NOT NULL,
                            resolved_type TEXT NOT NULL,
                            target_key TEXT,
                            target_id TEXT,
                            state TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            revision INTEGER NOT NULL
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_inbox_claim_workspace_state
                        ON inbox_resolution_claims(
                            tenant_id, workspace_id, namespace, state, updated_at
                        )
                        """
                    )
            self._initialized = True
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox repository initialization failed") from exc

    @staticmethod
    def _values(item: InboxItem) -> tuple[object, ...]:
        data = item.model_dump(mode="json")
        workspace = canonical_workspace(item.workspace_key)
        return (
            data["id"],
            workspace.tenant_id,
            workspace.workspace_id,
            workspace.namespace,
            data["content"],
            data["source"],
            data["status"],
            data["suggested_type"],
            data["created_at"],
            data["updated_at"],
            data["resolved_at"],
            data["resolved_type"],
            data["resolved_target_id"],
            json.dumps(data["metadata"], ensure_ascii=False, sort_keys=True),
            data["revision"],
        )

    @staticmethod
    def _item(row: sqlite3.Row) -> InboxItem:
        data = dict(row)
        data["workspace_key"] = WorkspaceKey(
            tenant_id=data.pop("tenant_id"),
            workspace_id=data.pop("workspace_id"),
            namespace=data.pop("namespace"),
        )
        data["metadata"] = json.loads(data["metadata"])
        return InboxItem.model_validate(data)

    @staticmethod
    def _claim(row: sqlite3.Row) -> InboxResolutionClaim:
        data = dict(row)
        data["workspace_key"] = WorkspaceKey(
            tenant_id=data.pop("tenant_id"),
            workspace_id=data.pop("workspace_id"),
            namespace=data.pop("namespace"),
        )
        return InboxResolutionClaim.model_validate(data)

    @staticmethod
    def _scoped_item_row(
        conn: sqlite3.Connection, workspace: WorkspaceKey, item_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM inbox_items
            WHERE id=? AND tenant_id=? AND workspace_id=? AND namespace=?
            """,
            (item_id, workspace.tenant_id, workspace.workspace_id, workspace.namespace),
        ).fetchone()
        if row is not None:
            return row
        if conn.execute("SELECT 1 FROM inbox_items WHERE id=?", (item_id,)).fetchone():
            raise InboxWorkspaceMismatchError("Inbox item belongs to another workspace")
        raise InboxItemNotFoundError("Inbox item not found")

    @staticmethod
    def _scoped_claim_row(
        conn: sqlite3.Connection, workspace: WorkspaceKey, item_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM inbox_resolution_claims
            WHERE inbox_item_id=? AND tenant_id=? AND workspace_id=? AND namespace=?
            """,
            (item_id, workspace.tenant_id, workspace.workspace_id, workspace.namespace),
        ).fetchone()
        if row is not None:
            return row
        if conn.execute(
            "SELECT 1 FROM inbox_resolution_claims WHERE inbox_item_id=?", (item_id,)
        ).fetchone():
            raise InboxWorkspaceMismatchError("Inbox claim belongs to another workspace")
        raise InboxResolutionClaimNotFoundError("Inbox resolution claim not found")

    async def save(self, item: InboxItem) -> InboxItem:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute(
                        "INSERT INTO inbox_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        self._values(item),
                    )
            self._last_error = None
            return item
        except sqlite3.IntegrityError as exc:
            raise InboxRevisionConflictError("Inbox item already exists") from exc
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox item save failed") from exc

    async def get(self, workspace_key: WorkspaceKey, item_id: str) -> InboxItem:
        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                row = conn.execute(
                    """
                    SELECT * FROM inbox_items
                    WHERE id=? AND tenant_id=? AND workspace_id=? AND namespace=?
                    """,
                    (
                        item_id,
                        workspace.tenant_id,
                        workspace.workspace_id,
                        workspace.namespace,
                    ),
                ).fetchone()
                exists = row is not None or conn.execute(
                    "SELECT 1 FROM inbox_items WHERE id=?", (item_id,)
                ).fetchone() is not None
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox item query failed") from exc
        if row is not None:
            return self._item(row)
        if exists:
            raise InboxWorkspaceMismatchError("Inbox item belongs to another workspace")
        raise InboxItemNotFoundError("Inbox item not found")

    async def list(
        self,
        workspace_key: WorkspaceKey,
        *,
        status: InboxStatus | None = InboxStatus.PENDING,
        limit: int = 50,
        offset: int = 0,
    ) -> InboxPage:
        workspace = canonical_workspace(workspace_key)
        clauses = ["tenant_id=?", "workspace_id=?", "namespace=?"]
        params: list[object] = [
            workspace.tenant_id,
            workspace.workspace_id,
            workspace.namespace,
        ]
        if status is not None:
            clauses.append("status=?")
            params.append(status.value)
        params.extend((limit + 1, offset))
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                rows = conn.execute(
                    f"""
                    SELECT * FROM inbox_items
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
                ).fetchall()
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox item list failed") from exc
        return InboxPage(
            items=tuple(self._item(row) for row in rows[:limit]),
            status=status,
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def claim_resolution(
        self,
        workspace_key: WorkspaceKey,
        item_id: str,
        *,
        resolved_type: InboxResolvedType,
        target_key: str | None,
        target_id: str | None,
        now,
    ) -> InboxResolutionClaim:
        """Atomically establish or recover the one durable resolution claim."""

        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute("BEGIN IMMEDIATE")
                    item = self._item(self._scoped_item_row(conn, workspace, item_id))
                    claim_row = conn.execute(
                        "SELECT * FROM inbox_resolution_claims WHERE inbox_item_id=?",
                        (item_id,),
                    ).fetchone()
                    if claim_row is None:
                        if item.status != InboxStatus.PENDING:
                            raise InboxRevisionConflictError(
                                "Resolved Inbox item has no recoverable claim"
                            )
                        claim = InboxResolutionClaim(
                            inbox_item_id=item_id,
                            workspace_key=workspace,
                            resolved_type=resolved_type,
                            target_key=target_key,
                            target_id=target_id,
                            created_at=now,
                            updated_at=now,
                        )
                        data = claim.model_dump(mode="json")
                        conn.execute(
                            """
                            INSERT INTO inbox_resolution_claims VALUES (?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                data["inbox_item_id"],
                                workspace.tenant_id,
                                workspace.workspace_id,
                                workspace.namespace,
                                data["resolved_type"],
                                data["target_key"],
                                data["target_id"],
                                data["state"],
                                data["created_at"],
                                data["updated_at"],
                                data["revision"],
                            ),
                        )
                    else:
                        claim = self._claim(claim_row)
                        claim_workspace = canonical_workspace(claim.workspace_key)
                        if (
                            claim_workspace.tenant_id,
                            claim_workspace.workspace_id,
                            claim_workspace.namespace,
                        ) != (
                            workspace.tenant_id,
                            workspace.workspace_id,
                            workspace.namespace,
                        ):
                            raise InboxWorkspaceMismatchError(
                                "Inbox claim belongs to another workspace"
                            )
            self._last_error = None
            return claim
        except (
            InboxItemNotFoundError,
            InboxWorkspaceMismatchError,
            InboxRevisionConflictError,
        ):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox resolution claim failed") from exc

    async def get_resolution_claim(
        self, workspace_key: WorkspaceKey, item_id: str
    ) -> InboxResolutionClaim:
        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                row = self._scoped_claim_row(conn, workspace, item_id)
            self._last_error = None
            return self._claim(row)
        except (
            InboxResolutionClaimNotFoundError,
            InboxWorkspaceMismatchError,
        ):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox resolution claim query failed") from exc

    async def record_target_created(
        self,
        workspace_key: WorkspaceKey,
        item_id: str,
        *,
        resolved_type: InboxResolvedType,
        target_id: str,
        now,
    ) -> InboxResolutionClaim:
        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute("BEGIN IMMEDIATE")
                    current = self._claim(
                        self._scoped_claim_row(conn, workspace, item_id)
                    )
                    if current.resolved_type != resolved_type:
                        raise InboxResolutionClaimConflictError(
                            "Inbox resolution type does not own this claim"
                        )
                    if current.state in {
                        InboxResolutionClaimState.TARGET_CREATED,
                        InboxResolutionClaimState.COMPLETED,
                    }:
                        if current.target_id != target_id:
                            raise InboxResolutionClaimConflictError(
                                "Inbox claim already records another target"
                            )
                        updated = current
                    else:
                        cursor = conn.execute(
                            """
                            UPDATE inbox_resolution_claims
                            SET target_id=?, state=?, updated_at=?, revision=?
                            WHERE inbox_item_id=? AND tenant_id=? AND workspace_id=?
                              AND namespace=? AND revision=? AND state=?
                            """,
                            (
                                target_id,
                                InboxResolutionClaimState.TARGET_CREATED.value,
                                now.isoformat(),
                                current.revision + 1,
                                item_id,
                                workspace.tenant_id,
                                workspace.workspace_id,
                                workspace.namespace,
                                current.revision,
                                InboxResolutionClaimState.CLAIMED.value,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise InboxResolutionClaimConflictError(
                                "Inbox claim was modified concurrently"
                            )
                        updated = current.model_copy(
                            update={
                                "target_id": target_id,
                                "state": InboxResolutionClaimState.TARGET_CREATED,
                                "updated_at": now,
                                "revision": current.revision + 1,
                            }
                        )
            self._last_error = None
            return InboxResolutionClaim.model_validate(updated.model_dump())
        except (
            InboxResolutionClaimConflictError,
            InboxResolutionClaimNotFoundError,
            InboxWorkspaceMismatchError,
        ):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox target claim update failed") from exc

    async def complete_resolution(
        self,
        workspace_key: WorkspaceKey,
        item_id: str,
        *,
        resolved_type: InboxResolvedType,
        now,
    ) -> tuple[InboxItem, InboxResolutionClaim]:
        """Atomically complete the Inbox item and its durable claim."""

        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute("BEGIN IMMEDIATE")
                    item = self._item(self._scoped_item_row(conn, workspace, item_id))
                    claim = self._claim(self._scoped_claim_row(conn, workspace, item_id))
                    if claim.resolved_type != resolved_type:
                        raise InboxResolutionClaimConflictError(
                            "Inbox resolution type does not own this claim"
                        )
                    external = resolved_type in {
                        InboxResolvedType.USER_TASK,
                        InboxResolvedType.REMINDER,
                        InboxResolvedType.WORK_LOG,
                    }
                    if external and claim.state not in {
                        InboxResolutionClaimState.TARGET_CREATED,
                        InboxResolutionClaimState.COMPLETED,
                    }:
                        raise InboxResolutionClaimConflictError(
                            "Inbox target has not been durably recorded"
                        )
                    final_status = (
                        InboxStatus.DISMISSED
                        if resolved_type == InboxResolvedType.DISMISSED
                        else InboxStatus.RESOLVED
                    )
                    if item.status == InboxStatus.PENDING:
                        completed_item = item.model_copy(
                            update={
                                "status": final_status,
                                "updated_at": now,
                                "resolved_at": now,
                                "resolved_type": resolved_type,
                                "resolved_target_id": claim.target_id,
                            }
                        )
                        completed_item = InboxItem.model_validate(
                            completed_item.model_dump()
                        )
                        values = self._values(
                            completed_item.model_copy(
                                update={"revision": item.revision + 1}
                            )
                        )
                        cursor = conn.execute(
                            """
                            UPDATE inbox_items SET
                                tenant_id=?, workspace_id=?, namespace=?, content=?,
                                source=?, status=?, suggested_type=?, created_at=?,
                                updated_at=?, resolved_at=?, resolved_type=?,
                                resolved_target_id=?, metadata=?, revision=?
                            WHERE id=? AND tenant_id=? AND workspace_id=? AND namespace=?
                              AND revision=? AND status=?
                            """,
                            (
                                *values[1:],
                                item_id,
                                workspace.tenant_id,
                                workspace.workspace_id,
                                workspace.namespace,
                                item.revision,
                                InboxStatus.PENDING.value,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise InboxRevisionConflictError(
                                "Inbox item was modified concurrently"
                            )
                        completed_item = completed_item.model_copy(
                            update={"revision": item.revision + 1}
                        )
                    elif not (
                        item.status == final_status
                        and item.resolved_type == resolved_type
                        and item.resolved_target_id == claim.target_id
                    ):
                        raise InboxResolutionClaimConflictError(
                            "Inbox item was completed by another resolution"
                        )
                    else:
                        completed_item = item

                    if claim.state != InboxResolutionClaimState.COMPLETED:
                        cursor = conn.execute(
                            """
                            UPDATE inbox_resolution_claims
                            SET state=?, updated_at=?, revision=?
                            WHERE inbox_item_id=? AND tenant_id=? AND workspace_id=?
                              AND namespace=? AND revision=?
                            """,
                            (
                                InboxResolutionClaimState.COMPLETED.value,
                                now.isoformat(),
                                claim.revision + 1,
                                item_id,
                                workspace.tenant_id,
                                workspace.workspace_id,
                                workspace.namespace,
                                claim.revision,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise InboxResolutionClaimConflictError(
                                "Inbox claim was modified concurrently"
                            )
                        claim = claim.model_copy(
                            update={
                                "state": InboxResolutionClaimState.COMPLETED,
                                "updated_at": now,
                                "revision": claim.revision + 1,
                            }
                        )
            self._last_error = None
            return (
                InboxItem.model_validate(completed_item.model_dump()),
                InboxResolutionClaim.model_validate(claim.model_dump()),
            )
        except (
            InboxItemNotFoundError,
            InboxResolutionClaimConflictError,
            InboxResolutionClaimNotFoundError,
            InboxRevisionConflictError,
            InboxWorkspaceMismatchError,
        ):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox resolution completion failed") from exc

    async def update(self, item: InboxItem, *, expected_revision: int) -> InboxItem:
        updated = item.model_copy(update={"revision": expected_revision + 1})
        values = self._values(updated)
        assignments = (
            "tenant_id=?, workspace_id=?, namespace=?, content=?, source=?, status=?, "
            "suggested_type=?, created_at=?, updated_at=?, resolved_at=?, resolved_type=?, "
            "resolved_target_id=?, metadata=?, revision=?"
        )
        workspace = canonical_workspace(item.workspace_key)
        params = (
            *values[1:],
            item.id,
            expected_revision,
            workspace.tenant_id,
            workspace.workspace_id,
            workspace.namespace,
        )
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    cursor = conn.execute(
                        f"UPDATE inbox_items SET {assignments} "
                        "WHERE id=? AND revision=? "
                        "AND tenant_id=? AND workspace_id=? AND namespace=?",
                        params,
                    )
                    if cursor.rowcount != 1:
                        exists = conn.execute(
                            "SELECT 1 FROM inbox_items WHERE id=?", (item.id,)
                        ).fetchone()
                        if exists is None:
                            raise InboxItemNotFoundError("Inbox item not found")
                        raise InboxRevisionConflictError("Inbox item was modified concurrently")
            self._last_error = None
            return updated
        except (InboxItemNotFoundError, InboxRevisionConflictError):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise InboxRepositoryError("Inbox item update failed") from exc

    async def resolve(self, item: InboxItem, *, expected_revision: int) -> InboxItem:
        return await self.update(item, expected_revision=expected_revision)

    async def dismiss(self, item: InboxItem, *, expected_revision: int) -> InboxItem:
        return await self.update(item, expected_revision=expected_revision)

    async def health_check(self) -> dict[str, object]:
        if not self._initialized:
            return {"status": RuntimeStatus.NOT_INITIALIZED.value}
        if self._manager.health_check(self.LOGICAL_NAME):
            self._last_error = None
            return {"status": RuntimeStatus.OK.value}
        self._last_error = "health_check_failed"
        return {"status": RuntimeStatus.FAILED.value}

    async def close(self) -> None:
        self._initialized = False
