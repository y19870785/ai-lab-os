"""Database Layer - Unified SQLite management.

Usage:
    from core.database import get_db, run_all_migrations
    db = get_db("data/memory")
    run_all_migrations(db)
    conn = db.get_connection("episodic")
"""
from core.database.manager import DatabaseManager, get_db, reset_db
from core.database.connection import transaction
from core.database.migration import run_migration, run_all_migrations
from core.database.models import MigrationRecord

__all__ = [
    "DatabaseManager", "get_db", "reset_db",
    "transaction",
    "run_migration", "run_all_migrations",
    "MigrationRecord",
]