# ADR-058 — WorkLogService over Existing Episodic Storage

Status: Accepted

> Accepted architecture decision for the SP-018 planning baseline. It does not approve or start implementation.

## Context

Work Log is currently written and read through generic MemoryManager calls. The physical rows already live in `episodic.db / episodic_memories`, while product consumers need type-safe Workspace, ID, filtering, ordering, pagination and legacy semantics. Creating `work_logs.db` would split truth and require migration or dual writes.

## Decision

1. `WorkLogService` becomes the only logical product boundary for Work Log create/get/list.
2. A `WorkLogRepository` protocol and SQLite adapter access the existing `episodic_memories` table.
3. The adapter uses the Composition Root's existing DatabaseManager and its `episodic` connection ownership.
4. No `work_logs.db`, new table, cross-database transaction or duplicate Work Log row is created.
5. WorkLogService is the only writer for `content.type=work_log` after each entrypoint is migrated.
6. New writes are insert-only; they do not use `INSERT OR REPLACE` to overwrite an existing canonical ID.
7. SQLiteEpisodicStore remains the generic Episodic Memory store. The Work Log adapter may share a row codec, but does not introduce a second Work Log truth.
8. Complete WorkspaceKey and `type=work_log` predicates are applied in Repository SQL before projection or pagination.
9. SP-018 planning assumes no Schema change. Any index or table change requires separate evidence and approval.

## Consequences

- CEO Assistant, API, CLI, Inbox, Agenda and Brief can share one product contract.
- Generic MemoryQuery is not expanded into a Work Log-specific product API.
- Two adapters access one table, so ownership must remain explicit and tests must prove no double writes or destructive replacement.
- JSON filtering may be slower without new indexes; correctness and Workspace isolation take precedence in the local-first Alpha boundary.

## Rejected alternatives

### Continue only through MemoryManager

Rejected because it would push Work Log-specific Workspace, canonical ID, legacy projection, context references and pagination into a generic Memory abstraction that currently truncates and orders by importance.

### Create work_logs.db

Rejected because it creates a second truth source, migration burden, duplicate risk and cross-database coordination without a current product need.

### Copy legacy rows into a new canonical representation

Rejected because automatic migration can duplicate records, drift identity, misassign Workspace and make rollback destructive.

## Implementation boundary

This ADR records a decision only. No Repository, Service, query, Schema, Composition Root or production code is implemented by the planning baseline.
