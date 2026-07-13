"""DecisionMemory — Decision reasoning chain memory.

Records agent decision processes with reasoning chains and outcome tracking.
Append-only design; decisions are immutable once written.

Usage:
    from core.memory.decision import DecisionMemory
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore

    store = SQLiteDecisionStore("decision.db")
    await store.initialize()
    dm = DecisionMemory(store=store, bus=get_bus())
    decision = await dm.save_decision(
        agent_id="analyst", session_id="sess_1",
        trigger="用户询问投资建议",
        alternatives=[{"name": "方案A", "pros": [...]}, {"name": "方案B", "pros": [...]}],
        reasoning_chain=["分析当前市场", "对比两个方案", "选择方案A"],
        chosen="方案A", importance=0.8,
    )
    ok = await dm.update_outcome("dec_001", "SUCCESS", note="方案A达到预期收益")
"""

from __future__ import annotations

from typing import Any

from core.memory.models import MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore
from core.memory.storage.sqlite_decision import SQLiteDecisionStore


class DecisionMemory:
    """High-level decision memory manager for reasoning chain storage."""

    def __init__(self, store: MemoryStore, bus=None) -> None:
        self._store = store
        self._bus = bus

    async def save_decision(
        self,
        agent_id: str,
        session_id: str,
        trigger: str,
        episode_id: str | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        reasoning_chain: list[str] | None = None,
        chosen: str = "",
        outcome: str = "PENDING",
        decision_type: str = "analysis",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        item_id: str | None = None,
    ) -> MemoryItem:
        content = {
            "agent_id": agent_id, "session_id": session_id,
            "trigger": trigger, "decision_type": decision_type, "episode_id": episode_id or "",
            "alternatives": alternatives or [],
            "reasoning_chain": reasoning_chain or [],
            "chosen": chosen, "outcome": outcome,
        }
        item = MemoryItem(id=item_id, memory_type=MemoryType.DECISION,
                          content=content, importance=importance,
                          metadata={**(metadata or {}), "action": "created",
                                    "agent_id": agent_id, "session_id": session_id})
        await self._store.save(item)
        if self._bus:
            await self._publish("created", item.id,
                                {"agent_id": agent_id, "decision_type": decision_type})
        return item

    async def query(
        self,
        agent_id: str | None = None,
        outcome: str | None = None,
        decision_type: str | None = None,
        min_importance: float = 0.0,
        top_k: int = 10,
    ) -> list[MemoryItem]:
        filters: dict[str, Any] = {}
        if agent_id: filters["agent_id"] = agent_id
        if outcome: filters["outcome"] = outcome
        if decision_type: filters["decision_type"] = decision_type
        q = MemoryQuery(memory_type=MemoryType.DECISION, filters=filters,
                        top_k=top_k, min_importance=min_importance)
        return await self._store.query(q)

    async def get(self, decision_id: str) -> MemoryItem | None:
        return await self._store.get(decision_id)

    async def update_outcome(self, decision_id: str, outcome: str, note: str = "") -> bool:
        if isinstance(self._store, SQLiteDecisionStore):
            return await self._store.update_outcome(decision_id, outcome, note)
        item = await self._store.get(decision_id)
        if item is None:
            return False
        item.content["outcome"] = outcome
        if note:
            item.content.setdefault("outcome_notes", []).append(
                {"time": __import__("datetime").datetime.now().isoformat(), "note": note}
            )
        await self._store.save(item)
        if self._bus:
            await self._publish("updated", decision_id, {"outcome": outcome})
        return True

    async def query_by_outcome(self, outcome: str, top_k: int = 10) -> list[MemoryItem]:
        return await self.query(outcome=outcome, top_k=top_k)

    async def delete(self, decision_id: str) -> bool:
        r = await self._store.delete(decision_id)
        if r and self._bus:
            await self._publish("deleted", decision_id, {})
        return r

    async def count(self) -> int:
        return await self._store.count()

    @property
    def store(self) -> MemoryStore:
        return self._store

    async def _publish(self, action: str, memory_id: str, extra: dict[str, Any]) -> None:
        if not self._bus:
            return
        from core.bus import Event
        await self._bus.publish(f"memory.{action}", Event(
            event_type=f"memory.{action}", source="memory.decision",
            payload={"memory_id": memory_id, "memory_type": "decision", **extra},
        ))
