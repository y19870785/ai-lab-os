"""DatabaseManager - owner of process-scoped SQLite connections."""
from __future__ import annotations
import sqlite3
import threading
from pathlib import Path

from core.database.connection import ConnectionLease, open_sqlite_connection
from core.errors import RuntimeStatus, failure_from_exception


class DatabasePathConflictError(ValueError):
    """Raised when one logical database name is rebound to another path."""


class DatabaseManager:
    def __init__(self, base_path="data"):
        self._base_path = Path(base_path).resolve()
        self._connections: dict[str, sqlite3.Connection] = {}
        self._paths: dict[str, Path] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._lock = threading.RLock()
        self._ever_opened = False

    def bind_path(self, name: str, db_path: str | Path) -> Path:
        """Bind a logical database name to one immutable path."""

        resolved = Path(db_path).resolve()
        with self._lock:
            current = self._paths.get(name)
            if current is not None and current != resolved:
                raise DatabasePathConflictError(
                    f"Database {name!r} is already bound to a different path"
                )
            self._paths[name] = resolved
            return resolved

    def get_path(self, name: str, db_path: str | Path | None = None) -> Path:
        if db_path is not None:
            return self.bind_path(name, db_path)
        with self._lock:
            current = self._paths.get(name)
        return current if current is not None else self.bind_path(
            name, self._base_path / f"{name}.db"
        )

    def get_connection(
        self, name: str, db_path: str | Path | None = None
    ) -> sqlite3.Connection:
        """Borrow a cached connection; the caller must never close it."""

        path = self.get_path(name, db_path)
        db_lock = self.get_lock(name)
        with db_lock:
            with self._lock:
                conn = self._connections.get(name)
            if conn is not None:
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    conn.close()
                    with self._lock:
                        if self._connections.get(name) is conn:
                            self._connections.pop(name, None)

            conn = open_sqlite_connection(path)
            with self._lock:
                self._connections[name] = conn
                self._ever_opened = True
            return conn

    def lease(
        self, name: str, db_path: str | Path | None = None
    ) -> ConnectionLease:
        """Return a lease that protects the complete borrowed operation."""

        path = self.get_path(name, db_path)
        db_lock = self.get_lock(name)
        return ConnectionLease.managed(
            lambda: self.get_connection(name, path),
            db_lock,
        )

    def get_lock(self, name: str) -> threading.RLock:
        """Return a per-database lock for thread-safe operations."""
        with self._lock:
            if name not in self._locks:
                self._locks[name] = threading.RLock()
            return self._locks[name]

    def close(self, name: str) -> None:
        db_lock = self.get_lock(name)
        with db_lock:
            with self._lock:
                conn = self._connections.get(name)
            if conn is not None:
                conn.close()
                with self._lock:
                    if self._connections.get(name) is conn:
                        self._connections.pop(name, None)

    # ── Health & Maintenance ──

    def health_check(self, name: str) -> bool:
        """Probe an existing connection without creating a database file."""

        with self._lock:
            conn = self._connections.get(name)
        if conn is None:
            return False
        try:
            with self.get_lock(name):
                conn.execute("SELECT 1")
                return True
        except sqlite3.Error:
            return False

    def health(self) -> dict[str, object]:
        """Return lifecycle health without exposing local filesystem paths."""

        with self._lock:
            names = tuple(self._connections)
            ever_opened = self._ever_opened
        if not names:
            return {
                "status": (
                    RuntimeStatus.STOPPED.value
                    if ever_opened else RuntimeStatus.NOT_INITIALIZED.value
                ),
                "connections": 0,
            }
        failures = []
        for name in names:
            if self.health_check(name):
                continue
            failure = failure_from_exception(
                sqlite3.OperationalError("SQLite connection health check failed"),
                component="database",
                operation="health_check",
                details={"logical_database": name},
            )
            failures.append(failure.to_dict())
        return {
            "status": (
                RuntimeStatus.FAILED.value if failures else RuntimeStatus.OK.value
            ),
            "connections": len(names),
            "failed_connections": len(failures),
            "failures": failures,
        }

    def vacuum(self, name: str) -> None:
        """Rebuild database to reclaim disk space."""
        with self.lease(name) as conn:
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

    def close_all(self) -> None:
        with self._lock:
            names = tuple(self._connections)
        failures: list[Exception] = []
        for name in names:
            try:
                self.close(name)
            except Exception as exc:
                failures.append(exc)
        if failures:
            raise RuntimeError(
                f"Failed to close {len(failures)} database connection(s)"
            ) from failures[0]

    @property
    def connection_count(self) -> int:
        with self._lock:
            return len(self._connections)

_db = None
def get_db(base_path="data"):
    global _db
    if _db is None: _db = DatabaseManager(base_path=base_path)
    return _db
def reset_db():
    global _db
    if _db: _db.close_all()
    _db = None
