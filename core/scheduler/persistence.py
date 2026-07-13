"""Scheduler Persistence —— SQLite 持久化层。

负责 Job 的持久化存储，支持重启恢复。
"""

from __future__ import annotations
import json
import sqlite3
import os
from datetime import datetime, timezone
from core.scheduler.models import Job, JobInfo, Trigger, TriggerType, JobStatus


class SchedulerPersistence:
    """Scheduler SQLite 持久化"""

    def __init__(self, db_path: str = "scheduler.db"):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self):
        self._conn.execute("""
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
                created_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    async def save_job(self, job: Job) -> None:
        """保存或更新 Job"""
        row = {
            "id": job.info.id,
            "name": job.info.name,
            "description": job.info.description,
            "version": job.info.version,
            "tags": json.dumps(job.info.tags),
            "metadata": json.dumps(job.info.metadata),
            "trigger_type": job.trigger.trigger_type.value,
            "cron_expression": job.trigger.cron_expression,
            "interval_seconds": job.trigger.interval_seconds,
            "run_at": job.trigger.run_at.isoformat() if job.trigger.run_at else None,
            "event_type": job.trigger.event_type,
            "trigger_timezone": job.trigger.timezone,
            "next_run_at": job.trigger.next_run_at.isoformat() if job.trigger.next_run_at else None,
            "workflow_name": job.workflow_name,
            "workflow_variables": json.dumps(job.workflow_variables),
            "status": job.status.value,
            "max_retries": job.max_retries,
            "timeout": job.timeout,
            "max_concurrent": job.max_concurrent,
            "retry_count": job.retry_count,
            "run_count": job.run_count,
            "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
            "last_result": job.last_result,
            "created_at": job.info.created_at.isoformat(),
        }
        self._conn.execute("""
            INSERT OR REPLACE INTO jobs (
                id, name, description, version, tags, metadata,
                trigger_type, cron_expression, interval_seconds, run_at,
                event_type, trigger_timezone, next_run_at,
                workflow_name, workflow_variables, status,
                max_retries, timeout, max_concurrent,
                retry_count, run_count, last_run_at, last_result, created_at
            ) VALUES (
                :id, :name, :description, :version, :tags, :metadata,
                :trigger_type, :cron_expression, :interval_seconds, :run_at,
                :event_type, :trigger_timezone, :next_run_at,
                :workflow_name, :workflow_variables, :status,
                :max_retries, :timeout, :max_concurrent,
                :retry_count, :run_count, :last_run_at, :last_result, :created_at
            )
        """, row)
        self._conn.commit()

    async def load_jobs(self) -> list[Job]:
        """加载所有 Job"""
        cursor = self._conn.execute("SELECT * FROM jobs")
        jobs = []
        for row in cursor.fetchall():
            jobs.append(self._row_to_job(row))
        return jobs

    async def delete_job(self, job_id: str) -> bool:
        """删除 Job"""
        cursor = self._conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def _row_to_job(self, row) -> Job:
        """将数据库行转换为 Job 对象"""
        run_at = None
        if row["run_at"]:
            try:
                run_at = datetime.fromisoformat(row["run_at"])
            except ValueError:
                pass
        next_run = None
        if row["next_run_at"]:
            try:
                next_run = datetime.fromisoformat(row["next_run_at"])
            except ValueError:
                pass
        last_run = None
        if row["last_run_at"]:
            try:
                last_run = datetime.fromisoformat(row["last_run_at"])
            except ValueError:
                pass
        created = datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc)

        return Job(
            info=JobInfo(
                id=row["id"], name=row["name"], description=row["description"] or "",
                version=row["version"] or "1.0.0",
                tags=json.loads(row["tags"]) if row["tags"] else [],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=created,
            ),
            trigger=Trigger(
                trigger_type=TriggerType(row["trigger_type"]),
                cron_expression=row["cron_expression"] or "",
                interval_seconds=row["interval_seconds"] or 0,
                run_at=run_at,
                event_type=row["event_type"] or "",
                timezone=row["trigger_timezone"] or "Asia/Shanghai",
                next_run_at=next_run,
            ),
            workflow_name=row["workflow_name"] or "",
            workflow_variables=json.loads(row["workflow_variables"]) if row["workflow_variables"] else {},
            status=JobStatus(row["status"]),
            max_retries=row["max_retries"],
            timeout=row["timeout"],
            max_concurrent=row["max_concurrent"],
            retry_count=row["retry_count"] or 0,
            run_count=row["run_count"] or 0,
            last_run_at=last_run,
            last_result=row["last_result"] or "",
        )
