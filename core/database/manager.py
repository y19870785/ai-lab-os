"""DatabaseManager - Unified SQLite connection management."""
from __future__ import annotations
import sqlite3
import threading
from pathlib import Path

class DatabaseManager:
    def __init__(self, base_path="data"):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._connections = {}
        self._locks = {}
        self._lock = threading.Lock()

    def get_connection(self, name):
        db_path = str(self._base_path / f"{name}.db")
        with self._lock:
            if name not in self._connections:
                conn = sqlite3.connect(db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                self._connections[name] = conn
            return self._connections[name]

    def get_lock(self, name):
        """Return a per-database lock for thread-safe operations."""
        with self._lock:
            if name not in self._locks:
                self._locks[name] = threading.Lock()
            return self._locks[name]

    def close(self, name):
        with self._lock:
            conn = self._connections.pop(name, None)
            if conn: conn.close()

    # ── Health & Maintenance ──

    def health_check(self, name: str) -> bool:
        """Check if database connection is alive."""
        try:
            conn = self.get_connection(name)
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def vacuum(self, name: str) -> None:
        """Rebuild database to reclaim disk space."""
        conn = self.get_connection(name)
        conn.execute("VACUUM")

    def backup(self, name: str, dest_path: str) -> str:
        """Backup database to external path. Returns dest_path.

        TODO: implement file-copy with WAL checkpoint.
        """
        raise NotImplementedError("backup not implemented")

    def restore(self, name: str, src_path: str) -> bool:
        """Restore database from external path. Returns True on success.

        TODO: implement file-replace with integrity check.
        """
        raise NotImplementedError("restore not implemented")

    def close_all(self):
        with self._lock:
            for name, conn in self._connections.items(): conn.close()
            self._connections.clear()

_db = None
def get_db(base_path="data"):
    global _db
    if _db is None: _db = DatabaseManager(base_path=base_path)
    return _db
def reset_db():
    global _db
    if _db: _db.close_all()
    _db = None