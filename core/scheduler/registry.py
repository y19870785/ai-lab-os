"""SchedulerRegistry —— Job 注册与发现中心"""

from __future__ import annotations
from core.scheduler.models import Job
from core.scheduler.exceptions import JobNotFoundError, JobAlreadyExistsError


class SchedulerRegistry:
    """Job 注册中心"""

    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def register(self, job: Job) -> None:
        """注册一个 Job —— 按 ID 和 Name 双重去重"""
        if job.info.id in self._jobs:
            raise JobAlreadyExistsError(f"Job already exists: {job.info.name}")
        if self.get_by_name(job.info.name) is not None:
            raise JobAlreadyExistsError(f"Job already exists: {job.info.name}")
        self._jobs[job.info.id] = job

    def unregister(self, job_id: str) -> bool:
        """移除一个 Job"""
        return self._jobs.pop(job_id, None) is not None

    def replace(self, job: Job) -> None:
        """Replace one already-known job with freshly persisted state."""
        if job.info.id not in self._jobs:
            raise JobNotFoundError(f"Job not found: {job.info.id}")
        self._jobs[job.info.id] = job

    def get(self, job_id: str) -> Job:
        """获取 Job"""
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return job

    def get_by_name(self, name: str) -> Job | None:
        """按名称获取 Job"""
        for job in self._jobs.values():
            if job.info.name == name:
                return job
        return None

    def list(self) -> list[Job]:
        """列出所有 Job"""
        return list(self._jobs.values())

    def list_ids(self) -> list[str]:
        """列出所有 Job ID"""
        return list(self._jobs.keys())

    def search(self, tag: str = "", name_pattern: str = "") -> list[Job]:
        """搜索 Job"""
        results = list(self._jobs.values())
        if tag:
            results = [j for j in results if tag in j.info.tags]
        if name_pattern:
            results = [j for j in results if name_pattern.lower() in j.info.name.lower()]
        return results

    def exists(self, job_id: str) -> bool:
        return job_id in self._jobs

    @property
    def count(self) -> int:
        return len(self._jobs)
