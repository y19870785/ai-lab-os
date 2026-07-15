"""Job 执行器 —— 负责真正执行一次 Job。

调用 Workflow Runtime，记录 JobRun，管理超时和重试。
"""

from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime, timezone

from core.scheduler.models import Job, JobRun, JobStatus, JobRunStatus
from core.scheduler.handlers import ActionHandlerRegistry, WorkflowActionHandler
from core.scheduler.exceptions import JobStateError
from core.errors import (
    ErrorCategory,
    failure_event_payload,
    failure_from_exception,
)


logger = logging.getLogger("ai-lab.scheduler.jobs")


class JobExecutor:
    """Job 执行器 —— 委托给 Workflow Runtime"""

    def __init__(self, workflow_runtime=None, bus=None, handler_registry=None):
        self._workflow_runtime = workflow_runtime
        self._bus = bus
        self._running: dict[str, asyncio.Task] = {}
        self._handlers = handler_registry or ActionHandlerRegistry()
        if workflow_runtime is not None and not self._handlers.exists("workflow"):
            self._handlers.register("workflow", WorkflowActionHandler(workflow_runtime))

    async def execute(self, job: Job, run: JobRun | None = None) -> JobRun:
        """执行一次 Job"""
        if job.status == JobStatus.PAUSED:
            raise JobStateError(f"Job {job.info.name} is paused")

        run = run or JobRun(
            job_id=job.info.id,
            job_name=job.info.name,
            status=JobRunStatus.RUNNING,
            attempt=job.run_count + 1,
            claim_token=job.claim_token or "",
        )
        run.trace_id = run.id

        await self._publish("scheduler.job.started", job.info.id, job.info.name)

        t0 = time.time()
        try:
            handler = self._handlers.get(job.action_type)
            run.result = await asyncio.wait_for(
                handler.execute(job, run),
                timeout=job.timeout,
            )
            run.status = JobRunStatus.SUCCESS

        except asyncio.TimeoutError as exc:
            run.status = JobRunStatus.TIMEOUT
            run.failure = failure_from_exception(
                exc,
                component="scheduler.job",
                operation="execute",
                trace_id=run.trace_id,
                code="scheduler.job.timeout",
                category=ErrorCategory.TIMEOUT,
                retryable=True,
                details={"timeout_seconds": job.timeout},
            )
            run.error = f"Job timed out after {job.timeout}s"
        except Exception as exc:
            run.status = JobRunStatus.FAILED
            run.failure = failure_from_exception(
                exc,
                component="scheduler.job",
                operation="execute",
                trace_id=run.trace_id,
                code="scheduler.job.execution_failed",
            )
            if run.failure.category == ErrorCategory.INTERNAL:
                run.failure = run.failure.model_copy(update={
                    "category": ErrorCategory.DEPENDENCY_FAILURE,
                    "retryable": True,
                })
            run.error = run.failure.message
            logger.exception(
                "scheduler.job.execution_failed",
                extra={"job_id": job.info.id, "trace_id": run.trace_id,
                       "failure_code": run.failure.code},
            )

        run.finished_at = datetime.now(timezone.utc)
        run.latency_ms = (time.time() - t0) * 1000

        # 更新 Job 状态
        job.last_run_at = run.finished_at
        job.last_result = run.status.value
        job.last_error = run.failure
        job.run_count += 1

        event_type = "scheduler.job.completed" if run.status == JobRunStatus.SUCCESS else "scheduler.job.failed"
        event_extra = {"status": run.status.value, "trace_id": run.trace_id,
                       "latency_ms": run.latency_ms}
        if run.failure is not None:
            event_extra.update(failure_event_payload(run.failure))
        await self._publish(event_type, job.info.id, job.info.name, event_extra)

        return run

    async def _publish(self, event_type: str, job_id: str, job_name: str, extra: dict | None = None):
        if self._bus is None:
            return
        from core.bus.memory_events import make_memory_event
        event = make_memory_event(
            event_type=event_type, memory_id=job_id, memory_type="scheduler",
            source="scheduler.runtime",
            trace_id=str((extra or {}).get("trace_id", "")),
            extra=extra or {},
        )
        await self._bus.publish(event.event_type, event)
