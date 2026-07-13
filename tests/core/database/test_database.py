"""Database Layer tests."""
from __future__ import annotations
import os, tempfile
import pytest
from core.database import get_db, reset_db, run_migration, run_all_migrations, transaction

class TestDatabaseManager:
    def setup_method(self):
        reset_db()

    def test_get_connection(self):
        db = get_db(tempfile.mkdtemp())
        conn = db.get_connection("test")
        assert conn is not None
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INT)")
        conn.execute("INSERT INTO t VALUES (1)")
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
        db.close("test")

    def test_close_all(self):
        db = get_db(tempfile.mkdtemp())
        db.get_connection("a"); db.get_connection("b")
        db.close_all()

    def test_migration(self):
        db = get_db(tempfile.mkdtemp())
        run_migration("episodic", db)
        conn = db.get_connection("episodic")
        r = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodic_memories'").fetchone()
        assert r is not None

    def test_run_all_migrations(self):
        db = get_db(tempfile.mkdtemp())
        run_all_migrations(db)
        conn = db.get_connection("audit")
        r = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'").fetchone()
        assert r is not None

    def test_transaction_success(self):
        db = get_db(tempfile.mkdtemp())
        conn = db.get_connection("tx_test")
        conn.execute("CREATE TABLE IF NOT EXISTS tx_t (id INT)")
        with transaction(conn):
            conn.execute("INSERT INTO tx_t VALUES (42)")
        assert conn.execute("SELECT id FROM tx_t").fetchone()[0] == 42

