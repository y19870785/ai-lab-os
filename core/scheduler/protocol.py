"""SchedulerProtocol —— Scheduler Runtime 抽象接口"""

from __future__ import annotations
from abc import ABC, abstractmethod
from core.scheduler.models import Job, ScheduleRequest, JobRun, Trigger


class SchedulerProtocol(ABC):
    """Scheduler 抽象接口"""

    @abstractmethod
    async def initialize(self) -> None:
        """初始化调度器"""
        ...

    @abstractmethod
    async def start(self) -> None:
        """启动调度循环"""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """关闭调度器"""
        ...

    @abstractmethod
    async def schedule(self, request: ScheduleRequest) -> Job:
        """创建一个调度任务"""
        ...

    @abstractmethod
    async def pause_job(self, job_id: str) -> bool:
        """暂停任务"""
        ...

    @abstractmethod
    async def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        ...

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """删除任务"""
        ...

    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None:
        """获取任务"""
        ...

    @abstractmethod
    async def list_jobs(self) -> list[Job]:
        """列出所有任务"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        ...
