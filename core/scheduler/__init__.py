"""AI-Lab Scheduler Runtime —— 统一调度中心。

Scheduler 是整个 AI-Lab 的调度中心。
所有自动执行能力（Cron / Interval / Event / Manual）都必须经过 Scheduler。

架构位置：
    Application → Scheduler → Workflow → Agent → Knowledge → Provider → Tool
"""

from core.scheduler.models import (
    Job, JobInfo, JobRun, JobStatus, JobRunStatus,
    Trigger, TriggerType, ScheduleRequest,
)
from core.scheduler.protocol import SchedulerProtocol
from core.scheduler.runtime import SchedulerRuntime
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.triggers import TriggerEngine
from core.scheduler.jobs import JobExecutor
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.config import SchedulerConfig
from core.scheduler.events import SchedulerEventTypes, publish_scheduler_event
from core.scheduler.exceptions import (
    SchedulerError, JobNotFoundError, JobAlreadyExistsError,
    JobStateError, TriggerError, SchedulerShutdownError,
)

__all__ = [
    # Models
    "Job", "JobInfo", "JobRun", "JobStatus", "JobRunStatus",
    "Trigger", "TriggerType", "ScheduleRequest",
    # Core
    "SchedulerProtocol", "SchedulerRuntime", "SchedulerRegistry",
    "TriggerEngine", "JobExecutor", "SchedulerPersistence",
    "SchedulerConfig",
    # Events
    "SchedulerEventTypes", "publish_scheduler_event",
    # Exceptions
    "SchedulerError", "JobNotFoundError", "JobAlreadyExistsError",
    "JobStateError", "TriggerError", "SchedulerShutdownError",
]
