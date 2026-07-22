"""SQLite persistence for canonical Waiting-For snapshots and events."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import DatabaseManager
from core.database.connection import transaction
from core.errors import RuntimeStatus
from core.waiting_for.exceptions import (
    WaitingForConflictError,
    WaitingForNotFoundError,
    WaitingForPersistenceError,
    WaitingForWorkspaceMismatchError,
)
from core.waiting_for.models import (
    WaitingFor,
    WaitingForEvent,
    WaitingForEventType,
    WaitingForEventPage,
    WaitingForPage,
    WaitingForStatus,
    WaitingForView,
    canonical_workspace,
)
from core.workspace.models import WorkspaceKey


class SQLiteWaitingForRepository:
    """Borrow one DatabaseManager-owned connection for all repository work."""

    LOGICAL_NAME = "waiting_for"

    @staticmethod
    def _workspace_identity(workspace_key: WorkspaceKey) -> tuple[str, str, str]:
        workspace = canonical_workspace(workspace_key)
        return workspace.tenant_id, workspace.workspace_id, workspace.namespace

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
                        CREATE TABLE IF NOT EXISTS waiting_for_items (
                            id TEXT PRIMARY KEY,
                            tenant_id TEXT NOT NULL,
                            workspace_id TEXT NOT NULL,
                            namespace TEXT NOT NULL,
                            subject TEXT NOT NULL,
                            waiting_on TEXT NOT NULL,
                            context TEXT NOT NULL,
                            status TEXT NOT NULL,
                            expected_by TEXT,
                            next_review_at TEXT,
                            timezone TEXT NOT NULL,
                            linked_user_task_id TEXT,
                            linked_reminder_id TEXT,
                            source TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            resolved_at TEXT,
                            cancelled_at TEXT,
                            resolution_note TEXT NOT NULL,
                            metadata TEXT NOT NULL,
                            revision INTEGER NOT NULL
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_waiting_for_workspace_status_review
                        ON waiting_for_items(
                            tenant_id, workspace_id, namespace, status,
                            next_review_at, expected_by, id
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_waiting_for_linked_task
                        ON waiting_for_items(linked_user_task_id)
                        WHERE linked_user_task_id IS NOT NULL
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_waiting_for_linked_reminder
                        ON waiting_for_items(linked_reminder_id)
                        WHERE linked_reminder_id IS NOT NULL
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS waiting_for_events (
                            id TEXT PRIMARY KEY,
                            waiting_for_id TEXT NOT NULL,
                            tenant_id TEXT NOT NULL,
                            workspace_id TEXT NOT NULL,
                            namespace TEXT NOT NULL,
                            sequence INTEGER NOT NULL,
                            event_type TEXT NOT NULL,
                            occurred_at TEXT NOT NULL,
                            note TEXT NOT NULL,
                            source TEXT NOT NULL,
                            trace_id TEXT NOT NULL,
                            metadata TEXT NOT NULL,
                            UNIQUE(waiting_for_id, sequence)
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_waiting_for_events_workspace_item_sequence
                        ON waiting_for_events(
                            tenant_id, workspace_id, namespace,
                            waiting_for_id, sequence
                        )
                        """
                    )
            self._initialized = True
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise WaitingForPersistenceError(
                "Waiting-For repository initialization failed"
            ) from exc

    @staticmethod
    def _item_values(item: WaitingFor) -> tuple[object, ...]:
        data = item.model_dump(mode="json")
        workspace = canonical_workspace(item.workspace_key)
        return (
            data["id"],
            workspace.tenant_id,
            workspace.workspace_id,
            workspace.namespace,
            data["subject"],
            data["waiting_on"],
            data["context"],
            data["status"],
            data["expected_by"],
            data["next_review_at"],
            data["timezone"],
            data["linked_user_task_id"],
            data["linked_reminder_id"],
            data["source"],
            data["created_at"],
            data["updated_at"],
            data["resolved_at"],
            data["cancelled_at"],
            data["resolution_note"],
            json.dumps(data["metadata"], ensure_ascii=False, sort_keys=True),
            data["revision"],
        )

    @staticmethod
    def _event_values(event: WaitingForEvent) -> tuple[object, ...]:
        data = event.model_dump(mode="json")
        workspace = canonical_workspace(event.workspace_key)
        return (
            data["id"],
            data["waiting_for_id"],
            workspace.tenant_id,
            workspace.workspace_id,
            workspace.namespace,
            data["sequence"],
            data["event_type"],
            data["occurred_at"],
            data["note"],
            data["source"],
            data["trace_id"],
            json.dumps(data["metadata"], ensure_ascii=False, sort_keys=True),
        )

    @staticmethod
    def _item(row: sqlite3.Row) -> WaitingFor:
        data = dict(row)
        data["workspace_key"] = WorkspaceKey(
            tenant_id=data.pop("tenant_id"),
            workspace_id=data.pop("workspace_id"),
            namespace=data.pop("namespace"),
        )
        data["metadata"] = json.loads(data["metadata"])
        return WaitingFor.model_validate(data)

    @staticmethod
    def _event(row: sqlite3.Row) -> WaitingForEvent:
        data = dict(row)
        data["workspace_key"] = WorkspaceKey(
            tenant_id=data.pop("tenant_id"),
            workspace_id=data.pop("workspace_id"),
            namespace=data.pop("namespace"),
        )
        data["metadata"] = json.loads(data["metadata"])
        return WaitingForEvent.model_validate(data)

    @staticmethod
    def _scoped_row(
        conn: sqlite3.Connection, workspace: WorkspaceKey, waiting_for_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM waiting_for_items
            WHERE id=? AND tenant_id=? AND workspace_id=? AND namespace=?
            """,
            (
                waiting_for_id,
                workspace.tenant_id,
                workspace.workspace_id,
                workspace.namespace,
            ),
        ).fetchone()
        if row is not None:
            return row
        exists = conn.execute(
            "SELECT 1 FROM waiting_for_items WHERE id=?", (waiting_for_id,)
        ).fetchone()
        if exists is not None:
            raise WaitingForWorkspaceMismatchError(
                "Waiting-For item belongs to another workspace"
            )
        raise WaitingForNotFoundError("Waiting-For item not found")

    def _insert_item(self, conn: sqlite3.Connection, item: WaitingFor) -> None:
        conn.execute(
            "INSERT INTO waiting_for_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            self._item_values(item),
        )

    def _insert_event(self, conn: sqlite3.Connection, event: WaitingForEvent) -> None:
        conn.execute(
            "INSERT INTO waiting_for_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            self._event_values(event),
        )

    async def create(
        self, item: WaitingFor, event: WaitingForEvent
    ) -> tuple[WaitingFor, WaitingForEvent]:
        if (
            self._workspace_identity(item.workspace_key)
            != self._workspace_identity(event.workspace_key)
            or event.waiting_for_id != item.id
            or item.revision != 1
            or event.sequence != item.revision
            or event.event_type != WaitingForEventType.CREATED
        ):
            raise WaitingForConflictError("Created event does not match snapshot")
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute("BEGIN IMMEDIATE")
                    self._insert_item(conn, item)
                    self._insert_event(conn, event)
            self._last_error = None
            return item, event
        except sqlite3.IntegrityError as exc:
            raise WaitingForConflictError("Waiting-For item already exists") from exc
        except WaitingForConflictError:
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise WaitingForPersistenceError("Waiting-For create failed") from exc

    async def get(
        self, workspace_key: WorkspaceKey, waiting_for_id: str
    ) -> WaitingFor:
        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                row = self._scoped_row(conn, workspace, waiting_for_id)
            self._last_error = None
            return self._item(row)
        except (
            WaitingForNotFoundError,
            WaitingForWorkspaceMismatchError,
        ):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise WaitingForPersistenceError("Waiting-For query failed") from exc

    async def list(
        self,
        workspace_key: WorkspaceKey,
        *,
        view: WaitingForView,
        now: datetime,
        limit: int,
        offset: int,
    ) -> WaitingForPage:
        workspace = canonical_workspace(workspace_key)
        clauses = ["tenant_id=?", "workspace_id=?", "namespace=?"]
        params: list[object] = [
            workspace.tenant_id,
            workspace.workspace_id,
            workspace.namespace,
        ]
        now_value = now.isoformat()
        if view == WaitingForView.OPEN:
            clauses.append("status=?")
            params.append(WaitingForStatus.OPEN.value)
        elif view == WaitingForView.DUE:
            clauses.extend(("status=?", "next_review_at IS NOT NULL", "next_review_at<=?"))
            params.extend((WaitingForStatus.OPEN.value, now_value))
        elif view == WaitingForView.OVERDUE:
            clauses.extend(("status=?", "expected_by IS NOT NULL", "expected_by<?"))
            params.extend((WaitingForStatus.OPEN.value, now_value))
        elif view == WaitingForView.ATTENTION:
            clauses.extend(
                (
                    "status=?",
                    "((next_review_at IS NOT NULL AND next_review_at<=?) "
                    "OR (expected_by IS NOT NULL AND expected_by<?))",
                )
            )
            params.extend((WaitingForStatus.OPEN.value, now_value, now_value))
        elif view == WaitingForView.RESOLVED:
            clauses.append("status=?")
            params.append(WaitingForStatus.RESOLVED.value)
        elif view == WaitingForView.CANCELLED:
            clauses.append("status=?")
            params.append(WaitingForStatus.CANCELLED.value)

        order = """
            CASE WHEN next_review_at IS NULL THEN 1 ELSE 0 END,
            next_review_at,
            CASE WHEN expected_by IS NULL THEN 1 ELSE 0 END,
            expected_by,
            created_at,
            id
        """
        params.extend((limit + 1, offset))
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                rows = conn.execute(
                    f"""
                    SELECT * FROM waiting_for_items
                    WHERE {' AND '.join(clauses)}
                    ORDER BY {order}
                    LIMIT ? OFFSET ?
                    """,
                    params,
                ).fetchall()
            self._last_error = None
            return WaitingForPage(
                items=tuple(self._item(row) for row in rows[:limit]),
                view=view,
                limit=limit,
                offset=offset,
                has_more=len(rows) > limit,
                generated_at=now,
            )
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise WaitingForPersistenceError("Waiting-For list failed") from exc

    async def list_events(
        self,
        workspace_key: WorkspaceKey,
        waiting_for_id: str,
        *,
        limit: int,
        offset: int,
    ) -> WaitingForEventPage:
        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                self._scoped_row(conn, workspace, waiting_for_id)
                rows = conn.execute(
                    """
                    SELECT * FROM waiting_for_events
                    WHERE waiting_for_id=? AND tenant_id=?
                      AND workspace_id=? AND namespace=?
                    ORDER BY sequence ASC
                    LIMIT ? OFFSET ?
                    """,
                    (
                        waiting_for_id,
                        workspace.tenant_id,
                        workspace.workspace_id,
                        workspace.namespace,
                        limit + 1,
                        offset,
                    ),
                ).fetchall()
            self._last_error = None
            return WaitingForEventPage(
                items=tuple(self._event(row) for row in rows[:limit]),
                limit=limit,
                offset=offset,
                has_more=len(rows) > limit,
            )
        except (
            WaitingForNotFoundError,
            WaitingForWorkspaceMismatchError,
        ):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise WaitingForPersistenceError("Waiting-For event list failed") from exc

    async def mutate(
        self,
        workspace_key: WorkspaceKey,
        *,
        updated: WaitingFor,
        event: WaitingForEvent,
        expected_revision: int,
    ) -> tuple[WaitingFor, WaitingForEvent]:
        workspace = canonical_workspace(workspace_key)
        request_identity = self._workspace_identity(workspace)
        if (
            request_identity != self._workspace_identity(updated.workspace_key)
            or request_identity != self._workspace_identity(event.workspace_key)
        ):
            raise WaitingForConflictError("Mutation workspace does not match request")
        if updated.revision != expected_revision + 1:
            raise WaitingForConflictError("Snapshot revision is invalid")
        if event.waiting_for_id != updated.id or event.sequence != updated.revision:
            raise WaitingForConflictError("Mutation event does not match snapshot")
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute("BEGIN IMMEDIATE")
                    current = self._item(self._scoped_row(conn, workspace, updated.id))
                    if self._workspace_identity(current.workspace_key) != request_identity:
                        raise WaitingForConflictError("Stored workspace does not match request")
                    if current.revision != expected_revision:
                        raise WaitingForConflictError("Waiting-For revision conflict")
                    values = self._item_values(updated)
                    cursor = conn.execute(
                        """
                        UPDATE waiting_for_items SET
                            tenant_id=?, workspace_id=?, namespace=?, subject=?,
                            waiting_on=?, context=?, status=?, expected_by=?,
                            next_review_at=?, timezone=?, linked_user_task_id=?,
                            linked_reminder_id=?, source=?, created_at=?, updated_at=?,
                            resolved_at=?, cancelled_at=?, resolution_note=?, metadata=?,
                            revision=?
                        WHERE id=? AND tenant_id=? AND workspace_id=? AND namespace=?
                          AND revision=?
                        """,
                        (*values[1:], values[0], *values[1:4], expected_revision),
                    )
                    if cursor.rowcount != 1:
                        raise WaitingForConflictError("Waiting-For revision conflict")
                    self._insert_event(conn, event)
            self._last_error = None
            return updated, event
        except (
            WaitingForConflictError,
            WaitingForNotFoundError,
            WaitingForWorkspaceMismatchError,
        ):
            raise
        except sqlite3.IntegrityError as exc:
            raise WaitingForConflictError("Waiting-For event conflict") from exc
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise WaitingForPersistenceError("Waiting-For mutation failed") from exc

    async def health_check(self) -> dict[str, object]:
        if not self._initialized:
            return {"status": RuntimeStatus.NOT_INITIALIZED.value}
        if self._manager.health_check(self.LOGICAL_NAME):
            return {"status": RuntimeStatus.OK.value}
        return {
            "status": RuntimeStatus.FAILED.value,
            "failure": self._last_error or "connection_unavailable",
        }

    async def close(self) -> None:
        self._manager.close(self.LOGICAL_NAME)
        self._initialized = False
