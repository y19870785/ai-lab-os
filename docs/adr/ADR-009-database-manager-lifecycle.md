# ADR-009: Database Manager Lifecycle

## Status
Accepted (2026-07-12)

## Context
Prior to v0.13.0, each Memory Store (SQLiteEpisodicStore, SQLiteSemanticStore, SQLiteDecisionStore) managed its own SQLite connection: opening in every method call and closing after. This resulted in:
- Duplicate connection-creation code (3x)
- No shared connection pool — each `save()` opened a new file descriptor
- No centralized schema migration
- No consistent backup/restore strategy

## Decision
`DatabaseManager` (singleton via `get_db()`) owns ALL SQLite connection lifecycles:

| Responsibility | Owner |
|---------------|-------|
| Connection creation / pooling | DatabaseManager |
| Per-database locking | DatabaseManager.`get_lock(name)` |
| Schema migration (DDL) | DatabaseManager + `migration.py` |
| Health check | DatabaseManager.`health_check(name)` |
| Vacuum | DatabaseManager.`vacuum(name)` |
| Backup / Restore | DatabaseManager (interface only for now) |
| Transaction management | DatabaseManager + `connection.transaction()` |

Memory Stores call `db_manager.get_connection(name)` instead of `sqlite3.connect()`.

When `db_manager=None` (backward compat), stores fall back to self-managed connections.

## Consequences
- Three SQLite stores now accept optional `db_manager` parameter
- All database files live under `data/` directory
- Schema changes go through `run_migration()`, not scattered in store init
- `health_check()`, `vacuum()` added to DatabaseManager
- `backup()` / `restore()` are stubbed (NotImplemented) — design contract in place
