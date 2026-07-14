"""SQLite connection leases and transaction helpers."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


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


@dataclass(frozen=True)
class ConnectionLease:
    """Describe whether the borrower owns and must close the connection."""

    connection: sqlite3.Connection
    owned: bool

    def __enter__(self) -> sqlite3.Connection:
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.owned:
            self.connection.close()

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
