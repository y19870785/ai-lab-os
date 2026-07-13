"""EpisodicMemory — Long-term event memory.

Manages episodic (event-based) memories with SQLite persistence.
Provides session-level and agent-level episode tracking.

Each episode records:
- What happened (events, interactions)
- When it happened (timestamp, session context)
- Who was involved (agent_id, session_id)
- How important it was (importance, metadata)

Designed to work with:
- MemoryManager (via MemoryStore interface)
- ConsolidationEngine (importance/decay/policy lifecycle)
- Future VectorStore (semantic search)

Usage:
    from core.memory.episodic import EpisodicMemory
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore

    store = SQLiteEpisodicStore("episodic.db")
    await store.initialize()
    episodic = EpisodicMemory(store=store, bus=get_bus())

    # Save an episode
    ep = await episodic.save_episode(
        session_id="sess_001",
        agent_id="agent_analyst",
        events=[{"type": "user_message", "content": "分析A股"}],
        summary="用户请求A股分析",
        importance=0.7,
    )

    # Retrieve episodes
    episodes = await episodic.retrieve_episode(session_id="sess_001")
    results = await episodic.query(agent_id="agent_analyst", top_k=5)
"""

from __future__ import annotations

from typing import Any

from core.memory.models import MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore


class EpisodicMemory:
    """High-level episodic memory manager.

    Wraps a MemoryStore (e.g., SQLiteEpisodicStore) with episode-specific
    convenience methods. Maintains event publishing for lifecycle integration.
    """

    def __init__(self, store: MemoryStore, bus=None) -> None:
        self._store = store
        self._bus = bus

    # ── Episode-specific API ──

    async def save_episode(
        self,
        session_id: str,
        agent_id: str,
        events: list[dict[str, Any]] | None = None,
        summary: str = "",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        item_id: str | None = None,
    ) -> MemoryItem:
        """Save a complete episode to episodic memory.

        Args:
            session_id: The session this episode belongs to.
            agent_id: The agent that produced this episode.
            events: List of event dicts that occurred.
            summary: Human-readable summary of the episode.
            importance: Importance score (0.0 ~ 1.0).
            metadata: Additional metadata (tags, source, etc.).
            item_id: Optional explicit ID (auto-generated if omitted).

        Returns:
            The saved MemoryItem.
        """
        content: dict[str, Any] = {
            "session_id": session_id,
            "agent_id": agent_id,
            "events": events or [],
            "summary": summary,
        }

        item_kw = {
            "memory_type": MemoryType.EPISODIC,
            "content": content,
            "importance": importance,
            "metadata": {
                **(metadata or {}),
                "action": "created",
                "session_id": session_id,
                "agent_id": agent_id,
            },
        }
        if item_id is not None:
            item_kw["id"] = item_id
        item = MemoryItem(**item_kw)

        await self._store.save(item)

        if self._bus:
            await self._publish_event("created", item.id, {
                "session_id": session_id,
                "agent_id": agent_id,
                "summary": summary[:200],
                "importance": importance,
            })

        return item

    async def retrieve_episode(
        self,
        episode_id: str | None = None,
        session_id: str | None = None,
    ) -> list[MemoryItem]:
        """Retrieve episodes by ID or session_id.

        Args:
            episode_id: Get a specific episode.
            session_id: Get all episodes for a session.

        Returns:
            List of matching MemoryItems.
        """
        if episode_id:
            item = await self._store.get(episode_id)
            return [item] if item else []

        if session_id:
            query = MemoryQuery(
                memory_type=MemoryType.EPISODIC,
                filters={"session_id": session_id},
                top_k=100,
            )
            return await self._store.query(query)

        return []

    async def query(
        self,
        agent_id: str | None = None,
        session_id: str | None = None,
        min_importance: float = 0.0,
        top_k: int = 10,
        time_range: tuple | None = None,
    ) -> list[MemoryItem]:
        """Query episodic memories with flexible filters.

        Args:
            agent_id: Filter by agent.
            session_id: Filter by session.
            min_importance: Minimum importance threshold.
            top_k: Max results.
            time_range: (start_datetime, end_datetime) tuple.

        Returns:
            List of matching MemoryItems.
        """
        filters: dict[str, Any] = {}
        if agent_id:
            filters["agent_id"] = agent_id
        if session_id:
            filters["session_id"] = session_id

        query = MemoryQuery(
            memory_type=MemoryType.EPISODIC,
            filters=filters,
            top_k=top_k,
            min_importance=min_importance,
            time_range=time_range,
        )

        results = await self._store.query(query)

        if self._bus:
            await self._publish_event("accessed", "", {
                "agent_id": agent_id,
                "session_id": session_id,
                "result_count": len(results),
            })

        return results

    async def delete(self, episode_id: str) -> bool:
        """Delete an episode by ID."""
        result = await self._store.delete(episode_id)
        if result and self._bus:
            await self._publish_event("deleted", episode_id, {})
        return result

    async def count(self) -> int:
        """Total episodic memory count."""
        return await self._store.count()

    async def delete_by_session(self, session_id: str) -> int:
        """Delete all episodes for a session. Returns count deleted."""
        items = await self.retrieve_episode(session_id=session_id)
        count = 0
        for item in items:
            if await self._store.delete(item.id):
                count += 1
                if self._bus:
                    await self._publish_event("deleted", item.id, {
                        "session_id": session_id,
                    })
        return count

    # ── Underlying store access ──

    @property
    def store(self) -> MemoryStore:
        """Access the underlying MemoryStore directly."""
        return self._store

    # ── Event publishing ──

    async def _publish_event(self, action: str, memory_id: str, extra: dict[str, Any]) -> None:
        if not self._bus:
            return
        from core.bus import Event
        event = Event(
            event_type=f"memory.{action}",
            source="memory.episodic",
            payload={
                "memory_id": memory_id,
                "memory_type": "episodic",
                **extra,
            },
        )
        await self._bus.publish(f"memory.{action}", event)