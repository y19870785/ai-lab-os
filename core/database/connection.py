"""Connection helpers for DatabaseManager."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from typing import Iterator

@contextmanager
def transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise