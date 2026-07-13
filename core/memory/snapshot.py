"""Memory Snapshot - Point-in-time memory state capture.
Supports create, restore, and compare operations.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any
from core.memory.models import MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore

class MemorySnapshot:
    def __init__(self, stores: dict[MemoryType, MemoryStore], db_manager=None):
        self._stores = stores
        self._db = db_manager

    async def create_snapshot(self, label: str = "") -> str:
        snap = {"label": label, "timestamp": datetime.now().isoformat(), "items": {}}
        for mtype, store in self._stores.items():
            items = await store.query(MemoryQuery(memory_type=mtype, top_k=10000))
            snap["items"][mtype.value] = [item.model_dump() for item in items]
        snap_id = __import__("uuid").uuid4().hex[:12]
        if self._db:
            conn = self._db.get_connection("snapshot")
            conn.execute(
                "INSERT OR REPLACE INTO snapshots (snapshot_id, label, timestamp, data) VALUES (?,?,?,?)",
                (snap_id, label, snap["timestamp"], json.dumps(snap)),
            )
            conn.commit()
        return snap_id

    async def restore_snapshot(self, snapshot_id: str) -> int:
        snap = await self._load_snapshot(snapshot_id)
        if not snap: return 0
        count = 0
        for mt_str, items_data in snap["items"].items():
            mtype = MemoryType(mt_str)
            store = self._stores.get(mtype)
            if not store: continue
            for data in items_data:
                item = MemoryItem(**data)
                await store.save(item)
                count += 1
        return count

    async def compare_snapshot(self, snapshot_id: str) -> dict:
        snap = await self._load_snapshot(snapshot_id)
        if not snap: return {"error": "Snapshot not found"}
        result = {"added": [], "removed": [], "changed": []}
        snap_ids = {}
        for mt_str, items in snap["items"].items():
            for item in items:
                snap_ids[item["id"]] = (mt_str, item)
        for mtype, store in self._stores.items():
            current = await store.query(MemoryQuery(memory_type=mtype, top_k=10000))
            curr_ids = {item.id: item for item in current}
            for cid in curr_ids:
                if cid not in snap_ids:
                    result["added"].append({"id": cid, "type": mtype.value})
            for sid in snap_ids:
                smt = snap_ids[sid][0]
                if MemoryType(smt) == mtype and sid not in curr_ids:
                    result["removed"].append({"id": sid, "type": smt})
        return result

    async def _load_snapshot(self, snapshot_id: str):
        if not self._db: return None
        conn = self._db.get_connection("snapshot")
        row = conn.execute("SELECT data FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if not row: return None
        return json.loads(row["data"])