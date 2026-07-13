"""Job 执行器 —— 负责真正执行一次 Job。

调用 Workflow Runtime，记录 JobRun，管理超时和重试。
"""

from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone

from core.scheduler.models import Job, JobRun, JobStatus, JobRunStatus
from core.scheduler.exceptions import JobStateError


class JobExecutor:
    """Job 执行器 —— 委托给 Workflow Runtime"""

    def __init__(self, workflow_runtime=None, bus=None):
        self._workflow_runtime = workflow_runtime
        self._bus = bus
        self._running: dict[str, asyncio.Task] = {}

    async def execute(self, job: Job) -> JobRun:
        """执行一次 Job"""
        if job.status == JobStatus.PAUSED:
            raise JobStateError(f"Job {job.info.name} is paused")

        run = JobRun(job_id=job.info.id, job_name=job.info.name, status=JobRunStatus.RUNNING)

        await self._publish("scheduler.job.started", job.info.id, job.info.name)

        t0 = time.time()
        try:
            if self._workflow_runtime:
                from core.workflow.models import WorkflowRequest
                req = WorkflowRequest(
                    workflow_name=job.workflow_name,
                    user_input=f"Scheduled: {job.info.name}",
                    variables=job.workflow_variables,
                    trace_id=run.id,
                )
                result = await asyncio.wait_for(
                    self._workflow_runtime.run(req),
                    timeout=job.timeout,
                )
                run.status = JobRunStatus.SUCCESS if result.status.value == "completed" else JobRunStatus.FAILED
                run.result = result.outputs if result.status.value == "completed" else result.errors
            else:
                # 无 Workflow Runtime 时模拟执行
                await asyncio.sleep(0.01)
                run.status = JobRunStatus.SUCCESS
                run.result = {"status": "ok", "note": "no workflow runtime"}

        except asyncio.TimeoutError:
            run.status = JobRunStatus.TIMEOUT
            run.error = f"Job timed out after {job.timeout}s"
        except Exception as e:
            run.status = JobRunStatus.FAILED
            run.error = str(e)

        run.finished_at = datetime.now(timezone.utc)
        run.latency_ms = (time.time() - t0) * 1000

        # 更新 Job 状态
        job.last_run_at = run.finished_at
        job.last_result = run.status.value
        job.run_count += 1

        event_type = "scheduler.job.completed" if run.status == JobRunStatus.SUCCESS else "scheduler.job.failed"
        await self._publish(event_type, job.info.id, job.info.name,
                            {"status": run.status.value, "latency_ms": run.latency_ms})

        return run

    async def _publish(self, event_type: str, job_id: str, job_name: str, extra: dict | None = None):
        if self._bus is None:
            return
        from core.bus.memory_events import make_memory_event
        event = make_memory_event(
            event_type=event_type, memory_id=job_id, memory_type="scheduler",
            source="scheduler.runtime", extra=extra or {},
        )
        await self._bus.publish(event.event_type, event)
