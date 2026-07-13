"""Workflow 配置"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class WorkflowConfig:
    """Workflow Runtime 配置"""
    default_timeout: int = 300  # 单个 Workflow 默认超时（秒）
    step_timeout: int = 60  # 单步骤默认超时（秒）
    max_retries: int = 3  # 单步骤最大重试次数
    checkpoint_enabled: bool = True
    auto_resume: bool = True
    max_parallel_steps: int = 5
    planner_type: str = "rule"  # rule / llm / tree / graph
    memory_enabled: bool = True
    knowledge_enabled: bool = True
    event_publish_enabled: bool = True
