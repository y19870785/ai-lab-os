# AI-Lab Technical Debt Register

> Last updated: 2026-07-12 | Version: v0.14.0

## Active Debts

### TD-002: MemoryManager dual API (P1)
- **Status**: Deferred
- **Description**: MemoryManager has both new API (save_memory/retrieve_memory/...) and legacy API (save/retrieve/...). Old API marked deprecated but still used by tests.
- **Recommended action**: Migrate all tests to new API, remove old API in v0.15.0.
- **Files**: core/memory/manager.py, tests/core/memory/test_memory.py, tests/core/memory/test_integration.py

### TD-003: SessionMemory as MemoryStore (P1)
- **Status**: Deferred
- **Description**: SessionMemory implements MemoryStore protocol but uses in-memory dict — not persistent, not distributed. If multi-instance deployment is needed, this must be replaced with a persistent backend (Redis/SQLite).
- **Recommended action**: Rename SessionMemory to SessionCache or add SQLite/REDIS backend in v0.16.0.
- **Files**: core/memory/session.py

### TD-004: ConsolidationEngine single-thread bottleneck (P1)
- **Status**: Deferred
- **Description**: ConsolidationEngine._consolidate_store() loops sequentially over all items. With 100k+ items, this blocks. Needs async batching.
- **Recommended action**: Add chunked processing (batch of 100) in v0.16.0.
- **Files**: core/memory/consolidation.py

### TD-005: MemorySnapshot full-scan compare (P2)
- **Status**: Deferred
- **Description**: compare_snapshot() pulls all items (top_k=10000) and does in-memory diff. O(n) in item count.
- **Recommended action**: Add incremental diff or checksum mechanism.
- **Files**: core/memory/snapshot.py

### TD-006: Event handler exception swallowing (P2)
- **Status**: Deferred
- **Description**: MemoryPublisher uses asyncio.gather(return_exceptions=True) — exceptions are silently dropped. Should log errors to system.error topic.
- **Files**: core/bus/publisher.py

### TD-007: Config model mismatch (P2)
- **Status**: Deferred
- **Description**: core/config.py defines DatabaseConfig with PostgreSQL fields (host/port/user/password) but DatabaseManager uses SQLite. Either align or split into separate config objects.
- **Files**: core/config.py, core/database/manager.py

### TD-008: Audit lambda closure (P3)
- **Status**: Deferred
- **Description**: MemoryAuditor uses lambda with default-argument capture for closure. Works but less readable than functools.partial.
- **Files**: core/memory/audit.py

### TD-009: Knowledge Layer stubs (P1)
- **Status**: Deferred
- **Description**: knowledge/manager.py, knowledge/ingestion.py are skeleton files. Need full implementation in Phase 3.
- **Files**: knowledge/*.py

### TD-010: No Provider Layer (P0 — block for Phase 3)
- **Status**: Must address before Phase 3
- **Description**: No unified ModelProvider / EmbeddingProvider / VectorProvider / StorageProvider abstraction. Current design scatters provider concepts across modules.
- **Recommended action**: Create core/providers/ in v0.15.0 before starting Knowledge Layer.
- **Files**: Architecture-level concern

## Resolved Debts

### TD-001: test_episodic.py syntax error
- **Status**: ✅ Resolved in v0.13.0
- **Resolution**: Test file was rewritten with clean syntax. All 121 tests pass.
