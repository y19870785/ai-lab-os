"""Task 配置"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TaskConfig:
    """Task Runtime 配置"""
    default_timeout: int = 600
    max_retries: int = 3
    max_parallel_workflows: int = 5
    max_depth: int = 10  # 最大嵌套深度
    checkpoint_interval: int = 1  # 每 N 个 Workflow 保存一次快照
    event_publish_enabled: bool = True
    memory_integration_enabled: bool = True
    knowledge_integration_enabled: bool = True
