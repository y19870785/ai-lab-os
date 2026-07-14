"""SchedulerRuntime —— AI-Lab 统一调度中心。

职责：
1. 维护所有 Job 的生命周期
2. 按 Trigger 触发 Job 执行
3. 委托 JobExecutor 执行（→ Workflow Runtime）
4. 管理并发限制
5. 持久化恢复
6. 事件发布

Scheduler 不直接执行业务，只能通过 Workflow Runtime。
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from core.scheduler.models import (
    Job, JobInfo, JobRun, JobStatus, Trigger, TriggerType, ScheduleRequest,
)
from core.scheduler.protocol import SchedulerProtocol
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.triggers import TriggerEngine
from core.scheduler.jobs import JobExecutor
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.config import SchedulerConfig
from core.scheduler.events import publish_scheduler_event, SchedulerEventTypes
from core.scheduler.exceptions import (
    JobNotFoundError, JobAlreadyExistsError, JobStateError, SchedulerShutdownError,
)
from core.errors import (
    ErrorCategory,
    FailureInfo,
    RuntimeStatus,
    failure_event_payload,
    failure_from_exception,
)


logger = logging.getLogger("ai-lab.scheduler.runtime")


class SchedulerRuntime(SchedulerProtocol):
    """Scheduler 运行时 —— 统一调度中心"""

    def __init__(
        self,
        registry: SchedulerRegistry | None = None,
        executor: JobExecutor | None = None,
        persistence: SchedulerPersistence | None = None,
        config: SchedulerConfig | None = None,
        bus=None,
    ):
        self._registry = registry or SchedulerRegistry()
        self._executor = executor or JobExecutor()
        self._persistence = persistence
        self._config = config or SchedulerConfig()
        self._bus = bus
        self._tick_task: asyncio.Task | None = None
        self._running = False
        self._job_locks: dict[str, asyncio.Lock] = {}
        self._background_tasks: set[asyncio.Task] = set()
        self._last_tick_at: datetime | None = None
        self._last_successful_tick_at: datetime | None = None
        self._last_error: FailureInfo | None = None
        self._consecutive_failures = 0

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        if self._persistence and self._config.persistence_enabled:
            await self._persistence.initialize()
            if self._config.auto_recover:
                await self._recover_jobs()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._consecutive_failures = 0
        await publish_scheduler_event(self._bus, SchedulerEventTypes.STARTED)
        self._tick_task = asyncio.create_task(self._tick_loop(), name="ai-lab-scheduler-tick")

    async def shutdown(self) -> None:
        self._running = False
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None
        tasks = list(self._background_tasks)
        if tasks:
            if self._config.cancel_running_jobs_on_shutdown:
                for task in tasks:
                    task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=self._config.shutdown_timeout,
                )
            except asyncio.TimeoutError:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()
        await publish_scheduler_event(self._bus, SchedulerEventTypes.SHUTDOWN)
        if self._persistence:
            await self._persistence.close()

    # ---- Job 管理 ----

    async def schedule(self, request: ScheduleRequest) -> Job:
        """创建一个调度任务"""
        # 检查重名
        existing = self._registry.get_by_name(request.job_name)
        if existing:
            raise JobAlreadyExistsError(f"Job already exists: {request.job_name}")

        # 验证 Trigger
        if not TriggerEngine.validate(request.trigger):
            from core.scheduler.exceptions import TriggerError
            raise TriggerError(f"Invalid trigger: {request.trigger.trigger_type}")

        # 计算首次触发时间
        trigger = request.trigger
        if trigger.trigger_type != TriggerType.MANUAL:
            trigger.next_run_at = TriggerEngine.compute_next(trigger)

        job = Job(
            info=JobInfo(name=request.job_name, tags=request.metadata.get("tags", [])),
            trigger=trigger,
            workflow_name=request.workflow_name,
            workflow_variables=request.variables,
            timeout=self._config.default_timeout,
        )

        self._registry.register(job)

        if self._persistence and self._config.persistence_enabled:
            await self._persistence.save_job(job)

        await publish_scheduler_event(
            self._bus, SchedulerEventTypes.CREATED, job.info.id, job.info.name,
        )
        return job

    async def pause_job(self, job_id: str) -> bool:
        job = self._registry.get(job_id)
        job.status = JobStatus.PAUSED
        await self._save_job(job)
        await publish_scheduler_event(
            self._bus, SchedulerEventTypes.PAUSED, job_id, job.info.name,
        )
        return True

    async def resume_job(self, job_id: str) -> bool:
        job = self._registry.get(job_id)
        job.status = JobStatus.ACTIVE
        # 重新计算下次触发时间
        if job.trigger.trigger_type != TriggerType.MANUAL:
            job.trigger.next_run_at = TriggerEngine.compute_next(job.trigger)
        await self._save_job(job)
        await publish_scheduler_event(
            self._bus, SchedulerEventTypes.RESUMED, job_id, job.info.name,
        )
        return True

    async def delete_job(self, job_id: str) -> bool:
        if not self._registry.exists(job_id):
            return False
        job = self._registry.get(job_id)
        self._registry.unregister(job_id)
        if self._persistence:
            await self._persistence.delete_job(job_id)
        await publish_scheduler_event(
            self._bus, SchedulerEventTypes.DELETED, job_id, job.info.name,
        )
        return True

    async def get_job(self, job_id: str) -> Job | None:
        try:
            return self._registry.get(job_id)
        except JobNotFoundError:
            return None

    async def list_jobs(self) -> list[Job]:
        return self._registry.list()

    async def health_check(self) -> bool:
        return self._running

    async def health(self) -> dict[str, object]:
        if not self._running:
            status = RuntimeStatus.STOPPED
        elif self._consecutive_failures >= self._config.failure_threshold:
            status = RuntimeStatus.FAILED
        elif self._consecutive_failures:
            status = RuntimeStatus.DEGRADED
        else:
            status = RuntimeStatus.OK
        jobs = self._registry.list()
        return {
            "status": status.value,
            "running": self._running,
            "active_jobs": sum(1 for job in jobs if job.status == JobStatus.ACTIVE),
            "running_jobs": len(self._background_tasks),
            "consecutive_failures": self._consecutive_failures,
            "last_tick_at": self._last_tick_at.isoformat() if self._last_tick_at else None,
            "last_successful_tick_at": (
                self._last_successful_tick_at.isoformat()
                if self._last_successful_tick_at else None
            ),
            "last_error": self._last_error.to_dict() if self._last_error else None,
        }

    # ---- 内部 ----

    async def _tick_loop(self):
        """主调度循环"""
        while self._running:
            try:
                await self._tick()
                now = datetime.now(timezone.utc)
                self._last_tick_at = now
                self._last_successful_tick_at = now
                self._consecutive_failures = 0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._last_tick_at = datetime.now(timezone.utc)
                self._consecutive_failures += 1
                self._last_error = failure_from_exception(
                    exc,
                    component="scheduler.runtime",
                    operation="tick",
                    code="scheduler.tick.failed",
                    category=ErrorCategory.EXECUTION_FAILURE,
                    retryable=True,
                    details={"consecutive_failures": self._consecutive_failures},
                )
                logger.exception(
                    "scheduler.tick.failed",
                    extra={"failure_code": self._last_error.code,
                           "consecutive_failures": self._consecutive_failures},
                )
                await publish_scheduler_event(
                    self._bus,
                    SchedulerEventTypes.TICK_FAILED,
                    extra=failure_event_payload(self._last_error),
                )
            if self._running:
                await asyncio.sleep(self._config.tick_interval)

    async def _tick(self):
        """一次调度周期：检查所有 ACTIVE Job 是否应该触发"""
        now = datetime.now(timezone.utc)
        active_jobs = [j for j in self._registry.list() if j.status == JobStatus.ACTIVE]

        for job in active_jobs:
            if not TriggerEngine.should_fire(job.trigger, now):
                continue

            # 并发限制
            running_count = sum(1 for j in self._registry.list() if j.status == JobStatus.RUNNING)
            if running_count >= self._config.max_concurrent_jobs:
                continue

            job.status = JobStatus.RUNNING
            task = asyncio.create_task(
                self._run_job(job),
                name=f"ai-lab-scheduler-job-{job.info.id}",
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            task.add_done_callback(self._observe_background_task)

    async def _run_job(self, job: Job):
        """执行一次 Job"""
        job.status = JobStatus.RUNNING
        try:
            run = await self._executor.execute(job)
            job.last_error = run.failure

            # 更新状态
            if run.status.value == "success":
                job.status = JobStatus.ACTIVE
                job.retry_count = 0
            else:
                job.retry_count += 1
                if job.retry_count >= job.max_retries:
                    job.status = JobStatus.FAILED
                else:
                    job.status = JobStatus.ACTIVE

            # 计算下次触发时间
            if job.status == JobStatus.ACTIVE and job.trigger.trigger_type != TriggerType.MANUAL:
                job.trigger.next_run_at = TriggerEngine.compute_next(job.trigger)
            else:
                job.trigger.next_run_at = None

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            await self._save_job(job)
            raise
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.last_error = failure_from_exception(
                exc,
                component="scheduler.runtime",
                operation="run_job",
                code="scheduler.job.runtime_failed",
                category=ErrorCategory.EXECUTION_FAILURE,
                retryable=True,
                details={"job_id": job.info.id},
            )
            logger.exception(
                "scheduler.job.runtime_failed",
                extra={"job_id": job.info.id, "failure_code": job.last_error.code},
            )
            await publish_scheduler_event(
                self._bus,
                SchedulerEventTypes.JOB_FAILED,
                job.info.id,
                job.info.name,
                failure_event_payload(job.last_error),
            )

        await self._save_job(job)

    def _observe_background_task(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        try:
            error = task.exception()
        except asyncio.CancelledError:
            return
        if error is not None:
            logger.error(
                "scheduler.background_task.failed",
                exc_info=(type(error), error, error.__traceback__),
            )

    async def _save_job(self, job: Job):
        if self._persistence and self._config.persistence_enabled:
            await self._persistence.save_job(job)

    async def _recover_jobs(self):
        """从持久化恢复 Job"""
        if not self._persistence:
            return
        jobs = await self._persistence.load_jobs()
        for job in jobs:
            try:
                self._registry.register(job)
            except JobAlreadyExistsError:
                pass
