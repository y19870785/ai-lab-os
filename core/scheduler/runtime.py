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
import time
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
        await publish_scheduler_event(self._bus, SchedulerEventTypes.STARTED)
        self._tick_task = asyncio.create_task(self._tick_loop())

    async def shutdown(self) -> None:
        self._running = False
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None
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

    # ---- 内部 ----

    async def _tick_loop(self):
        """主调度循环"""
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
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

            # 执行
            asyncio.create_task(self._run_job(job))

    async def _run_job(self, job: Job):
        """执行一次 Job"""
        job.status = JobStatus.RUNNING
        try:
            run = await self._executor.execute(job)

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

        except Exception:
            job.status = JobStatus.FAILED

        await self._save_job(job)

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
