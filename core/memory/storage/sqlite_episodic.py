"""SQLite-based Episodic Memory Store.

Persists episodic memories in SQLite for long-term storage.
Supports filtering by time range, importance, agent_id, session_id.

Designed to work with MemoryStore interface and ConsolidationEngine.

Usage:
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore

    store = SQLiteEpisodicStore(db_path="episodic.db")
    await store.initialize()
    item = MemoryItem(memory_type=MemoryType.EPISODIC, content={...})
    await store.save(item)
    results = await store.query(MemoryQuery(...))
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.database.connection import ConnectionLease, transaction
from core.database.manager import DatabaseManager
from core.memory.models import MemoryFilter, MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore


class SQLiteEpisodicStore(MemoryStore):
    """SQLite-backed episodic memory store.

    Stores MemoryItem as JSON in SQLite rows.
    Supports:
    - CRUD via MemoryStore interface
    - Filtering by time_range, importance, metadata fields
    - Thread-safe with connection-per-operation
    """

    def __init__(
        self,
        db_path: str = "episodic.db",
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self._db_path = db_path
        self._db_manager = db_manager

    async def initialize(self) -> None:
        """Create table if not exists. Call before first use."""
        with self._lease() as conn, transaction(conn):
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL DEFAULT 'episodic',
                    content TEXT NOT NULL DEFAULT '{}',
                    importance REAL NOT NULL DEFAULT 0.5,
                    embedding TEXT,
                    timestamp TEXT NOT NULL,
                    ttl INTEGER,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_importance
                ON episodic_memories(importance)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_timestamp
                ON episodic_memories(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_type
                ON episodic_memories(memory_type)
            """)

    # ── MemoryStore interface ──

    async def save(self, item: MemoryItem) -> str:
        self._validate_type(item)
        with self._lease() as conn, transaction(conn):
            conn.execute(
                """INSERT OR REPLACE INTO episodic_memories
                (id, memory_type, content, importance, embedding, timestamp, ttl, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    item.id,
                    item.memory_type.value,
                    json.dumps(item.content, ensure_ascii=False),
                    item.importance,
                    json.dumps(item.embedding) if item.embedding else None,
                    item.timestamp.isoformat(),
                    item.ttl,
                    json.dumps(item.metadata, ensure_ascii=False),
                ),
            )
        return item.id

    async def batch_save(self, items: list[MemoryItem]) -> list[str]:
        ids = []
        with self._lease() as conn, transaction(conn):
            for item in items:
                self._validate_type(item)
                conn.execute(
                    """INSERT OR REPLACE INTO episodic_memories
                    (id, memory_type, content, importance, embedding, timestamp, ttl, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (
                        item.id,
                        item.memory_type.value,
                        json.dumps(item.content, ensure_ascii=False),
                        item.importance,
                        json.dumps(item.embedding) if item.embedding else None,
                        item.timestamp.isoformat(),
                        item.ttl,
                        json.dumps(item.metadata, ensure_ascii=False),
                    ),
                )
                ids.append(item.id)
        return ids

    async def get(self, id: str) -> MemoryItem | None:
        with self._lease() as conn:
            row = conn.execute(
                "SELECT * FROM episodic_memories WHERE id = ?", (id,)
            ).fetchone()
        return self._row_to_item(row) if row else None

    async def query(self, spec: MemoryQuery) -> list[MemoryItem]:
        conditions = []
        params: list[Any] = []

        conditions.append("memory_type = ?")
        params.append(spec.memory_type.value if spec.memory_type else MemoryType.EPISODIC.value)

        if spec.min_importance > 0:
            conditions.append("importance >= ?")
            params.append(spec.min_importance)

        if spec.time_range:
            start, end = spec.time_range
            conditions.append("timestamp >= ? AND timestamp <= ?")
            params.append(start.isoformat())
            params.append(end.isoformat())

        # Metadata filters
        for key, value in spec.filters.items():
            if key in ("agent_id", "session_id", "source"):
                conditions.append(f"json_extract(content, '$.{key}') = ?")
                params.append(str(value))

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM episodic_memories WHERE {where_clause} ORDER BY importance DESC LIMIT ?"
        params.append(spec.top_k)

        with self._lease() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [self._row_to_item(r) for r in rows]

    async def delete(self, id: str) -> bool:
        with self._lease() as conn, transaction(conn):
            cursor = conn.execute("DELETE FROM episodic_memories WHERE id = ?", (id,))
            return cursor.rowcount > 0

    async def count(self, filter: MemoryFilter | None = None) -> int:
        conditions = []
        params: list[Any] = []
        conditions.append("memory_type = 'episodic'")

        if filter:
            if filter.min_importance > 0:
                conditions.append("importance >= ?")
                params.append(filter.min_importance)
            if filter.time_after:
                conditions.append("timestamp >= ?")
                params.append(filter.time_after.isoformat())
            if filter.time_before:
                conditions.append("timestamp <= ?")
                params.append(filter.time_before.isoformat())

        where = " AND ".join(conditions)
        with self._lease() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM episodic_memories WHERE {where}", params
            ).fetchone()
            return row[0] if row else 0

    # ── Maintenance ──

    async def close(self) -> None:
        pass

    async def vacuum(self) -> None:
        """Rebuild database to reclaim space."""
        with self._lease() as conn:
            conn.execute("VACUUM")

    # ── Internal helpers ──

    def _lease(self) -> ConnectionLease:
        if self._db_manager:
            return self._db_manager.lease("episodic", self._db_path)
        return ConnectionLease.standalone(self._db_path)

    def _validate_type(self, item: MemoryItem) -> None:
        if item.memory_type not in (MemoryType.EPISODIC,):
            raise ValueError(
                f"SQLiteEpisodicStore only accepts EPISODIC type, got {item.memory_type}"
            )

    @staticmethod
    def _row_to_item(row: Any) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            content=json.loads(row["content"]) if row["content"] else {},
            importance=row["importance"],
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            ttl=row["ttl"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    @property
    def db_path(self) -> str:
        return self._db_path
