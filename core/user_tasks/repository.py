"""SQLite UserTask repository using DatabaseManager-owned connections."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import DatabaseManager
from core.database.connection import transaction
from core.errors import RuntimeStatus
from core.user_tasks.exceptions import (
    UserTaskConflictError,
    UserTaskNotFoundError,
    UserTaskPersistenceError,
)
from core.user_tasks.models import UserTask, UserTaskQuery
from core.user_tasks.workspace import workspace_identity
from core.workspace.models import WorkspaceKey


class SQLiteUserTaskRepository:
    LOGICAL_NAME = "user_tasks"
    _COMPLETE_WORKSPACE_SQL = """
        CASE
            WHEN json_valid(metadata) = 1 THEN
                CASE
                    WHEN json_type(metadata) = 'object'
                     AND json_type(metadata, '$.workspace') = 'object'
                     AND json_type(metadata, '$.workspace.tenant_id') = 'text'
                     AND length(trim(json_extract(
                         metadata, '$.workspace.tenant_id'
                     ))) > 0
                     AND json_type(metadata, '$.workspace.workspace_id') = 'text'
                     AND length(trim(json_extract(
                         metadata, '$.workspace.workspace_id'
                     ))) > 0
                     AND json_type(metadata, '$.workspace.namespace') = 'text'
                     AND length(trim(json_extract(
                         metadata, '$.workspace.namespace'
                     ))) > 0
                    THEN 1
                    ELSE 0
                END
            ELSE 0
        END
    """

    def __init__(self, database_manager: DatabaseManager, db_path: str | Path) -> None:
        self._manager = database_manager
        self._path = self._manager.bind_path(self.LOGICAL_NAME, db_path)
        self._initialized = False
        self._last_error: str | None = None

    async def initialize(self) -> None:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_tasks (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        status TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        due_at TEXT,
                        timezone TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        completed_at TEXT,
                        cancelled_at TEXT,
                        source TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        trace_id TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        legacy_source_id TEXT UNIQUE,
                        revision INTEGER NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_status_due ON user_tasks(status, due_at)")
                conn.commit()
            self._initialized = True
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise UserTaskPersistenceError("UserTask repository initialization failed") from exc

    @staticmethod
    def _values(task: UserTask) -> tuple[object, ...]:
        data = task.model_dump(mode="json")
        return (
            data["id"], data["title"], data["description"], data["status"],
            data["priority"], data["due_at"], data["timezone"], data["created_at"],
            data["updated_at"], data["completed_at"], data["cancelled_at"],
            data["source"], data["session_id"], data["agent_id"], data["trace_id"],
            json.dumps(data["metadata"], ensure_ascii=False), data["legacy_source_id"],
            data["revision"],
        )

    @staticmethod
    def _task(row: sqlite3.Row) -> UserTask:
        data = dict(row)
        data["metadata"] = json.loads(data["metadata"])
        return UserTask.model_validate(data)

    @classmethod
    def _workspace_predicate(
        cls,
        workspace_key: WorkspaceKey,
    ) -> tuple[str, tuple[str, ...]]:
        tenant_id, workspace_id, namespace = workspace_identity(workspace_key)
        sql = f"""
            CASE
                WHEN ({cls._COMPLETE_WORKSPACE_SQL}) = 1 THEN
                    CASE
                        WHEN json_extract(
                            metadata, '$.workspace.tenant_id'
                        ) = ?
                         AND json_extract(
                            metadata, '$.workspace.workspace_id'
                        ) = ?
                         AND json_extract(
                            metadata, '$.workspace.namespace'
                        ) = ?
                        THEN 1
                        ELSE 0
                    END
                ELSE
                    CASE
                        WHEN ? = 'default'
                         AND ? = 'default'
                         AND ? = 'default'
                        THEN 1
                        ELSE 0
                    END
            END = 1
        """
        return sql, (
            tenant_id,
            workspace_id,
            namespace,
            tenant_id,
            workspace_id,
            namespace,
        )

    @staticmethod
    def _ensure_valid_metadata(
        conn: sqlite3.Connection,
        *,
        task_id: str | None = None,
    ) -> None:
        sql = "SELECT 1 FROM user_tasks WHERE json_valid(metadata) = 0"
        params: tuple[object, ...] = ()
        if task_id is not None:
            sql += " AND id = ?"
            params = (task_id,)
        if conn.execute(f"{sql} LIMIT 1", params).fetchone() is not None:
            raise UserTaskPersistenceError("UserTask persisted metadata is malformed")

    async def create(self, task: UserTask) -> UserTask:
        try:
            with (
                self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
                transaction(conn),
            ):
                conn.execute(
                    "INSERT INTO user_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    self._values(task),
                )
            self._last_error = None
            return task
        except sqlite3.IntegrityError as exc:
            raise UserTaskConflictError("UserTask already exists") from exc
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise UserTaskPersistenceError("UserTask create failed") from exc

    async def get(
        self,
        workspace_key: WorkspaceKey,
        task_id: str,
    ) -> UserTask:
        workspace_sql, workspace_params = self._workspace_predicate(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                self._ensure_valid_metadata(conn, task_id=task_id)
                row = conn.execute(
                    f"""
                    SELECT * FROM user_tasks
                    WHERE id = ? AND ({workspace_sql})
                    """,
                    (task_id, *workspace_params),
                ).fetchone()
            task = self._task(row) if row is not None else None
            self._last_error = None
        except UserTaskPersistenceError:
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise UserTaskPersistenceError("UserTask query failed") from exc
        if task is None:
            raise UserTaskNotFoundError("UserTask not found")
        return task

    async def list(
        self,
        workspace_key: WorkspaceKey,
        query: UserTaskQuery,
        *,
        as_of: datetime | None,
    ) -> list[UserTask]:
        workspace_sql, workspace_params = self._workspace_predicate(workspace_key)
        clauses: list[str] = [f"({workspace_sql})"]
        params: list[object] = list(workspace_params)
        for column, value in (("status", query.status), ("priority", query.priority)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value.value)
        if query.due_from is not None:
            clauses.append("due_at >= ?")
            params.append(query.due_from.isoformat())
        if query.due_to is not None:
            clauses.append("due_at <= ?")
            params.append(query.due_to.isoformat())
        if query.completed_from is not None:
            clauses.append("completed_at >= ?")
            params.append(query.completed_from.isoformat())
        if query.completed_to is not None:
            clauses.append("completed_at < ?")
            params.append(query.completed_to.isoformat())
        if query.cancelled_from is not None:
            clauses.append("cancelled_at >= ?")
            params.append(query.cancelled_from.isoformat())
        if query.cancelled_to is not None:
            clauses.append("cancelled_at < ?")
            params.append(query.cancelled_to.isoformat())
        if query.overdue is not None:
            if as_of is None:
                raise UserTaskPersistenceError(
                    "UserTask overdue query requires a resolved as_of"
                )
            clauses.append("status = 'active'")
            clauses.append("due_at IS NOT NULL")
            clauses.append("due_at < ?" if query.overdue else "due_at >= ?")
            params.append(as_of.isoformat())
        where = f"WHERE {' AND '.join(clauses)}"
        sql = (
            f"SELECT * FROM user_tasks {where} "
            "ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 ELSE 3 END, due_at IS NULL, due_at, created_at, id "
            "LIMIT ? OFFSET ?"
        )
        params.extend((query.limit, query.offset))
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                self._ensure_valid_metadata(conn)
                rows = conn.execute(sql, params).fetchall()
            self._last_error = None
            return [self._task(row) for row in rows]
        except UserTaskPersistenceError:
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise UserTaskPersistenceError("UserTask list failed") from exc

    async def update(
        self,
        workspace_key: WorkspaceKey,
        task: UserTask,
        expected_revision: int,
    ) -> UserTask:
        updated = task.model_copy(update={"revision": expected_revision + 1})
        values = self._values(updated)
        assignments = (
            "title=?, description=?, status=?, priority=?, due_at=?, timezone=?, "
            "created_at=?, updated_at=?, completed_at=?, cancelled_at=?, source=?, "
            "session_id=?, agent_id=?, trace_id=?, metadata=?, legacy_source_id=?, revision=?"
        )
        workspace_sql, workspace_params = self._workspace_predicate(workspace_key)
        params = (*values[1:], task.id, expected_revision, *workspace_params)
        try:
            with (
                self._manager.lease(self.LOGICAL_NAME, self._path) as conn,
                transaction(conn),
            ):
                self._ensure_valid_metadata(conn, task_id=task.id)
                cursor = conn.execute(
                    f"""
                    UPDATE user_tasks SET {assignments}
                    WHERE id=? AND revision=? AND ({workspace_sql})
                    """,
                    params,
                )
                if cursor.rowcount != 1:
                    exists = conn.execute(
                        f"""
                        SELECT 1 FROM user_tasks
                        WHERE id=? AND ({workspace_sql})
                        """,
                        (task.id, *workspace_params),
                    ).fetchone()
                    if exists is None:
                        raise UserTaskNotFoundError("UserTask not found")
                    raise UserTaskConflictError("UserTask was modified concurrently")
            self._last_error = None
            return updated
        except (UserTaskNotFoundError, UserTaskConflictError):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise UserTaskPersistenceError("UserTask update failed") from exc

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
