"""Database Layer - Unified SQLite management.

Usage:
    from core.database import get_db, run_all_migrations
    db = get_db("data/memory")
    run_all_migrations(db)
    conn = db.get_connection("episodic")
"""
from core.database.manager import (
    DatabaseManager,
    DatabasePathConflictError,
    get_db,
    reset_db,
)
from core.database.connection import ConnectionLease, transaction
from core.database.migration import run_migration, run_all_migrations
from core.database.models import MigrationRecord

__all__ = [
    "DatabaseManager", "DatabasePathConflictError", "get_db", "reset_db",
    "ConnectionLease", "transaction",
    "run_migration", "run_all_migrations",
    "MigrationRecord",
]
