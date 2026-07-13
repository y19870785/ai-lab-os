"""Agent 记忆画像。定义 Agent 如何使用 Memory Layer。

每个 Agent 可以声明需要什么类型的记忆、检索策略和写入策略。
"""

from __future__ import annotations

from pydantic import BaseModel

from core.memory.protocol import MemoryType


class MemoryProfile(BaseModel):
    """Agent 记忆画像。定义 Agent 如何关联和使用记忆系统。"""
    agent_id: str = ""

    # 声明的记忆需求
    enabled_memories: list[MemoryType] = [
        MemoryType.SESSION,
        MemoryType.EPISODIC,
    ]

    # 检索策略
    recall_on_start: bool = True
    max_recall_items: int = 20
    min_recall_importance: float = 0.3

    # 写入策略
    auto_store_episodic: bool = True
    auto_extract_semantic: bool = False

    # 上下文窗口管理
    max_context_tokens: int = 8000
    context_ranking: str = "importance"
