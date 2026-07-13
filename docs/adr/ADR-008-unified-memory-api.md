# ADR-008: Unified Memory API

## Status
Accepted (2026-07-12)

## Context
AI-Lab Memory Layer has four memory types (Session/Episodic/Semantic/Decision). Each was developed in separate phases (2.2 through 2.6), leading to slight API inconsistencies between stores.

## Decision
All Memory Stores MUST implement the identical 8-method interface defined in `MemoryStore` protocol:

| Method | Signature | Semantics |
|--------|-----------|-----------|
| `save` | `(item: MemoryItem) -> str` | Store a single item, return ID |
| `batch_save` | `(items: list[MemoryItem]) -> list[str]` | Batch store, return IDs |
| `get` | `(id: str) -> MemoryItem | None` | Retrieve by ID |
| `query` | `(spec: MemoryQuery) -> list[MemoryItem]` | Search by criteria |
| `delete` | `(id: str) -> bool` | Delete by ID, return success |
| `count` | `(filter: MemoryFilter | None) -> int` | Count with optional filter |
| `initialize` | `() -> None` | Idempotent store init |
| `close` | `() -> None` | Idempotent resource release |

Rationale:
- No store may have extra methods that other stores lack (beyond type-specific convenience wrappers at the high-level API)
- `count()` must respect `filter` parameter — previously SessionMemory/Semantic/Decision ignored it
- `initialize()` ensures SQLite stores create tables before use; SessionMemory is a no-op
- `close()` exists for resource lifecycle even when DatabaseManager manages connections

## Consequences
- All four stores now expose exactly 8 identical public methods
- `MemoryQuery` gained `offset`, `sort_by`, `sort_desc` for pagination
- `MemoryFilter` dropped `tags` (moved to `MemoryQuery.filters`)
- Backward compatible: no existing callers break
- Testing surface is uniform across stores

## Alternatives Considered
- **Keep asymmetry**: Rejected — would force callers to check `isinstance()` before calling methods, violating LSP
- **Split into separate protocols**: Rejected — four stores share 90% semantics, one protocol is cleaner
