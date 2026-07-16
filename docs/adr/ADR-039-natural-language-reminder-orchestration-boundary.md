# ADR-039: Natural-Language Reminder Orchestration Boundary

## Status

Proposed / SP-009 implementation candidate

## Context

Natural-language Reminder creation spans UserTask, Reminder, and Scheduler persistence. Letting CEO Assistant call repositories or Scheduler directly would duplicate SP-005 Saga behavior and make partial failure invisible.

## Decision

The Composition Root creates one `NaturalLanguageReminderOrchestrator` and injects it into CEO Assistant. A deterministic parser produces task/reminder intent and an optional aware UTC due time as independent dimensions. A task may own `due_at` without owning a Reminder. Reminder intent requires a supported future `due_at`; the orchestrator then creates/reuses the UserTask and delegates Reminder plus Scheduler Job creation to `ReminderSchedulerBridge`.

`Clock` and the configured IANA timezone are injected. Production uses `SystemClock`; tests use an explicit mutable clock. Explicit idempotency keys retain retry semantics; `/chat` generates a fresh non-empty key for each request that omits one. Only the key hash, not the raw value, is persisted. Bridge failure is returned as `FailureInfo` and recorded in UserTask metadata while the existing Reminder Saga remains the recovery authority.

## Consequences

- CEO Assistant owns no persistence details or Scheduler Job construction.
- Task-only input remains available when Reminder/Scheduler are disabled.
- Reminder input fails before task creation when orchestration is unavailable.
- Cross-database behavior remains a recoverable Saga, not a fictional transaction.
- The supported language subset is intentionally small and deterministic.

## Rejected Alternatives

- LLM-derived time: nondeterministic and difficult to test.
- Direct repository calls from CEO Assistant: duplicates ownership.
- Global title deduplication: prevents legitimate same-title reminders.
- Silent fallback to task-only: creates false success.
