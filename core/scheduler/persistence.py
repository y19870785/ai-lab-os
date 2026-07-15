"""SQLite persistence and cross-runtime CAS claims for Scheduler jobs."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from core.errors import ErrorCategory, FailureInfo
from core.scheduler.exceptions import JobClaimLostError, SchedulerPersistenceError
from core.scheduler.models import (
    Job,
    JobInfo,
    JobRun,
    JobRunStatus,
    JobStatus,
    Trigger,
    TriggerType,
)


_FAILURE_DETAIL_KEYS = {
    "action_type",
    "attempt",
    "consecutive_failures",
    "job_id",
    "recovery_state",
    "reminder_id",
    "timeout_seconds",
}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scheduler datetimes must be timezone-aware")
    return value.astimezone(timezone.utc)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("persisted scheduler datetime is naive")
    return parsed.astimezone(timezone.utc)


def _failure_json(failure: FailureInfo | None) -> str | None:
    if failure is None:
        return None
    details = {
        key: value for key, value in failure.details.items() if key in _FAILURE_DETAIL_KEYS
    }
    return json.dumps(
        {
            "code": failure.code,
            "category": failure.category.value,
            "component": failure.component,
            "operation": failure.operation,
            "retryable": failure.retryable,
            "trace_id": failure.trace_id,
            "details": details,
        },
        ensure_ascii=True,
    )


def _failure(value: str | None) -> FailureInfo | None:
    if not value:
        return None
    raw = json.loads(value)
    return FailureInfo(
        code=raw["code"],
        category=ErrorCategory(raw["category"]),
        message="Scheduler operation failed",
        component=raw["component"],
        operation=raw["operation"],
        retryable=bool(raw.get("retryable", False)),
        trace_id=str(raw.get("trace_id", "")),
        details=raw.get("details") or {},
    )


class SchedulerPersistence:
    """Own one SQLite connection and serialize operations on that connection."""

    def __init__(self, db_path: str = "scheduler.db") -> None:
        self._db_path = str(Path(db_path))
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    async def initialize(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                self._conn = conn
                self._create_tables()
                self._migrate_jobs()
            except Exception:
                conn.close()
                self._conn = None
                raise

    async def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            self._conn.close()
            self._conn = None

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise SchedulerPersistenceError("Scheduler persistence is not initialized")
        return self._conn

    def _create_tables(self) -> None:
        conn = self._connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                version TEXT DEFAULT '1.0.0',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                trigger_type TEXT NOT NULL,
                cron_expression TEXT DEFAULT '',
                interval_seconds INTEGER DEFAULT 0,
                run_at TEXT,
                event_type TEXT DEFAULT '',
                trigger_timezone TEXT DEFAULT 'Asia/Shanghai',
                next_run_at TEXT,
                workflow_name TEXT DEFAULT '',
                workflow_variables TEXT DEFAULT '{}',
                status TEXT DEFAULT 'active',
                max_retries INTEGER DEFAULT 3,
                timeout INTEGER DEFAULT 300,
                max_concurrent INTEGER DEFAULT 1,
                retry_count INTEGER DEFAULT 0,
                run_count INTEGER DEFAULT 0,
                last_run_at TEXT,
                last_result TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                action_type TEXT NOT NULL DEFAULT 'workflow',
                action_payload TEXT NOT NULL DEFAULT '{}',
                claim_token TEXT,
                claim_expires_at TEXT,
                last_error TEXT,
                updated_at TEXT,
                revision INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_runs (
                run_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                claim_token TEXT NOT NULL,
                failure TEXT,
                trace_id TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(status, next_run_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_job_runs_job ON job_runs(job_id, attempt)")
        conn.commit()

    def _migrate_jobs(self) -> None:
        conn = self._connection()
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        additions = {
            "action_type": "TEXT NOT NULL DEFAULT 'workflow'",
            "action_payload": "TEXT NOT NULL DEFAULT '{}'",
            "claim_token": "TEXT",
            "claim_expires_at": "TEXT",
            "last_error": "TEXT",
            "updated_at": "TEXT",
            "revision": "INTEGER NOT NULL DEFAULT 1",
        }
        for name, definition in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
        conn.execute("UPDATE jobs SET action_type='workflow' WHERE action_type IS NULL OR action_type='' ")
        conn.execute("UPDATE jobs SET action_payload='{}' WHERE action_payload IS NULL")
        conn.execute("UPDATE jobs SET updated_at=created_at WHERE updated_at IS NULL")
        conn.execute("UPDATE jobs SET revision=1 WHERE revision IS NULL OR revision < 1")
        conn.commit()

    def _job_values(self, job: Job) -> dict[str, object]:
        return {
            "id": job.info.id,
            "name": job.info.name,
            "description": job.info.description,
            "version": job.info.version,
            "tags": json.dumps(job.info.tags, ensure_ascii=True),
            "metadata": json.dumps(job.info.metadata, ensure_ascii=True),
            "trigger_type": job.trigger.trigger_type.value,
            "cron_expression": job.trigger.cron_expression,
            "interval_seconds": job.trigger.interval_seconds,
            "run_at": _utc(job.trigger.run_at).isoformat() if job.trigger.run_at else None,
            "event_type": job.trigger.event_type,
            "trigger_timezone": job.trigger.timezone,
            "next_run_at": _utc(job.trigger.next_run_at).isoformat() if job.trigger.next_run_at else None,
            "workflow_name": job.workflow_name,
            "workflow_variables": json.dumps(job.workflow_variables, ensure_ascii=True),
            "status": job.status.value,
            "max_retries": job.max_retries,
            "timeout": job.timeout,
            "max_concurrent": job.max_concurrent,
            "retry_count": job.retry_count,
            "run_count": job.run_count,
            "last_run_at": _utc(job.last_run_at).isoformat() if job.last_run_at else None,
            "last_result": job.last_result,
            "created_at": _utc(job.info.created_at).isoformat(),
            "action_type": job.action_type,
            "action_payload": json.dumps(job.action_payload, ensure_ascii=True),
            "claim_token": job.claim_token,
            "claim_expires_at": (
                _utc(job.claim_expires_at).isoformat() if job.claim_expires_at else None
            ),
            "last_error": _failure_json(job.last_error),
            "updated_at": _utc(job.updated_at).isoformat(),
            "revision": job.revision,
        }

    async def save_job(self, job: Job) -> None:
        values = self._job_values(job)
        columns = tuple(values)
        with self._lock:
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                exists = conn.execute("SELECT 1 FROM jobs WHERE id=?", (job.info.id,)).fetchone()
                if exists:
                    assignments = ", ".join(f"{name}=:{name}" for name in columns if name != "id")
                    conn.execute(f"UPDATE jobs SET {assignments} WHERE id=:id", values)
                else:
                    names = ", ".join(columns)
                    params = ", ".join(f":{name}" for name in columns)
                    conn.execute(f"INSERT INTO jobs ({names}) VALUES ({params})", values)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise SchedulerPersistenceError("Scheduler job save failed") from exc

    async def claim_job(
        self,
        job_id: str,
        *,
        now: datetime,
        claim_token: str,
        claim_expires_at: datetime,
        run_id: str,
    ) -> Job | None:
        now_iso = _utc(now).isoformat()
        expires_iso = _utc(claim_expires_at).isoformat()
        with self._lock:
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(
                    """
                    UPDATE jobs
                    SET status='running', claim_token=?, claim_expires_at=?,
                        updated_at=?, revision=revision+1
                    WHERE id=?
                      AND status IN ('active', 'retrying')
                      AND next_run_at IS NOT NULL
                      AND next_run_at<=?
                      AND (claim_token IS NULL OR claim_expires_at<?)
                    """,
                    (claim_token, expires_iso, now_iso, job_id, now_iso, now_iso),
                )
                if cursor.rowcount != 1:
                    conn.rollback()
                    return None
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                attempt = int(row["run_count"] or 0) + 1
                conn.execute(
                    """
                    INSERT INTO job_runs (
                        run_id, job_id, attempt, started_at, status, claim_token, trace_id
                    ) VALUES (?, ?, ?, ?, 'running', ?, ?)
                    """,
                    (run_id, job_id, attempt, now_iso, claim_token, run_id),
                )
                conn.commit()
                return self._row_to_job(row)
            except Exception as exc:
                conn.rollback()
                raise SchedulerPersistenceError("Scheduler job claim failed") from exc

    async def finalize_claim(self, job: Job, run: JobRun, claim_token: str) -> None:
        values = self._job_values(job)
        with self._lock:
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(
                    """
                    UPDATE jobs SET
                        status=:status, next_run_at=:next_run_at,
                        retry_count=:retry_count, run_count=:run_count,
                        last_run_at=:last_run_at, last_result=:last_result,
                        last_error=:last_error, claim_token=NULL,
                        claim_expires_at=NULL, updated_at=:updated_at,
                        revision=revision+1
                    WHERE id=:id AND claim_token=:expected_claim
                    """,
                    {**values, "expected_claim": claim_token},
                )
                if cursor.rowcount != 1:
                    raise JobClaimLostError("Scheduler job claim is no longer owned")
                run_cursor = conn.execute(
                    """
                    UPDATE job_runs SET finished_at=?, status=?, failure=?, trace_id=?
                    WHERE run_id=? AND claim_token=?
                    """,
                    (
                        _utc(run.finished_at).isoformat() if run.finished_at else None,
                        run.status.value,
                        _failure_json(run.failure),
                        run.trace_id,
                        run.id,
                        claim_token,
                    ),
                )
                if run_cursor.rowcount != 1:
                    raise JobClaimLostError("Scheduler JobRun claim is no longer owned")
                conn.commit()
            except JobClaimLostError:
                conn.rollback()
                raise
            except Exception as exc:
                conn.rollback()
                raise SchedulerPersistenceError("Scheduler claim finalization failed") from exc

    async def renew_claim(
        self, job_id: str, claim_token: str, claim_expires_at: datetime
    ) -> bool:
        with self._lock:
            conn = self._connection()
            cursor = conn.execute(
                """
                UPDATE jobs SET claim_expires_at=?, updated_at=?, revision=revision+1
                WHERE id=? AND status='running' AND claim_token=?
                """,
                (
                    _utc(claim_expires_at).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    job_id,
                    claim_token,
                ),
            )
            conn.commit()
            return cursor.rowcount == 1

    async def release_expired_claims(self, now: datetime) -> int:
        now_iso = _utc(now).isoformat()
        expired_failure = _failure_json(FailureInfo(
            code="scheduler.job.claim_expired",
            category=ErrorCategory.EXECUTION_FAILURE,
            message="Scheduler claim expired",
            component="scheduler.persistence",
            operation="recover_claim",
            retryable=True,
        ))
        with self._lock:
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    UPDATE job_runs SET status='failed', finished_at=?, failure=?
                    WHERE status='running' AND claim_token IN (
                        SELECT claim_token FROM jobs
                        WHERE status='running' AND claim_expires_at IS NOT NULL
                          AND claim_expires_at<=?
                    )
                    """,
                    (now_iso, expired_failure, now_iso),
                )
                cursor = conn.execute(
                    """
                    UPDATE jobs SET
                        status=CASE
                            WHEN retry_count + 1 >= max_retries THEN 'failed'
                            ELSE 'retrying'
                        END,
                        retry_count=retry_count+1,
                        run_count=run_count+1,
                        last_result='failed',
                        last_error=?,
                        claim_token=NULL, claim_expires_at=NULL,
                        updated_at=?, revision=revision+1
                    WHERE status='running' AND claim_expires_at IS NOT NULL
                      AND claim_expires_at<=?
                    """,
                    (expired_failure, now_iso, now_iso),
                )
                conn.commit()
                return cursor.rowcount
            except Exception as exc:
                conn.rollback()
                raise SchedulerPersistenceError("Expired Scheduler claim recovery failed") from exc

    async def load_jobs(self) -> list[Job]:
        with self._lock:
            try:
                rows = self._connection().execute("SELECT * FROM jobs ORDER BY created_at, id").fetchall()
                return [self._row_to_job(row) for row in rows]
            except Exception as exc:
                raise SchedulerPersistenceError("Scheduler jobs load failed") from exc

    async def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            try:
                row = self._connection().execute(
                    "SELECT * FROM jobs WHERE id=?", (job_id,)
                ).fetchone()
                return self._row_to_job(row) if row else None
            except Exception as exc:
                raise SchedulerPersistenceError("Scheduler job query failed") from exc

    async def list_job_runs(self, job_id: str) -> list[JobRun]:
        with self._lock:
            try:
                rows = self._connection().execute(
                    "SELECT * FROM job_runs WHERE job_id=? ORDER BY attempt, started_at",
                    (job_id,),
                ).fetchall()
                return [self._row_to_run(row) for row in rows]
            except Exception as exc:
                raise SchedulerPersistenceError("Scheduler JobRun query failed") from exc

    async def delete_job(self, job_id: str) -> bool:
        with self._lock:
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM job_runs WHERE job_id=?", (job_id,))
                cursor = conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as exc:
                conn.rollback()
                raise SchedulerPersistenceError("Scheduler job delete failed") from exc

    async def cancel_job(self, job_id: str, now: datetime) -> bool:
        now_iso = _utc(now).isoformat()
        with self._lock:
            conn = self._connection()
            try:
                cursor = conn.execute(
                    """
                    UPDATE jobs SET status='cancelled', next_run_at=NULL,
                        claim_token=NULL, claim_expires_at=NULL,
                        updated_at=?, revision=revision+1
                    WHERE id=? AND status IN ('active', 'retrying', 'paused')
                    """,
                    (now_iso, job_id),
                )
                conn.commit()
                return cursor.rowcount == 1
            except Exception as exc:
                conn.rollback()
                raise SchedulerPersistenceError("Scheduler job cancellation failed") from exc

    async def reschedule_job(
        self,
        job_id: str,
        *,
        run_at: datetime,
        timezone_name: str,
        action_payload: dict[str, object],
    ) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        run_iso = _utc(run_at).isoformat()
        with self._lock:
            conn = self._connection()
            try:
                cursor = conn.execute(
                    """
                    UPDATE jobs SET run_at=?, next_run_at=?, trigger_timezone=?,
                        action_payload=?, status='active', retry_count=0,
                        last_error=NULL, updated_at=?, revision=revision+1
                    WHERE id=? AND status IN ('active', 'retrying', 'paused', 'failed', 'cancelled')
                    """,
                    (
                        run_iso,
                        run_iso,
                        timezone_name,
                        json.dumps(action_payload, ensure_ascii=True),
                        now_iso,
                        job_id,
                    ),
                )
                conn.commit()
                return cursor.rowcount == 1
            except Exception as exc:
                conn.rollback()
                raise SchedulerPersistenceError("Scheduler job reschedule failed") from exc

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            info=JobInfo(
                id=row["id"],
                name=row["name"],
                description=row["description"] or "",
                version=row["version"] or "1.0.0",
                tags=json.loads(row["tags"] or "[]"),
                metadata=json.loads(row["metadata"] or "{}"),
                created_at=_dt(row["created_at"]),
            ),
            trigger=Trigger(
                trigger_type=TriggerType(row["trigger_type"]),
                cron_expression=row["cron_expression"] or "",
                interval_seconds=row["interval_seconds"] or 0,
                run_at=_dt(row["run_at"]),
                event_type=row["event_type"] or "",
                timezone=row["trigger_timezone"] or "Asia/Shanghai",
                next_run_at=_dt(row["next_run_at"]),
            ),
            workflow_name=row["workflow_name"] or "",
            workflow_variables=json.loads(row["workflow_variables"] or "{}"),
            action_type=row["action_type"] or "workflow",
            action_payload=json.loads(row["action_payload"] or "{}"),
            status=JobStatus(row["status"]),
            max_retries=row["max_retries"],
            timeout=row["timeout"],
            max_concurrent=row["max_concurrent"],
            retry_count=row["retry_count"] or 0,
            run_count=row["run_count"] or 0,
            last_run_at=_dt(row["last_run_at"]),
            last_result=row["last_result"] or "",
            last_error=_failure(row["last_error"]),
            claim_token=row["claim_token"],
            claim_expires_at=_dt(row["claim_expires_at"]),
            updated_at=_dt(row["updated_at"]) or _dt(row["created_at"]),
            revision=row["revision"] or 1,
        )

    def _row_to_run(self, row: sqlite3.Row) -> JobRun:
        return JobRun(
            id=row["run_id"],
            job_id=row["job_id"],
            status=JobRunStatus(row["status"]),
            started_at=_dt(row["started_at"]),
            finished_at=_dt(row["finished_at"]),
            trace_id=row["trace_id"] or "",
            failure=_failure(row["failure"]),
            attempt=row["attempt"],
            claim_token=row["claim_token"],
        )
