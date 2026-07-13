"""Consolidation Engine 单元测试。

覆盖：
- ImportanceScorer 评分计算（基础/频率/时效/置信度）
- MemoryDecay 衰减计算
- ConsolidationPolicy 策略决策（保留/压缩/晋升/删除）
- ConsolidationEngine 周期执行
- 事件集成（memory.consolidated）
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from core.bus import Event, get_bus, reset_bus
from core.memory import (
    MemoryItem,
    MemoryQuery,
    MemoryType,
    get_manager,
    reset_manager,
)
from core.memory.consolidation import ConsolidationEngine, ConsolidationResult
from core.memory.decay import DecayConfig, MemoryDecay
from core.memory.importance import ImportanceConfig, ImportanceScorer
from core.memory.policy import (
    ConsolidationAction,
    ConsolidationPolicy,
    ConsolidationThresholds,
    PolicyDecision,
)
from core.memory.session import SessionMemory


# ═══════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════

def _make_item(
    memory_type: MemoryType = MemoryType.EPISODIC,
    importance: float = 0.5,
    content: dict | None = None,
    item_id: str | None = None,
) -> MemoryItem:
    return MemoryItem(
        id=item_id or _make_item._counter(),
        memory_type=memory_type,
        importance=importance,
        content=content or {"text": "test memory"},
    )
_make_item._counter_val = 0
_make_item._counter = lambda: (
    setattr(_make_item, "_counter_val", _make_item._counter_val + 1)
    or f"test_{_make_item._counter_val}"
)


class InMemoryTestStore:
    """Minimal in-memory store for testing consolidation."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    async def save(self, item: MemoryItem) -> str:
        self._items[item.id] = item
        return item.id

    async def batch_save(self, items: list[MemoryItem]) -> list[str]:
        return [await self.save(i) for i in items]

    async def get(self, id: str) -> MemoryItem | None:
        return self._items.get(id)

    async def query(self, spec: MemoryQuery) -> list[MemoryItem]:
        results = list(self._items.values())
        if spec.min_importance > 0:
            results = [r for r in results if r.importance >= spec.min_importance]
        results.sort(key=lambda x: x.importance, reverse=True)
        return results[: spec.top_k]

    async def delete(self, id: str) -> bool:
        return self._items.pop(id, None) is not None

    async def count(self, filter=None) -> int:
        return len(self._items)

    @property
    def items(self) -> dict[str, MemoryItem]:
        return self._items


# ═══════════════════════════════════════════════════════════════
# 1. ImportanceScorer
# ═══════════════════════════════════════════════════════════════

class TestImportanceScorer:

    def test_calculate_base_only(self):
        """默认配置下，base 权重占主导。"""
        scorer = ImportanceScorer()
        item = _make_item(importance=0.8)
        score = scorer.calculate(item, now=1000.0)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # 高基础分应该得到较高综合分

    def test_calculate_low_importance(self):
        """低重要性记忆的综合分应当低。"""
        scorer = ImportanceScorer()
        item = _make_item(importance=0.1)
        score = scorer.calculate(item, now=1000.0)
        assert score < 0.4

    def test_frequency_factor_saturation(self):
        """多次访问应该提升评分，但存在饱和。"""
        scorer = ImportanceScorer()
        item = _make_item(importance=0.3)
        score_once = scorer.calculate(item, access_count=1, now=1000.0)
        score_many = scorer.calculate(item, access_count=20, now=1000.0)
        assert score_many > score_once

    def test_recency_decay(self):
        """近期访问过的记忆评分更高。"""
        scorer = ImportanceScorer()
        item = _make_item(importance=0.5)
        now = time.time()
        score_recent = scorer.calculate(item, last_access_ts=now, now=now)
        score_old = scorer.calculate(item, last_access_ts=now - 86400 * 7, now=now)
        assert score_recent > score_old

    def test_confidence_boost(self):
        """高置信度的记忆评分更高。"""
        scorer = ImportanceScorer()
        item_low = _make_item(importance=0.5)
        item_low.metadata["confidence"] = 0.2
        item_high = _make_item(importance=0.5)
        item_high.metadata["confidence"] = 0.9
        score_low = scorer.calculate(item_low, now=1000.0)
        score_high = scorer.calculate(item_high, now=1000.0)
        assert score_high > score_low

    def test_record_access(self):
        """record_access 应增加访问计数。"""
        scorer = ImportanceScorer()
        scorer.record_access("mem_1")
        scorer.record_access("mem_1")
        assert scorer.get_access_count("mem_1") == 2
        assert scorer.get_last_access("mem_1") is not None

    def test_custom_config(self):
        """自定义权重配置应生效。"""
        config = ImportanceConfig(w_base=1.0, w_frequency=0.0, w_recency=0.0, w_confidence=0.0)
        scorer = ImportanceScorer(config=config)
        item = _make_item(importance=0.7)
        score = scorer.calculate(item, now=1000.0)
        assert abs(score - 0.7) < 0.01

    def test_reset(self):
        """reset 应清除追踪状态。"""
        scorer = ImportanceScorer()
        scorer.record_access("mem_1")
        scorer.reset("mem_1")
        assert scorer.get_access_count("mem_1") == 0
        scorer.record_access("mem_2")
        scorer.reset()
        assert scorer.get_access_count("mem_2") == 0


# ═══════════════════════════════════════════════════════════════
# 2. MemoryDecay
# ═══════════════════════════════════════════════════════════════

class TestMemoryDecay:

    def test_fresh_memory(self):
        """刚创建的记忆衰减因子应为 1.0。"""
        decay = MemoryDecay()
        now = time.time()
        factor = decay.calculate(created_at=now, now=now)
        assert abs(factor - 1.0) < 0.01

    def test_half_life(self):
        """经过一个半衰期后因子约为 0.5。"""
        decay = MemoryDecay(config=DecayConfig(half_life=3600.0))
        now = time.time()
        factor = decay.calculate(created_at=now - 3600.0, now=now)
        assert abs(factor - 0.5) < 0.05

    def test_old_memory(self):
        """非常老的记忆应该接近 0。"""
        decay = MemoryDecay(config=DecayConfig(half_life=3600.0))
        now = time.time()
        factor = decay.calculate(created_at=now - 3600 * 24 * 30, now=now)
        assert factor < 0.01

    def test_is_decayed(self):
        """is_decayed 应正确判断衰减状态。"""
        decay = MemoryDecay(config=DecayConfig(half_life=1.0, min_strength=0.1))
        fresh = _make_item()
        time.sleep(0.1)  # still very fresh
        assert not decay.is_decayed(fresh, now=time.time())

        # Simulate old memory
        import datetime
        old = _make_item()
        old.timestamp = datetime.datetime.now() - datetime.timedelta(days=30)
        assert decay.is_decayed(old, now=time.time())

    def test_effective_strength(self):
        """effective_strength = importance * decay_factor。"""
        decay = MemoryDecay()
        now = time.time()
        item = _make_item(importance=0.8)
        strength = decay.effective_strength(item, 0.8, now=now)
        assert abs(strength - 0.8) < 0.01

    def test_custom_half_life(self):
        """超大半衰期应使衰减极慢。"""
        decay = MemoryDecay(config=DecayConfig(half_life=86400 * 365))
        now = time.time()
        factor = decay.calculate(created_at=now - 86400, now=now)
        assert factor > 0.95


# ═══════════════════════════════════════════════════════════════
# 3. ConsolidationPolicy
# ═══════════════════════════════════════════════════════════════

class TestConsolidationPolicy:

    def test_retain_high_score(self):
        """高重要度 + 新鲜的记忆应保留。"""
        policy = ConsolidationPolicy()
        item = _make_item(memory_type=MemoryType.EPISODIC)
        decision = policy.evaluate(item, importance_score=0.8, decay_factor=0.9, access_count=2)
        assert decision.action == ConsolidationAction.RETAIN

    def test_promote_high_value(self):
        """高重要度 + 高频访问 + 新鲜的记忆应晋升。"""
        policy = ConsolidationPolicy()
        item = _make_item(memory_type=MemoryType.EPISODIC)
        decision = policy.evaluate(item, importance_score=0.85, decay_factor=0.9, access_count=5)
        assert decision.action == ConsolidationAction.PROMOTE

    def test_compress_medium_score(self):
        """中等重要度的记忆应压缩。"""
        policy = ConsolidationPolicy()
        item = _make_item(memory_type=MemoryType.EPISODIC)
        decision = policy.evaluate(item, importance_score=0.35, decay_factor=0.6, access_count=1)
        assert decision.action == ConsolidationAction.COMPRESS

    def test_delete_low_score(self):
        """低重要度 + 衰减的记忆应删除。"""
        policy = ConsolidationPolicy()
        item = _make_item(memory_type=MemoryType.EPISODIC)
        decision = policy.evaluate(item, importance_score=0.1, decay_factor=0.3, access_count=1)
        assert decision.action == ConsolidationAction.DELETE

    def test_session_never_promote(self):
        """SESSION 类型的记忆不应晋升（而是删除或保留）。"""
        policy = ConsolidationPolicy()
        item = _make_item(memory_type=MemoryType.SESSION, importance=0.9)
        decision = policy.evaluate(item, importance_score=0.9, decay_factor=0.9, access_count=10)
        assert decision.action != ConsolidationAction.PROMOTE

    def test_session_decayed_delete(self):
        """SESSION 记忆衰减后应删除。"""
        policy = ConsolidationPolicy()
        item = _make_item(memory_type=MemoryType.SESSION)
        decision = policy.evaluate(item, importance_score=0.1, decay_factor=0.05, access_count=1)
        assert decision.action == ConsolidationAction.DELETE

    def test_evaluate_batch(self):
        """批量评估应正确处理多个记忆。"""
        policy = ConsolidationPolicy()
        items = [
            (_make_item(importance=0.9), 0.9, 0.9, 5),
            (_make_item(importance=0.1), 0.1, 0.2, 1),
            (_make_item(importance=0.4), 0.4, 0.6, 2),
        ]
        decisions = policy.evaluate_batch(items)
        assert len(decisions) == 3
        actions = [d.action for d in decisions]
        assert ConsolidationAction.PROMOTE in actions
        assert ConsolidationAction.DELETE in actions

    def test_custom_thresholds(self):
        """自定义阈值应生效。"""
        thresholds = ConsolidationThresholds(
            promote_min_score=0.9,
            delete_max_score=0.3,
        )
        policy = ConsolidationPolicy(thresholds=thresholds)
        item = _make_item(importance=0.85)
        # 0.85 < 0.9 -> should not promote
        decision = policy.evaluate(item, importance_score=0.85, decay_factor=0.9, access_count=5)
        assert decision.action != ConsolidationAction.PROMOTE

    def test_decision_has_reasons(self):
        """决策应包含理由。"""
        policy = ConsolidationPolicy()
        item = _make_item()
        decision = policy.evaluate(item, importance_score=0.1, decay_factor=0.2, access_count=1)
        assert len(decision.reasons) > 0
        assert "delete" in decision.reasons[0].lower()


# ═══════════════════════════════════════════════════════════════
# 4. ConsolidationEngine
# ═══════════════════════════════════════════════════════════════

class TestConsolidationEngine:

    @pytest.mark.asyncio
    async def test_empty_cycle(self):
        """空存储的合并周期应正常完成。"""
        bus = get_bus()
        await bus.start()
        try:
            engine = ConsolidationEngine(bus=bus)
            store = InMemoryTestStore()
            engine.register_store(MemoryType.EPISODIC, store)

            result = await engine.run_cycle()
            assert result.evaluated == 0
            assert result.errors == []
            assert result.duration_ms >= 0
        finally:
            await bus.stop()
            reset_bus()

    @pytest.mark.asyncio
    async def test_cycle_with_items(self):
        """包含记忆的存储应正确评估。"""
        bus = get_bus()
        await bus.start()
        try:
            engine = ConsolidationEngine(bus=bus)
            store = InMemoryTestStore()

            # Add high and low importance items
            await store.save(_make_item(importance=0.9))
            await store.save(_make_item(importance=0.1))
            await store.save(_make_item(importance=0.4))

            engine.register_store(MemoryType.EPISODIC, store)

            result = await engine.run_cycle()
            assert result.evaluated == 3
            assert result.retained + result.compressed + result.promoted + result.deleted == 3
        finally:
            await bus.stop()
            reset_bus()

    @pytest.mark.asyncio
    async def test_cycle_deletes_decayed(self):
        """衰减的记忆应在合并周期中被删除。"""
        bus = get_bus()
        await bus.start()
        try:
            engine = ConsolidationEngine(bus=bus)
            store = InMemoryTestStore()

            # Override decay to fast decay for testing
            engine._decay = MemoryDecay(config=DecayConfig(half_life=0.001, min_strength=0.001))

            item = _make_item(importance=0.1, item_id="to_delete")
            await store.save(item)

            engine.register_store(MemoryType.EPISODIC, store)

            # Wait for decay
            await asyncio.sleep(0.05)

            result = await engine.run_cycle()
            assert result.deleted > 0
            assert await store.get("to_delete") is None
        finally:
            await bus.stop()
            reset_bus()

    @pytest.mark.asyncio
    async def test_event_published(self):
        """合并周期完成后应发布 memory.consolidated 事件。"""
        bus = get_bus()
        await bus.start()

        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        await bus.subscribe("memory.consolidated", handler)

        try:
            engine = ConsolidationEngine(bus=bus)
            store = InMemoryTestStore()
            await store.save(_make_item(importance=0.5))
            engine.register_store(MemoryType.EPISODIC, store)

            result = await engine.run_cycle()
            assert result.evaluated > 0
            assert len(received_events) >= 1
            evt = received_events[0]
            assert evt.event_type == "memory.consolidated"
            assert evt.source == "memory.consolidation"
        finally:
            await bus.stop()
            reset_bus()

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """session_cleanup 应正确处理会话记忆。"""
        bus = get_bus()
        await bus.start()
        try:
            engine = ConsolidationEngine(bus=bus)
            store = InMemoryTestStore()

            await store.save(_make_item(
                memory_type=MemoryType.SESSION, importance=0.9, item_id="keep_me"
            ))
            await store.save(_make_item(
                memory_type=MemoryType.SESSION, importance=0.05, item_id="delete_me"
            ))

            engine.register_store(MemoryType.SESSION, store)

            result = await engine.run_session_cleanup(store)
            assert result.evaluated > 0
        finally:
            await bus.stop()
            reset_bus()

    @pytest.mark.asyncio
    async def test_multiple_stores(self):
        """多个存储应分别被合并。"""
        bus = get_bus()
        await bus.start()
        try:
            engine = ConsolidationEngine(bus=bus)
            store1 = InMemoryTestStore()
            store2 = InMemoryTestStore()

            await store1.save(_make_item(importance=0.5))
            await store2.save(_make_item(importance=0.8))
            await store2.save(_make_item(importance=0.1))

            engine.register_store(MemoryType.EPISODIC, store1)
            engine.register_store(MemoryType.SEMANTIC, store2)

            result = await engine.run_cycle()
            assert result.evaluated == 3
        finally:
            await bus.stop()
            reset_bus()

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """后台循环应正确启动和停止。"""
        bus = get_bus()
        await bus.start()
        try:
            engine = ConsolidationEngine(bus=bus, cycle_interval=0.1)
            store = InMemoryTestStore()
            await store.save(_make_item(importance=0.5))
            engine.register_store(MemoryType.EPISODIC, store)

            await engine.start(interval=0.1)
            assert engine.is_running

            await asyncio.sleep(0.25)
            await engine.stop()
            assert not engine.is_running
        finally:
            await bus.stop()
            reset_bus()
