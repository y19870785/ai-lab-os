"""SQLite connection leases and transaction helpers."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Protocol


class _Lock(Protocol):
    def acquire(self) -> bool: ...

    def release(self) -> None: ...


def open_sqlite_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open one consistently configured SQLite connection."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    except Exception:
        conn.close()
        raise


class ConnectionLease:
    """Hold a connection and, for managed leases, its database lock."""

    def __init__(
        self,
        connection: sqlite3.Connection | None,
        *,
        owned: bool,
        lock: _Lock | None = None,
        connection_factory: Callable[[], sqlite3.Connection] | None = None,
    ) -> None:
        self._connection = connection
        self.owned = owned
        self._lock = lock
        self._connection_factory = connection_factory
        self._entered = False

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("Managed connection is available only inside its lease")
        return self._connection

    def __enter__(self) -> sqlite3.Connection:
        if self._entered:
            raise RuntimeError("Connection lease is already active")
        if self._lock is not None:
            self._lock.acquire()
        try:
            if self._connection_factory is not None:
                self._connection = self._connection_factory()
            self._entered = True
            return self.connection
        except Exception:
            if self._lock is not None:
                self._lock.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            if self.owned:
                self.connection.close()
        finally:
            self._entered = False
            if not self.owned:
                self._connection = None
            if self._lock is not None:
                self._lock.release()

    @classmethod
    def managed(
        cls,
        connection_factory: Callable[[], sqlite3.Connection],
        lock: _Lock,
    ) -> "ConnectionLease":
        return cls(
            None,
            owned=False,
            lock=lock,
            connection_factory=connection_factory,
        )

    @classmethod
    def standalone(cls, db_path: str | Path) -> "ConnectionLease":
        return cls(open_sqlite_connection(db_path), owned=True)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Commit an operation atomically, rolling it back on every failure."""

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
