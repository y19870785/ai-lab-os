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
import inspect
import logging
import uuid
from datetime import datetime, timedelta, timezone

from core.scheduler.models import (
    Job, JobInfo, JobRun, JobRunStatus, JobStatus, TriggerType, ScheduleRequest,
)
from core.scheduler.protocol import SchedulerProtocol
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.triggers import TriggerEngine
from core.scheduler.jobs import JobExecutor
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.config import SchedulerConfig
from core.scheduler.events import publish_scheduler_event, SchedulerEventTypes
from core.scheduler.exceptions import (
    JobNotFoundError, JobAlreadyExistsError, JobStateError,
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
        self._observability_error: str | None = None

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        if self._persistence and self._config.persistence_enabled:
            await self._persistence.initialize()
            await self._persistence.release_expired_claims(
                datetime.now(timezone.utc),
                retry_delay_seconds=self._config.retry_delay_seconds,
            )
            if self._config.auto_recover:
                await self._recover_jobs()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._consecutive_failures = 0
        await self._publish_event(SchedulerEventTypes.STARTED)
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
        await self._publish_event(SchedulerEventTypes.SHUTDOWN)
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
            action_type=request.action_type,
            action_payload=request.action_payload,
            trace_id=request.trace_id,
            timeout=self._config.default_timeout,
        )

        self._registry.register(job)
        try:
            if self._persistence and self._config.persistence_enabled:
                await self._persistence.save_job(job)
        except Exception:
            self._registry.unregister(job.info.id)
            raise

        await self._publish_event(
            SchedulerEventTypes.CREATED, job.info.id, job.info.name,
            {"trace_id": job.trace_id},
        )
        return job

    async def pause_job(self, job_id: str) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False
        if job.status == JobStatus.RUNNING:
            raise JobStateError("Running Job cannot be paused")
        if self._persistence and self._config.persistence_enabled:
            changed = await self._persistence.pause_job(
                job_id, job.revision, datetime.now(timezone.utc)
            )
            if changed is None:
                await self._sync_registry_from_persistence()
                raise JobStateError("Job changed concurrently and cannot be paused")
            self._registry.replace(changed)
            job = changed
        else:
            if job.status not in {JobStatus.ACTIVE, JobStatus.RETRYING}:
                raise JobStateError("Only active or retrying Job can be paused")
            job.status = JobStatus.PAUSED
        await self._publish_event(
            SchedulerEventTypes.PAUSED, job_id, job.info.name,
            {"trace_id": job.trace_id},
        )
        return True

    async def resume_job(self, job_id: str) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False
        if job.status != JobStatus.PAUSED:
            raise JobStateError("Only paused Job can be resumed")
        next_run_at = job.trigger.next_run_at
        if job.trigger.trigger_type != TriggerType.MANUAL:
            next_run_at = TriggerEngine.compute_next(job.trigger)
        if self._persistence and self._config.persistence_enabled:
            changed = await self._persistence.resume_job(
                job_id,
                job.revision,
                next_run_at=next_run_at,
                now=datetime.now(timezone.utc),
            )
            if changed is None:
                await self._sync_registry_from_persistence()
                raise JobStateError("Job changed concurrently and cannot be resumed")
            self._registry.replace(changed)
            job = changed
        else:
            job.status = JobStatus.ACTIVE
            job.trigger.next_run_at = next_run_at
        await self._publish_event(
            SchedulerEventTypes.RESUMED, job_id, job.info.name,
            {"trace_id": job.trace_id},
        )
        return True

    async def delete_job(self, job_id: str) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False
        if job.status == JobStatus.RUNNING:
            raise JobStateError("Running Job cannot be deleted")
        if self._persistence and self._config.persistence_enabled:
            deleted = await self._persistence.delete_job(job_id, job.revision)
            if not deleted:
                await self._sync_registry_from_persistence()
                raise JobStateError("Job changed concurrently and cannot be deleted")
        self._registry.unregister(job_id)
        await self._publish_event(
            SchedulerEventTypes.DELETED, job_id, job.info.name,
            {"trace_id": job.trace_id},
        )
        return True

    async def cancel_job(self, job_id: str) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False
        if self._persistence and self._config.persistence_enabled:
            cancelled = await self._persistence.cancel_job(job_id, datetime.now(timezone.utc))
            await self._sync_registry_from_persistence()
            return cancelled
        if job.status not in (JobStatus.ACTIVE, JobStatus.RETRYING, JobStatus.PAUSED):
            return False
        job.status = JobStatus.CANCELLED
        job.trigger.next_run_at = None
        job.claim_token = None
        job.claim_expires_at = None
        return True

    async def reschedule_one_shot(
        self,
        job_id: str,
        *,
        run_at: datetime,
        timezone_name: str,
        action_payload: dict[str, object],
    ) -> bool:
        job = await self.get_job(job_id)
        if job is None or job.trigger.trigger_type != TriggerType.ONE_SHOT:
            return False
        if self._persistence and self._config.persistence_enabled:
            changed = await self._persistence.reschedule_job(
                job_id,
                expected_revision=job.revision,
                run_at=run_at,
                timezone_name=timezone_name,
                action_payload=action_payload,
            )
            await self._sync_registry_from_persistence()
            return changed
        if job.status not in (
            JobStatus.ACTIVE, JobStatus.RETRYING, JobStatus.PAUSED,
            JobStatus.FAILED, JobStatus.CANCELLED,
        ):
            return False
        job.trigger.run_at = run_at
        job.trigger.next_run_at = run_at
        job.trigger.timezone = timezone_name
        job.action_payload = action_payload
        job.status = JobStatus.ACTIVE
        job.retry_count = 0
        job.last_error = None
        return True

    async def get_job(self, job_id: str) -> Job | None:
        if self._persistence and self._config.persistence_enabled:
            job = await self._persistence.get_job(job_id)
            if job is not None and self._registry.exists(job_id):
                self._registry.replace(job)
            return job
        try:
            return self._registry.get(job_id)
        except JobNotFoundError:
            return None

    async def list_jobs(self) -> list[Job]:
        if self._persistence and self._config.persistence_enabled:
            await self._sync_registry_from_persistence()
        return self._registry.list()

    async def list_job_runs(self, job_id: str) -> list[JobRun]:
        if not self._persistence or not self._config.persistence_enabled:
            return []
        return await self._persistence.list_job_runs(job_id)

    async def health_check(self) -> bool:
        return self._running

    async def health(self) -> dict[str, object]:
        if not self._running:
            status = RuntimeStatus.STOPPED
        elif self._consecutive_failures >= self._config.failure_threshold:
            status = RuntimeStatus.FAILED
        elif self._consecutive_failures or self._observability_error or getattr(
            self._executor, "observability_degraded", False
        ):
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
            "observability_error": self._observability_error,
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
                await self._publish_event(
                    SchedulerEventTypes.TICK_FAILED,
                    extra=failure_event_payload(self._last_error),
                )
            if self._running:
                await asyncio.sleep(self._config.tick_interval)

    async def _tick(self):
        """一次调度周期：检查所有 ACTIVE Job 是否应该触发"""
        now = datetime.now(timezone.utc)
        if self._persistence and self._config.persistence_enabled:
            await self._persistence.release_expired_claims(
                now, retry_delay_seconds=self._config.retry_delay_seconds
            )
            await self._sync_registry_from_persistence()
        active_jobs = [
            job for job in self._registry.list()
            if job.status in (JobStatus.ACTIVE, JobStatus.RETRYING)
        ]

        for job in active_jobs:
            if not TriggerEngine.should_fire(job.trigger, now):
                continue

            # 并发限制
            running_count = sum(1 for j in self._registry.list() if j.status == JobStatus.RUNNING)
            if running_count >= self._config.max_concurrent_jobs:
                continue

            claim_token = uuid.uuid4().hex
            run_id = uuid.uuid4().hex[:12]
            persisted_claim = bool(self._persistence and self._config.persistence_enabled)
            if persisted_claim:
                claimed = await self._persistence.claim_job(
                    job.info.id,
                    now=now,
                    claim_token=claim_token,
                    claim_expires_at=now + timedelta(seconds=self._config.claim_ttl_seconds),
                    run_id=run_id,
                )
                if claimed is None:
                    continue
                job = claimed
                self._registry.replace(job)
            else:
                job.status = JobStatus.RUNNING
                job.claim_token = claim_token
                job.claim_expires_at = now + timedelta(
                    seconds=self._config.claim_ttl_seconds
                )
            run = JobRun(
                id=run_id,
                job_id=job.info.id,
                job_name=job.info.name,
                status=JobRunStatus.RUNNING,
                started_at=now,
                trace_id=job.trace_id or run_id,
                attempt=job.run_count + 1,
                claim_token=claim_token,
            )
            task = asyncio.create_task(
                self._run_job(job, run, claim_token, persisted_claim),
                name=f"ai-lab-scheduler-job-{job.info.id}",
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            task.add_done_callback(self._observe_background_task)

    async def _run_job(
        self, job: Job, run: JobRun, claim_token: str, persisted_claim: bool
    ):
        """执行一次 Job"""
        job.status = JobStatus.RUNNING
        renewal_task = (
            asyncio.create_task(
                self._renew_claim_loop(job.info.id, claim_token),
                name=f"ai-lab-scheduler-claim-renewal-{job.info.id}",
            )
            if persisted_claim else None
        )
        try:
            execute_parameters = inspect.signature(self._executor.execute).parameters
            if len(execute_parameters) >= 2:
                run = await self._executor.execute(job, run)
            else:
                legacy_run = await self._executor.execute(job)
                run = legacy_run.model_copy(update={
                    "id": run.id,
                    "attempt": run.attempt,
                    "claim_token": claim_token,
                    "trace_id": legacy_run.trace_id or run.trace_id,
                })
            job.last_error = run.failure

            # 更新状态
            if run.status.value == "success":
                job.retry_count = 0
                if job.trigger.trigger_type == TriggerType.ONE_SHOT:
                    job.status = JobStatus.COMPLETED
                else:
                    job.status = JobStatus.ACTIVE
            else:
                job.retry_count += 1
                if job.retry_count >= job.max_retries:
                    job.status = JobStatus.FAILED
                else:
                    job.status = JobStatus.RETRYING

            # 计算下次触发时间
            if job.status == JobStatus.ACTIVE and job.trigger.trigger_type != TriggerType.MANUAL:
                job.trigger.next_run_at = TriggerEngine.compute_next(
                    job.trigger, datetime.now(timezone.utc)
                )
            elif job.status == JobStatus.RETRYING:
                job.trigger.next_run_at = datetime.now(timezone.utc) + timedelta(
                    seconds=self._config.retry_delay_seconds
                )
            else:
                job.trigger.next_run_at = None

            job.updated_at = datetime.now(timezone.utc)
            job.claim_token = claim_token

        except asyncio.CancelledError:
            # Leave the durable claim recoverable; expiry permits a later owner to retry.
            if not persisted_claim:
                job.status = JobStatus.ACTIVE
                job.claim_token = None
                job.claim_expires_at = None
            await self._stop_renewal(renewal_task)
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
            await self._publish_event(
                SchedulerEventTypes.JOB_FAILED,
                job.info.id,
                job.info.name,
                failure_event_payload(job.last_error),
            )
            run.status = JobRunStatus.FAILED
            run.failure = job.last_error
            run.error = "Scheduler runtime failed"
            run.finished_at = datetime.now(timezone.utc)
            job.run_count += 1
            job.last_run_at = run.finished_at
            job.last_result = run.status.value

        await self._stop_renewal(renewal_task)
        if persisted_claim:
            await self._persistence.finalize_claim(job, run, claim_token)
            persisted = await self._persistence.get_job(job.info.id)
            if persisted is not None:
                self._registry.replace(persisted)
        else:
            job.claim_token = None
            job.claim_expires_at = None

    async def _renew_claim_loop(self, job_id: str, claim_token: str) -> None:
        interval = max(self._config.claim_ttl_seconds / 3, 0.05)
        while True:
            await asyncio.sleep(interval)
            renewed = await self._persistence.renew_claim(
                job_id,
                claim_token,
                datetime.now(timezone.utc) + timedelta(
                    seconds=self._config.claim_ttl_seconds
                ),
            )
            if not renewed:
                return

    @staticmethod
    async def _stop_renewal(task: asyncio.Task | None) -> None:
        if task is None:
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

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

    async def _publish_event(
        self,
        event_type: str,
        job_id: str = "",
        job_name: str = "",
        extra: dict | None = None,
    ) -> None:
        try:
            await publish_scheduler_event(
                self._bus, event_type, job_id, job_name, extra
            )
            self._observability_error = None
        except Exception:
            self._observability_error = "event_publish_failed"
            logger.warning(
                "scheduler.event.publish_failed",
                extra={"event_type": event_type, "job_id": job_id},
            )

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

    async def _sync_registry_from_persistence(self) -> None:
        if not self._persistence:
            return
        jobs = await self._persistence.load_jobs()
        persisted_ids = {job.info.id for job in jobs}
        for job in jobs:
            if self._registry.exists(job.info.id):
                self._registry.replace(job)
            else:
                self._registry.register(job)
        for job_id in tuple(self._registry.list_ids()):
            if job_id not in persisted_ids:
                self._registry.unregister(job_id)
