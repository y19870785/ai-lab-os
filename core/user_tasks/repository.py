"""SQLite UserTask repository using DatabaseManager-owned connections."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.database import DatabaseManager
from core.database.connection import transaction
from core.errors import RuntimeStatus
from core.user_tasks.exceptions import (
    UserTaskConflictError,
    UserTaskNotFoundError,
    UserTaskPersistenceError,
)
from core.user_tasks.models import UserTask, UserTaskQuery, utc_now


class SQLiteUserTaskRepository:
    LOGICAL_NAME = "user_tasks"

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

    async def create(self, task: UserTask) -> UserTask:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
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

    async def get(self, task_id: str) -> UserTask:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                row = conn.execute("SELECT * FROM user_tasks WHERE id = ?", (task_id,)).fetchone()
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise UserTaskPersistenceError("UserTask query failed") from exc
        if row is None:
            raise UserTaskNotFoundError("UserTask not found")
        return self._task(row)

    async def list(self, query: UserTaskQuery | None = None) -> list[UserTask]:
        query = query or UserTaskQuery()
        clauses: list[str] = []
        params: list[object] = []
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
        if query.overdue is not None:
            clauses.append("status = 'active'")
            clauses.append("due_at IS NOT NULL")
            clauses.append("due_at < ?" if query.overdue else "due_at >= ?")
            params.append(utc_now().isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM user_tasks {where} "
            "ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 ELSE 3 END, due_at IS NULL, due_at, created_at, id LIMIT ?"
        )
        params.append(query.limit)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                rows = conn.execute(sql, params).fetchall()
            self._last_error = None
            return [self._task(row) for row in rows]
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise UserTaskPersistenceError("UserTask list failed") from exc

    async def update(self, task: UserTask, expected_revision: int) -> UserTask:
        updated = task.model_copy(update={"revision": expected_revision + 1})
        values = self._values(updated)
        assignments = (
            "title=?, description=?, status=?, priority=?, due_at=?, timezone=?, "
            "created_at=?, updated_at=?, completed_at=?, cancelled_at=?, source=?, "
            "session_id=?, agent_id=?, trace_id=?, metadata=?, legacy_source_id=?, revision=?"
        )
        params = (*values[1:], task.id, expected_revision)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    cursor = conn.execute(
                        f"UPDATE user_tasks SET {assignments} WHERE id=? AND revision=?",
                        params,
                    )
                    if cursor.rowcount != 1:
                        exists = conn.execute("SELECT 1 FROM user_tasks WHERE id=?", (task.id,)).fetchone()
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
