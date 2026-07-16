# ADR-043: Reminder Management Coordination Boundary

**Status:** Proposed / SP-011 implementation candidate
**Date:** 2026-07-17

## Context

Reminder cancellation and rescheduling affect Reminder and Scheduler persistence. Implementing those rules independently in API, CLI, and CEO Assistant would create conflicting terminal, workspace, idempotency, and recovery behavior.

## Decision

Create one Composition Root-owned `ReminderManagementService`. It resolves workspace-visible reminders, enforces terminal rules, maps stable failures, records hashed reschedule idempotency metadata, and delegates writes to the existing `ReminderSchedulerBridge` Saga.

API routes, CLI commands, and CEO Assistant may format results but may not update Reminder repositories or Scheduler Jobs directly. Exact IDs are workspace checked; title matching executes only when it yields one visible result.

Cancellation is idempotent. Triggered and failed reminders cannot be cancelled. Rescheduling may recover failed reminders, but triggered and cancelled reminders remain terminal. Bridge failures are surfaced as `reminder.cancellation_failed` or `reminder.rescheduling_failed` and retain a queryable persisted recovery state.

## Consequences

- One management contract serves all user entrypoints.
- Existing Saga/reconciliation behavior remains the only cross-database coordination mechanism.
- No cross-SQLite atomic transaction is claimed.
- External notifications, batch operations, fuzzy resolution, identity, and RBAC remain deferred.
