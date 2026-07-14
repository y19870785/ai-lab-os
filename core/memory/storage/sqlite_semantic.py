"""SQLite-based Semantic Memory Store.

Persists semantic (entity-relation) memories in SQLite.
Supports entity CRUD, relation management, and graph traversal.

Usage:
    from core.memory.storage.sqlite_semantic import SQLiteSemanticStore

    store = SQLiteSemanticStore(db_path="semantic.db")
    await store.initialize()
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

from core.database.connection import ConnectionLease, transaction
from core.database.manager import DatabaseManager
from core.memory.models import MemoryFilter, MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore


class SQLiteSemanticStore(MemoryStore):
    """SQLite-backed semantic memory store for entity-relation storage."""

    def __init__(
        self,
        db_path: str = "semantic.db",
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self._db_path = db_path
        self._db_manager = db_manager
        self._lock = threading.Lock()

    async def initialize(self) -> None:
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn, transaction(conn):
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS semantic_memories (
                        id TEXT PRIMARY KEY,
                        memory_type TEXT NOT NULL DEFAULT 'semantic',
                        content TEXT NOT NULL DEFAULT '{}',
                        importance REAL NOT NULL DEFAULT 0.5,
                        embedding TEXT,
                        timestamp TEXT NOT NULL,
                        ttl INTEGER,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    CREATE INDEX IF NOT EXISTS idx_semantic_importance
                        ON semantic_memories(importance);
                    CREATE INDEX IF NOT EXISTS idx_semantic_timestamp
                        ON semantic_memories(timestamp);
                """)

    async def save(self, item: MemoryItem) -> str:
        self._validate_type(item)
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn, transaction(conn):
                conn.execute(
                    """INSERT OR REPLACE INTO semantic_memories
                    (id, memory_type, content, importance, embedding, timestamp, ttl, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (item.id, item.memory_type.value, json.dumps(item.content, ensure_ascii=False),
                     item.importance,
                     json.dumps(item.embedding) if item.embedding else None,
                     item.timestamp.isoformat(), item.ttl,
                     json.dumps(item.metadata, ensure_ascii=False)),
                )
        return item.id

    async def batch_save(self, items: list[MemoryItem]) -> list[str]:
        ids = []
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn, transaction(conn):
                for item in items:
                    self._validate_type(item)
                    conn.execute(
                        """INSERT OR REPLACE INTO semantic_memories
                        (id, memory_type, content, importance, embedding, timestamp, ttl, metadata, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                        (item.id, item.memory_type.value, json.dumps(item.content, ensure_ascii=False),
                         item.importance,
                         json.dumps(item.embedding) if item.embedding else None,
                         item.timestamp.isoformat(), item.ttl,
                         json.dumps(item.metadata, ensure_ascii=False)),
                    )
                    ids.append(item.id)
        return ids

    async def get(self, id: str) -> MemoryItem | None:
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn:
                row = conn.execute("SELECT * FROM semantic_memories WHERE id = ?", (id,)).fetchone()
        return self._row_to_item(row) if row else None

    async def query(self, spec: MemoryQuery) -> list[MemoryItem]:
        conditions = ["memory_type = ?"]
        params: list[Any] = [MemoryType.SEMANTIC.value]
        if spec.min_importance > 0:
            conditions.append("importance >= ?"); params.append(spec.min_importance)
        if spec.time_range:
            start, end = spec.time_range
            conditions.append("timestamp >= ? AND timestamp <= ?")
            params.append(start.isoformat()); params.append(end.isoformat())
        for key, value in spec.filters.items():
            if key in ("entity_type", "entity_name", "relation_type"):
                conditions.append(f"json_extract(content, '$.{key}') = ?"); params.append(str(value))
        where = " AND ".join(conditions)
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn:
                rows = conn.execute(f"SELECT * FROM semantic_memories WHERE {where} ORDER BY importance DESC LIMIT ?",
                                    params + [spec.top_k]).fetchall()
        return [self._row_to_item(r) for r in rows]

    async def delete(self, id: str) -> bool:
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn, transaction(conn):
                c = conn.execute("DELETE FROM semantic_memories WHERE id = ?", (id,))
                return c.rowcount > 0

    async def count(self, filter: MemoryFilter | None = None) -> int:
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn:
                row = conn.execute("SELECT COUNT(*) FROM semantic_memories WHERE memory_type='semantic'").fetchone()
                return row[0] if row else 0

    async def vacuum(self) -> None:
        lock = self._db_manager.get_lock("semantic") if self._db_manager else self._lock
        with lock:
            with self._lease() as conn:
                conn.execute("VACUUM")

    async def close(self) -> None:
        pass

    def _lease(self) -> ConnectionLease:
        if self._db_manager:
            return self._db_manager.lease("semantic", self._db_path)
        return ConnectionLease.standalone(self._db_path)

    def _validate_type(self, item: MemoryItem) -> None:
        if item.memory_type != MemoryType.SEMANTIC:
            raise ValueError(f"SQLiteSemanticStore only accepts SEMANTIC type, got {item.memory_type}")

    @staticmethod
    def _row_to_item(row: Any) -> MemoryItem:
        return MemoryItem(id=row["id"], memory_type=MemoryType(row["memory_type"]),
                          content=json.loads(row["content"]) if row["content"] else {},
                          importance=row["importance"],
                          embedding=json.loads(row["embedding"]) if row["embedding"] else None,
                          timestamp=datetime.fromisoformat(row["timestamp"]),
                          ttl=row["ttl"], metadata=json.loads(row["metadata"]) if row["metadata"] else {})
