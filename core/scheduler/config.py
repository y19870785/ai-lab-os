"""Scheduler 配置"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SchedulerConfig:
    """Scheduler Runtime 配置"""
    tick_interval: float = 1.0  # 调度循环间隔（秒）
    max_concurrent_jobs: int = 10
    default_timeout: int = 300
    persistence_enabled: bool = True
    db_path: str = "scheduler.db"
    event_publish_enabled: bool = True
    auto_recover: bool = True  # 重启后自动恢复未完成任务
    failure_threshold: int = 3
    shutdown_timeout: float = 5.0
    cancel_running_jobs_on_shutdown: bool = True
