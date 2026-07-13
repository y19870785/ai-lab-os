"""SQLite-based Decision Memory Store.

Persists decision reasoning chains in SQLite.
Append-only by design — immutable records with outcome tracking.

Usage:
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore

    store = SQLiteDecisionStore(db_path="decision.db")
    await store.initialize()
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any

from core.memory.models import MemoryFilter, MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore


class SQLiteDecisionStore(MemoryStore):
    """SQLite-backed decision memory store.

    Design principles:
    - Append-only: decisions are immutable once written
    - Outcome tracking: PENDING -> SUCCESS/FAILURE via update_outcome()
    - Reasoning chains stored as structured JSON
    """

    def __init__(self, db_path: str = "decision.db", db_manager=None) -> None:
        self._db_path = db_path
        self._db_manager = db_manager
        self._lock = threading.Lock()

    async def initialize(self) -> None:
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS decision_memories (
                        id TEXT PRIMARY KEY,
                        memory_type TEXT NOT NULL DEFAULT 'decision',
                        content TEXT NOT NULL DEFAULT '{}',
                        importance REAL NOT NULL DEFAULT 0.5,
                        embedding TEXT,
                        timestamp TEXT NOT NULL,
                        ttl INTEGER,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    CREATE INDEX IF NOT EXISTS idx_decision_importance
                        ON decision_memories(importance);
                    CREATE INDEX IF NOT EXISTS idx_decision_timestamp
                        ON decision_memories(timestamp);
                """)
                conn.commit()
            finally:
                conn.close()

    async def save(self, item: MemoryItem) -> str:
        self._validate_type(item)
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO decision_memories
                    (id, memory_type, content, importance, embedding, timestamp, ttl, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (item.id, item.memory_type.value, json.dumps(item.content, ensure_ascii=False),
                     item.importance,
                     json.dumps(item.embedding) if item.embedding else None,
                     item.timestamp.isoformat(), item.ttl,
                     json.dumps(item.metadata, ensure_ascii=False)),
                )
                conn.commit()
            finally:
                conn.close()
        return item.id

    async def batch_save(self, items: list[MemoryItem]) -> list[str]:
        ids = []
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                for item in items:
                    self._validate_type(item)
                    conn.execute(
                        """INSERT OR REPLACE INTO decision_memories
                        (id, memory_type, content, importance, embedding, timestamp, ttl, metadata, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                        (item.id, item.memory_type.value, json.dumps(item.content, ensure_ascii=False),
                         item.importance,
                         json.dumps(item.embedding) if item.embedding else None,
                         item.timestamp.isoformat(), item.ttl,
                         json.dumps(item.metadata, ensure_ascii=False)),
                    )
                    ids.append(item.id)
                conn.commit()
            finally:
                conn.close()
        return ids

    async def get(self, id: str) -> MemoryItem | None:
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM decision_memories WHERE id = ?", (id,)).fetchone()
            finally:
                conn.close()
        return self._row_to_item(row) if row else None

    async def query(self, spec: MemoryQuery) -> list[MemoryItem]:
        conditions = ["memory_type = ?"]
        params: list[Any] = [MemoryType.DECISION.value]
        if spec.min_importance > 0:
            conditions.append("importance >= ?"); params.append(spec.min_importance)
        if spec.time_range:
            start, end = spec.time_range
            conditions.append("timestamp >= ? AND timestamp <= ?")
            params.append(start.isoformat()); params.append(end.isoformat())
        for key, value in spec.filters.items():
            if key in ("outcome", "agent_id", "session_id", "decision_type"):
                conditions.append(f"json_extract(content, '$.{key}') = ?"); params.append(str(value))
        where = " AND ".join(conditions)
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(f"SELECT * FROM decision_memories WHERE {where} ORDER BY importance DESC LIMIT ?",
                                    params + [spec.top_k]).fetchall()
            finally:
                conn.close()
        return [self._row_to_item(r) for r in rows]

    async def delete(self, id: str) -> bool:
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                c = conn.execute("DELETE FROM decision_memories WHERE id = ?", (id,))
                conn.commit(); return c.rowcount > 0
            finally:
                conn.close()

    async def count(self, filter: MemoryFilter | None = None) -> int:
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT COUNT(*) FROM decision_memories WHERE memory_type='decision'").fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    async def update_outcome(self, decision_id: str, outcome: str, note: str = "") -> bool:
        """Update decision outcome (PENDING -> SUCCESS/FAILURE)."""
        item = await self.get(decision_id)
        if item is None:
            return False
        item.content["outcome"] = outcome
        if note:
            item.content.setdefault("outcome_notes", []).append({"time": datetime.now().isoformat(), "note": note})
        item.metadata["action"] = "outcome_updated"
        await self.save(item)
        return True

    async def query_by_outcome(self, outcome: str, top_k: int = 10) -> list[MemoryItem]:
        return await self.query(MemoryQuery(
            memory_type=MemoryType.DECISION, filters={"outcome": outcome}, top_k=top_k,
        ))

    async def vacuum(self) -> None:
        lock = self._db_manager.get_lock("decision") if self._db_manager else self._lock
        with lock:
            conn = self._get_conn()
            try:
                conn.execute("VACUUM")
            finally:
                conn.close()

    async def close(self) -> None:
        pass

    def _get_conn(self) -> sqlite3.Connection:
        if self._db_manager:
            return self._db_manager.get_connection("decision")
        conn = sqlite3.connect(self._db_path); conn.row_factory = sqlite3.Row; return conn

    def _validate_type(self, item: MemoryItem) -> None:
        if item.memory_type != MemoryType.DECISION:
            raise ValueError(f"SQLiteDecisionStore only accepts DECISION type, got {item.memory_type}")

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> MemoryItem:
        return MemoryItem(id=row["id"], memory_type=MemoryType(row["memory_type"]),
                          content=json.loads(row["content"]) if row["content"] else {},
                          importance=row["importance"],
                          embedding=json.loads(row["embedding"]) if row["embedding"] else None,
                          timestamp=datetime.fromisoformat(row["timestamp"]),
                          ttl=row["ttl"], metadata=json.loads(row["metadata"]) if row["metadata"] else {})
