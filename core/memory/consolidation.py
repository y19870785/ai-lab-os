"""Consolidation Engine.

Memory life-cycle management system that periodically evaluates
all memories and applies consolidation policies.

The consolidation engine:
1. Scans memory stores for items that need consolidation
2. Calculates importance scores and decay factors
3. Applies consolidation policy decisions
4. Executes actions (retain/compress/promote/delete)
5. Publishes memory.consolidated events

Usage:
    from core.memory.consolidation import ConsolidationEngine
    from core.bus import get_bus

    engine = ConsolidationEngine(bus=get_bus())
    engine.register_store(MemoryType.EPISODIC, episodic_store)

    # Run one cycle
    results = await engine.run_cycle()

    # Or run continuously
    await engine.start(interval=300)  # every 5 minutes
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from core.memory.decay import MemoryDecay
from core.memory.importance import ImportanceScorer
from core.memory.models import MemoryItem, MemoryQuery, MemoryType
from core.memory.policy import ConsolidationAction, ConsolidationPolicy, PolicyDecision
from core.memory.protocol import MemoryStore


@dataclass
class ConsolidationResult:
    """Result of a single consolidation cycle."""
    evaluated: int = 0
    retained: int = 0
    compressed: int = 0
    promoted: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)
    decisions: list[PolicyDecision] = field(default_factory=list)
    duration_ms: float = 0.0


class CompressCallback:
    """Callback signature for memory compression.

    Implementing modules should register a compression function.
    Args:
        item: The memory item to compress.
    Returns:
        A compressed/summarized version of the content, or None if compression fails.
    """
    pass


class PromoteCallback:
    """Callback signature for promoting a memory to Knowledge Layer.

    Implementing modules should register a promotion function.
    Args:
        item: The memory item to promote.
    Returns:
        knowledge_id if promotion succeeds, None otherwise.
    """
    pass


# ── Role boundaries ──
# ImportanceScorer  → calculates importance (what to keep)
# MemoryDecay        → calculates time decay (when to forget)
# ConsolidationPolicy → decides action (RETAIN/COMPRESS/PROMOTE/DELETE)
# ConsolidationEngine → orchestrates cycle + publishes events (how to execute)
# ── End role boundaries ──

class ConsolidationEngine:
    """Memory consolidation engine.

    Manages memory life-cycle through periodic consolidation cycles.
    """

    def __init__(
        self,
        bus=None,
        importance_scorer: ImportanceScorer | None = None,
        decay_calc: MemoryDecay | None = None,
        policy: ConsolidationPolicy | None = None,
        cycle_interval: int = 300,
    ) -> None:
        self._bus = bus
        self._scorer = importance_scorer or ImportanceScorer()
        self._decay = decay_calc or MemoryDecay()
        self._policy = policy or ConsolidationPolicy()
        self._cycle_interval = cycle_interval
        self._stores: dict[MemoryType, MemoryStore] = {}

        # External callbacks
        self._compress_fn: Callable[[MemoryItem], dict[str, Any] | None] | None = None
        self._promote_fn: Callable[[MemoryItem], str | None] | None = None

        # Running state
        self._running = False
        self._task: asyncio.Task | None = None

    # ── Registration ──

    def register_store(self, memory_type: MemoryType, store: MemoryStore) -> None:
        """Register a memory store for consolidation."""
        self._stores[memory_type] = store

    def register_compress_fn(
        self, fn: Callable[[MemoryItem], dict[str, Any] | None]
    ) -> None:
        """Register a compression callback."""
        self._compress_fn = fn

    def register_promote_fn(
        self, fn: Callable[[MemoryItem], str | None]
    ) -> None:
        """Register a promotion callback."""
        self._promote_fn = fn

    # ── Cycle execution ──

    async def run_cycle(self) -> ConsolidationResult:
        """Run a single consolidation cycle across all registered stores.

        Returns:
            ConsolidationResult with stats and decisions.
        """
        start = time.time()
        result = ConsolidationResult()

        for memory_type, store in self._stores.items():
            if memory_type == MemoryType.SESSION:
                # Session memory is ephemeral; skip in regular consolidation
                continue
            try:
                await self._consolidate_store(memory_type, store, result)
            except Exception as e:
                err = f"Error consolidating {memory_type.value}: {e}"
                result.errors.append(err)

        result.duration_ms = (time.time() - start) * 1000

        # Publish consolidation event
        if self._bus:
            await self._publish_consolidation_event(result)

        return result

    async def run_session_cleanup(self, session_store: MemoryStore) -> ConsolidationResult:
        """Run a cleanup cycle specifically for session memories."""
        start = time.time()
        result = ConsolidationResult()

        try:
            items = await session_store.query(
                MemoryQuery(memory_type=MemoryType.SESSION, top_k=1000)
            )
            now = time.time()

            for item in items:
                score = self._scorer.calculate(item, now=now)
                decay = self._decay.calculate_from_item(item, now)
                access_count = self._scorer.get_access_count(item.id)

                decision = self._policy.evaluate(item, score, decay, access_count)
                result.decisions.append(decision)
                result.evaluated += 1

                if decision.action == ConsolidationAction.DELETE:
                    await session_store.delete(item.id)
                    result.deleted += 1
                else:
                    result.retained += 1
        except Exception as e:
            result.errors.append(f"Session cleanup error: {e}")

        result.duration_ms = (time.time() - start) * 1000
        if self._bus:
            await self._publish_consolidation_event(result)
        return result

    # ── Background loop ──

    async def start(self, interval: int | None = None) -> None:
        """Start the background consolidation loop.

        Args:
            interval: Seconds between cycles (default: self._cycle_interval).
        """
        if self._running:
            return

        self._running = True
        self._cycle_interval = interval or self._cycle_interval
        self._task = asyncio.create_task(self._loop())
        if self._bus:
            await self._publish_event("consolidation.started", {"interval": self._cycle_interval})

    async def stop(self) -> None:
        """Stop the background consolidation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._bus:
            await self._publish_event("consolidation.stopped", {})

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Internal ──

    async def _loop(self) -> None:
        """Background loop: run consolidation at regular intervals."""
        while self._running:
            try:
                result = await self.run_cycle()
                if result.errors:
                    # Log errors but keep running
                    pass
            except asyncio.CancelledError:
                break
            except Exception:
                pass

            await asyncio.sleep(self._cycle_interval)

    async def _consolidate_store(
        self,
        memory_type: MemoryType,
        store: MemoryStore,
        result: ConsolidationResult,
    ) -> None:
        """Run consolidation on a single memory store."""
        items = await store.query(
            MemoryQuery(memory_type=memory_type, top_k=1000)
        )
        now = time.time()

        for item in items:
            score = self._scorer.calculate(item, now=now)
            decay = self._decay.calculate_from_item(item, now)
            access_count = self._scorer.get_access_count(item.id)

            decision = self._policy.evaluate(item, score, decay, access_count)
            result.decisions.append(decision)
            result.evaluated += 1

            action = decision.action

            if action == ConsolidationAction.RETAIN:
                result.retained += 1

            elif action == ConsolidationAction.COMPRESS:
                success = await self._do_compress(item, store)
                if success:
                    result.compressed += 1

            elif action == ConsolidationAction.PROMOTE:
                success = await self._do_promote(item, store)
                if success:
                    result.promoted += 1

            elif action == ConsolidationAction.DELETE:
                await store.delete(item.id)
                result.deleted += 1

    async def _do_compress(self, item: MemoryItem, store: MemoryStore) -> bool:
        """Compress a memory item. Keeps the original metadata, condenses content."""
        if self._compress_fn:
            compressed_content = self._compress_fn(item)
            if compressed_content is not None:
                item.content = compressed_content
                item.metadata["consolidated"] = True
                item.metadata["consolidation_action"] = "compressed"
                await store.save(item)
                return True
        # Fallback: mark as compressed (keep truncated)
        item.metadata["consolidated"] = True
        item.metadata["consolidation_action"] = "compressed"
        item.metadata["original_size"] = len(str(item.content))
        await store.save(item)
        return True

    async def _do_promote(self, item: MemoryItem, store: MemoryStore) -> bool:
        await self._publish_memory_promoted(item)
        """Promote a memory to Knowledge Layer."""
        if self._promote_fn:
            knowledge_id = self._promote_fn(item)
            if knowledge_id is not None:
                item.metadata["consolidated"] = True
                item.metadata["consolidation_action"] = "promoted"
                item.metadata["knowledge_id"] = knowledge_id
                await store.save(item)
                return True

        # No promote callback registered; downgrade to retain
        item.metadata["consolidated"] = True
        item.metadata["consolidation_action"] = "promote_pending"
        await store.save(item)
        return False

    async def _publish_memory_promoted(self, item: MemoryItem) -> None:
        """Publish memory.promoted event."""
        if not self._bus:
            return
        from core.bus.memory_events import make_memory_event
        event = make_memory_event(
            event_type="memory.promoted",
            memory_id=item.id,
            memory_type=item.memory_type.value,
            source="memory.consolidation",
            extra={"importance": item.importance},
        )
        await self._bus.publish("memory.promoted", event)

    # ── Event publishing ──

    async def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish a consolidation lifecycle event."""
        if not self._bus:
            return
        from core.bus import Event
        event = Event(
            event_type=f"consolidation.{event_type}",
            source="memory.consolidation",
            payload=data,
        )
        await self._bus.publish(f"memory.{event_type}", event)

    async def _publish_consolidation_event(self, result: ConsolidationResult) -> None:
        """Publish consolidation cycle result event."""
        if not self._bus:
            return
        from core.bus import Event
        event = Event(
            event_type="memory.consolidated",
            source="memory.consolidation",
            payload={
                "evaluated": result.evaluated,
                "retained": result.retained,
                "compressed": result.compressed,
                "promoted": result.promoted,
                "deleted": result.deleted,
                "duration_ms": result.duration_ms,
                "errors": result.errors,
            },
        )
        await self._bus.publish("memory.consolidated", event)
