"""KnowledgeStore 的轻量 SQLite 持久化实现。"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from core.knowledge.models import KnowledgeItem, KnowledgeQuery, KnowledgeResult
from core.knowledge.protocol import KnowledgeStore


class SQLiteKnowledgeStore(KnowledgeStore):
    """Store-owned connections avoid the current shared-connection ownership bug."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS knowledge_items (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_title ON knowledge_items(title)")

    async def save(self, item: KnowledgeItem) -> str:
        payload = item.model_dump(mode="json")
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO knowledge_items
                   (id, data, title, content, updated_at) VALUES (?, ?, ?, ?, ?)""",
                (item.id, json.dumps(payload, ensure_ascii=False), item.title,
                 item.content, item.updated_at.isoformat()),
            )
        return item.id

    async def batch_save(self, items: list[KnowledgeItem]) -> list[str]:
        ids: list[str] = []
        for item in items:
            ids.append(await self.save(item))
        return ids

    async def get(self, id: str) -> KnowledgeItem | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT data FROM knowledge_items WHERE id = ?", (id,)).fetchone()
        return KnowledgeItem.model_validate_json(row["data"]) if row else None

    async def query(self, spec: KnowledgeQuery) -> list[KnowledgeResult]:
        text = spec.text.strip()
        sql = "SELECT data FROM knowledge_items"
        params: list[object] = []
        if text:
            sql += " WHERE title LIKE ? OR content LIKE ?"
            needle = f"%{text}%"
            params.extend([needle, needle])
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([spec.top_k, spec.offset])
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [KnowledgeResult(item=KnowledgeItem.model_validate_json(row["data"]), score=1.0)
                for row in rows]

    async def delete(self, id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM knowledge_items WHERE id = ?", (id,))
        return cursor.rowcount > 0

    async def count(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()
        return int(row[0]) if row else 0

    async def close(self) -> None:
        # Connections are operation-scoped and already closed.
        return None
