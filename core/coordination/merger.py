"""Result Merger —— 合并多个 Agent 的输出。

支持：
- RuleBasedMerger：按规则拼接（初期）
- 预留：LLMMerger（LLM 融合）
"""

from __future__ import annotations

from typing import Any

from core.coordination.models import CollaborationContext
from core.coordination.protocol import MergerProtocol


class RuleBasedMerger(MergerProtocol):
    """规则合并器 —— 按 Agent 顺序拼接结果。"""

    def strategy(self) -> str:
        return "rule"

    async def merge(self, results: dict[str, Any], context: CollaborationContext) -> str:
        """合并多个 Agent 的输出为统一文本。

        简单策略：按 agent_id 排序，逐个拼接。
        """
        parts = []
        for agent_id in sorted(results.keys()):
            result = results[agent_id]
            answer = ""
            if isinstance(result, dict):
                answer = result.get("answer", "") or result.get("output", "") or str(result)
            elif isinstance(result, str):
                answer = result
            else:
                answer = str(result)
            if answer:
                parts.append(f"[{agent_id}]: {answer}")

        merged = "\n\n".join(parts) if parts else "(no results)"
        return merged


class PriorityMerger(MergerProtocol):
    """优先级合并器 —— 高优先级 Agent 结果优先。"""

    def strategy(self) -> str:
        return "priority"

    async def merge(self, results: dict[str, Any], context: CollaborationContext) -> str:
        """按 agent 在 plan 中的顺序合并结果。"""
        plan_order = [step.get("agent_id", "") for step in context.plan if step.get("agent_id")]
        ordered_results = []
        seen = set()

        # 先按 plan 顺序
        for agent_id in plan_order:
            if agent_id in results and agent_id not in seen:
                ordered_results.append((agent_id, results[agent_id]))
                seen.add(agent_id)

        # 剩余 agent
        for agent_id in sorted(results.keys()):
            if agent_id not in seen:
                ordered_results.append((agent_id, results[agent_id]))

        parts = []
        for agent_id, result in ordered_results:
            answer = ""
            if isinstance(result, dict):
                answer = result.get("answer", "") or str(result)
            else:
                answer = str(result)
            if answer:
                parts.append(f"[{agent_id}]: {answer}")

        return "\n\n".join(parts) if parts else "(no results)"
