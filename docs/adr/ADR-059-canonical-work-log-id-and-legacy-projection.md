# ADR-059 — Canonical Work Log ID and Read-Only Legacy Projection

Status: Accepted

> Accepted architecture decision for the SP-018 planning baseline. It does not approve or start implementation.

## Context

CEO Assistant Work Logs currently receive generic random Memory IDs. Inbox conversion uses historical deterministic `inbox_wl_...` IDs. Existing rows may lack complete Workspace, timezone or typed fields. Deleting, rewriting or importing them would risk duplication, data loss and identity drift.

## Decision

1. New Work Logs use canonical `wl_<32 lowercase hex>` IDs.
2. A new row uses the same value for `WorkLogRecord.id` and `episodic_memories.id`.
3. Direct create uses cryptographically random hex and insert-only collision retry.
4. Inbox create derives the 32 hex payload deterministically from Inbox Item ID; a collision only recovers when the stored source matches that Inbox, otherwise it fails.
5. A legacy row is projected to `wl_legacy_<full sha256 of legacy memory id>`.
6. The projection is deterministic across processes and restarts, retains `legacy_memory_id`, and never writes a new row.
7. Public API/CLI lookup accepts canonical `wl_...` and `wl_legacy_...`; raw generic Memory IDs remain internal.
8. Legacy `inbox_wl_...` rows are treated as legacy inputs and receive the same stable projection. Existing Inbox resolution evidence is not rewritten.
9. Missing complete Workspace assigns the legacy row only to canonical `default/default/default`.
10. Legacy time is projected from explicit occurred_at/date, then persisted Memory timestamp; current time is never substituted.
11. Projection failures are visible as `work_log.legacy_projection_failed`; incompatible data is not silently discarded.

## Consequences

- All public consumers receive type-bearing stable IDs.
- Existing rows remain unchanged and traceable.
- Legacy lookup requires a deterministic digest lookup within the Repository.
- Raw status or incomplete fields may require explicit legacy projection metadata rather than pretending they satisfy the new create contract.

## Rejected alternatives

### Expose existing random Memory IDs

Rejected because they do not identify the product type and would preserve different identity contracts for API, CLI, Agenda and Brief.

### Rewrite IDs in place

Rejected because Inbox resolution claims and any external references may depend on the original row ID; the operation is destructive and difficult to roll back.

### Import into duplicate canonical rows

Rejected because retries can duplicate records and any inferred Workspace or time may be wrong.

## Implementation boundary

This ADR defines identity and compatibility only. The planning baseline performs no migration, write-back, alias table, Schema change or production implementation.
