"""SQLite Reminder repository using DatabaseManager-owned connections."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.database import DatabaseManager
from core.database.connection import transaction
from core.errors import ErrorCategory, FailureInfo, RuntimeStatus
from core.reminders.exceptions import (
    ReminderConflictError,
    ReminderNotFoundError,
    ReminderPersistenceError,
)
from core.reminders.models import (
    Reminder,
    ReminderOccurrence,
    ReminderOccurrenceStatus,
    ReminderStatus,
    utc_now,
)


_SAFE_FAILURE_DETAILS = {"reminder_id", "recovery_state", "attempt", "job_id"}


def _failure_json(failure: FailureInfo | None) -> str | None:
    if failure is None:
        return None
    return json.dumps({
        "code": failure.code,
        "category": failure.category.value,
        "component": failure.component,
        "operation": failure.operation,
        "retryable": failure.retryable,
        "trace_id": failure.trace_id,
        "details": {
            key: value for key, value in failure.details.items()
            if key in _SAFE_FAILURE_DETAILS
        },
    })


def _failure(value: str | None) -> FailureInfo | None:
    if not value:
        return None
    raw = json.loads(value)
    return FailureInfo(
        code=raw["code"],
        category=ErrorCategory(raw["category"]),
        message="Reminder operation failed",
        component=raw["component"],
        operation=raw["operation"],
        retryable=bool(raw.get("retryable", False)),
        trace_id=str(raw.get("trace_id", "")),
        details=raw.get("details") or {},
    )


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("persisted reminder datetime is naive")
    return parsed.astimezone(timezone.utc)


class SQLiteReminderRepository:
    LOGICAL_NAME = "reminders"

    def __init__(self, database_manager: DatabaseManager, db_path: str | Path) -> None:
        self._manager = database_manager
        self._path = Path(db_path)
        self._initialized = False
        self._last_error: str | None = None
        self._observability_error: str | None = None

    async def initialize(self) -> None:
        if self._initialized:
            return
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS reminders (
                            id TEXT PRIMARY KEY,
                            user_task_id TEXT NOT NULL,
                            remind_at TEXT NOT NULL,
                            timezone TEXT NOT NULL,
                            status TEXT NOT NULL,
                            scheduler_job_id TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            cancelled_at TEXT,
                            last_failure TEXT,
                            trace_id TEXT NOT NULL DEFAULT '',
                            metadata TEXT NOT NULL DEFAULT '{}',
                            revision INTEGER NOT NULL DEFAULT 1
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS reminder_occurrences (
                            id TEXT PRIMARY KEY,
                            reminder_id TEXT NOT NULL,
                            user_task_id TEXT NOT NULL,
                            scheduled_at TEXT NOT NULL,
                            triggered_at TEXT,
                            status TEXT NOT NULL,
                            trace_id TEXT NOT NULL DEFAULT '',
                            failure TEXT,
                            idempotency_key TEXT NOT NULL UNIQUE,
                            attempt INTEGER NOT NULL DEFAULT 1,
                            UNIQUE(reminder_id, scheduled_at),
                            FOREIGN KEY(reminder_id) REFERENCES reminders(id)
                        )
                        """
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_reminders_task ON reminders(user_task_id, status)"
                    )
            self._initialized = True
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder repository initialization failed") from exc

    async def create(self, reminder: Reminder) -> Reminder:
        try:
            values = self._values(reminder)
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute(
                        """
                        INSERT INTO reminders (
                            id, user_task_id, remind_at, timezone, status,
                            scheduler_job_id, created_at, updated_at, cancelled_at,
                            last_failure, trace_id, metadata, revision
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
            self._last_error = None
            return reminder
        except sqlite3.IntegrityError as exc:
            raise ReminderConflictError("Reminder already exists") from exc
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder create failed") from exc

    async def get(self, reminder_id: str) -> Reminder:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                row = conn.execute(
                    "SELECT * FROM reminders WHERE id=?", (reminder_id,)
                ).fetchone()
            reminder = self._reminder(row) if row else None
            self._last_error = None
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder query failed") from exc
        if reminder is None:
            raise ReminderNotFoundError("Reminder not found")
        return reminder

    async def list_for_task(self, task_id: str) -> list[Reminder]:
        return await self._list("user_task_id=?", (task_id,))

    async def list_by_statuses(self, statuses: set[ReminderStatus]) -> list[Reminder]:
        if not statuses:
            return []
        values = tuple(status.value for status in statuses)
        placeholders = ",".join("?" for _ in values)
        return await self._list(f"status IN ({placeholders})", values)

    async def list_page(
        self,
        *,
        remind_from: datetime | None = None,
        remind_to: datetime | None = None,
        limit: int,
        offset: int,
    ) -> list[Reminder]:
        clauses: list[str] = []
        params: list[object] = []
        if remind_from is not None:
            clauses.append("remind_at >= ?")
            params.append(remind_from.astimezone(timezone.utc).isoformat())
        if remind_to is not None:
            clauses.append("remind_at < ?")
            params.append(remind_to.astimezone(timezone.utc).isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                rows = conn.execute(
                    f"SELECT * FROM reminders {where} "
                    "ORDER BY remind_at ASC, id ASC LIMIT ? OFFSET ?",
                    (*params, limit, offset),
                ).fetchall()
            result = [self._reminder(row) for row in rows]
            self._last_error = None
            return result
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder page query failed") from exc

    async def _list(self, where: str, params: tuple[object, ...]) -> list[Reminder]:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                rows = conn.execute(
                    f"SELECT * FROM reminders WHERE {where} ORDER BY created_at, id",
                    params,
                ).fetchall()
            result = [self._reminder(row) for row in rows]
            self._last_error = None
            return result
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder list failed") from exc

    async def update(self, reminder: Reminder, expected_revision: int) -> Reminder:
        updated = reminder.model_copy(update={
            "revision": expected_revision + 1,
            "updated_at": utc_now(),
        })
        values = self._values(updated)
        assignments = (
            "user_task_id=?, remind_at=?, timezone=?, status=?, scheduler_job_id=?, "
            "created_at=?, updated_at=?, cancelled_at=?, last_failure=?, trace_id=?, "
            "metadata=?, revision=?"
        )
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    cursor = conn.execute(
                        f"UPDATE reminders SET {assignments} WHERE id=? AND revision=?",
                        (*values[1:], reminder.id, expected_revision),
                    )
                    if cursor.rowcount != 1:
                        exists = conn.execute(
                            "SELECT 1 FROM reminders WHERE id=?", (reminder.id,)
                        ).fetchone()
                        if exists is None:
                            raise ReminderNotFoundError("Reminder not found")
                        raise ReminderConflictError("Reminder was modified concurrently")
            self._last_error = None
            return updated
        except (ReminderNotFoundError, ReminderConflictError):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder update failed") from exc

    async def trigger(
        self, reminder_id: str, scheduled_at: datetime, trace_id: str
    ) -> tuple[Reminder, ReminderOccurrence, bool]:
        scheduled = scheduled_at.astimezone(timezone.utc).isoformat()
        key = f"{reminder_id}:{scheduled}"
        now = utc_now()
        occurrence_id = "occ_" + __import__("uuid").uuid4().hex
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    reminder_row = conn.execute(
                        "SELECT * FROM reminders WHERE id=?", (reminder_id,)
                    ).fetchone()
                    if reminder_row is None:
                        raise ReminderNotFoundError("Reminder not found")
                    reminder = self._reminder(reminder_row)
                    if reminder.status in {
                        ReminderStatus.CANCELLED,
                        ReminderStatus.PENDING_CANCEL,
                    }:
                        raise ReminderConflictError("Cancelled Reminder cannot trigger")
                    if reminder.status == ReminderStatus.TRIGGERED:
                        row = conn.execute(
                            "SELECT * FROM reminder_occurrences WHERE idempotency_key=?",
                            (key,),
                        ).fetchone()
                        if row is None or row["status"] != "triggered":
                            raise ReminderConflictError(
                                "Triggered Reminder has no matching occurrence"
                            )
                        return reminder, self._occurrence(row), True
                    if reminder.status not in {
                        ReminderStatus.SCHEDULED,
                        ReminderStatus.FAILED,
                    }:
                        raise ReminderConflictError(
                            "Reminder transition prevents this trigger"
                        )
                    if reminder.remind_at != scheduled_at.astimezone(timezone.utc):
                        raise ReminderConflictError(
                            "Reminder schedule changed before trigger"
                        )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO reminder_occurrences (
                            id, reminder_id, user_task_id, scheduled_at, status,
                            trace_id, idempotency_key, attempt
                        ) VALUES (?, ?, ?, ?, 'processing', ?, ?, 1)
                        """,
                        (
                            occurrence_id,
                            reminder.id,
                            reminder.user_task_id,
                            scheduled,
                            trace_id,
                            key,
                        ),
                    )
                    row = conn.execute(
                        "SELECT * FROM reminder_occurrences WHERE idempotency_key=?", (key,)
                    ).fetchone()
                    existing = row["status"] == ReminderOccurrenceStatus.TRIGGERED.value
                    if not existing:
                        conn.execute(
                            """
                            UPDATE reminder_occurrences SET
                                status='triggered', triggered_at=?, trace_id=?,
                                failure=NULL, attempt=attempt+CASE WHEN status='processing' THEN 0 ELSE 1 END
                            WHERE idempotency_key=?
                            """,
                            (now.isoformat(), trace_id, key),
                        )
                    cursor = conn.execute(
                        """
                        UPDATE reminders SET status='triggered', updated_at=?,
                            last_failure=NULL, trace_id=?, revision=revision+1
                        WHERE id=? AND status NOT IN ('cancelled', 'pending_cancel')
                        """,
                        (now.isoformat(), trace_id, reminder.id),
                    )
                    if cursor.rowcount != 1:
                        raise ReminderConflictError("Reminder was cancelled while triggering")
                    final_reminder = self._reminder(conn.execute(
                        "SELECT * FROM reminders WHERE id=?", (reminder.id,)
                    ).fetchone())
                    final_occurrence = self._occurrence(conn.execute(
                        "SELECT * FROM reminder_occurrences WHERE idempotency_key=?", (key,)
                    ).fetchone())
            self._last_error = None
            return final_reminder, final_occurrence, existing
        except (ReminderNotFoundError, ReminderConflictError):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder trigger failed") from exc

    async def list_occurrences(self, reminder_id: str) -> list[ReminderOccurrence]:
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM reminder_occurrences
                    WHERE reminder_id=? ORDER BY scheduled_at, id
                    """,
                    (reminder_id,),
                ).fetchall()
            result = [self._occurrence(row) for row in rows]
            self._last_error = None
            return result
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder occurrence query failed") from exc

    async def record_trigger_failure(
        self,
        reminder_id: str,
        scheduled_at: datetime,
        trace_id: str,
        failure: FailureInfo,
    ) -> None:
        scheduled = scheduled_at.astimezone(timezone.utc).isoformat()
        key = f"{reminder_id}:{scheduled}"
        now = utc_now().isoformat()
        occurrence_id = "occ_" + __import__("uuid").uuid4().hex
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    reminder_row = conn.execute(
                        "SELECT * FROM reminders WHERE id=?", (reminder_id,)
                    ).fetchone()
                    if reminder_row is None:
                        raise ReminderNotFoundError("Reminder not found")
                    reminder = self._reminder(reminder_row)
                    inserted = conn.execute(
                        """
                        INSERT OR IGNORE INTO reminder_occurrences (
                            id, reminder_id, user_task_id, scheduled_at, status,
                            trace_id, failure, idempotency_key, attempt
                        ) VALUES (?, ?, ?, ?, 'failed', ?, ?, ?, 1)
                        """,
                        (
                            occurrence_id,
                            reminder.id,
                            reminder.user_task_id,
                            scheduled,
                            trace_id,
                            _failure_json(failure),
                            key,
                        ),
                    )
                    if inserted.rowcount == 0:
                        conn.execute(
                            """
                            UPDATE reminder_occurrences SET status='failed', failure=?,
                                trace_id=?, attempt=attempt+1
                            WHERE idempotency_key=? AND status!='triggered'
                            """,
                            (_failure_json(failure), trace_id, key),
                        )
                    conn.execute(
                        """
                        UPDATE reminders SET status='failed', last_failure=?,
                            trace_id=?, updated_at=?, revision=revision+1
                        WHERE id=? AND status NOT IN (
                            'triggered', 'cancelled', 'pending_cancel'
                        )
                        """,
                        (_failure_json(failure), trace_id, now, reminder_id),
                    )
            self._last_error = None
        except (ReminderNotFoundError, ReminderConflictError):
            raise
        except Exception as exc:
            self._last_error = exc.__class__.__name__
            raise ReminderPersistenceError("Reminder trigger failure save failed") from exc

    def mark_observability_degraded(self, reason: str) -> None:
        self._observability_error = reason[:100]

    def clear_observability_degraded(self) -> None:
        self._observability_error = None

    async def health_check(self) -> dict[str, object]:
        if not self._initialized:
            return {"status": RuntimeStatus.NOT_INITIALIZED.value}
        if not self._manager.health_check(self.LOGICAL_NAME):
            self._last_error = "health_check_failed"
            return {"status": RuntimeStatus.FAILED.value}
        if self._last_error or self._observability_error:
            return {
                "status": RuntimeStatus.DEGRADED.value,
                "last_error": self._last_error or self._observability_error,
            }
        return {"status": RuntimeStatus.OK.value}

    async def close(self) -> None:
        self._initialized = False

    @staticmethod
    def _values(reminder: Reminder) -> tuple[object, ...]:
        data = reminder.model_dump(mode="python")
        return (
            reminder.id,
            reminder.user_task_id,
            reminder.remind_at.isoformat(),
            reminder.timezone,
            reminder.status.value,
            reminder.scheduler_job_id,
            reminder.created_at.isoformat(),
            reminder.updated_at.isoformat(),
            reminder.cancelled_at.isoformat() if reminder.cancelled_at else None,
            _failure_json(reminder.last_failure),
            reminder.trace_id,
            json.dumps(data["metadata"], ensure_ascii=True),
            reminder.revision,
        )

    @staticmethod
    def _reminder(row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=row["id"],
            user_task_id=row["user_task_id"],
            remind_at=_dt(row["remind_at"]),
            timezone=row["timezone"],
            status=ReminderStatus(row["status"]),
            scheduler_job_id=row["scheduler_job_id"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
            cancelled_at=_dt(row["cancelled_at"]),
            last_failure=_failure(row["last_failure"]),
            trace_id=row["trace_id"] or "",
            metadata=json.loads(row["metadata"] or "{}"),
            revision=row["revision"],
        )

    @staticmethod
    def _occurrence(row: sqlite3.Row) -> ReminderOccurrence:
        return ReminderOccurrence(
            id=row["id"],
            reminder_id=row["reminder_id"],
            user_task_id=row["user_task_id"],
            scheduled_at=_dt(row["scheduled_at"]),
            triggered_at=_dt(row["triggered_at"]),
            status=ReminderOccurrenceStatus(row["status"]),
            trace_id=row["trace_id"] or "",
            failure=_failure(row["failure"]),
            idempotency_key=row["idempotency_key"],
            attempt=row["attempt"],
        )
