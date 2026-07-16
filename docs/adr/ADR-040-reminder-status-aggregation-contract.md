# ADR-040: Reminder Status Aggregation Contract

## Status

Proposed / SP-009 implementation candidate

## Context

Reminder lifecycle facts are distributed across UserTask, Reminder, Scheduler Job, JobRun, and ReminderOccurrence. A database row or EventBus event alone is not a stable user-visible result.

## Decision

`ReminderStatusView` is the station-internal read contract. It is assembled on demand from persisted services and exposes identifiers, scheduled time and timezone, component statuses, latest occurrence, latest sanitized `FailureInfo`, and retryability.

The aggregate state is:

- `cancelled` when Reminder is cancelled;
- `triggered` when Reminder or the latest occurrence is triggered;
- `retrying` when the Scheduler Job is retrying;
- `failed` when Reminder or Scheduler reached failure;
- otherwise `scheduled`.

The API exposes `GET /reminders/{reminder_id}/status`; CLI exposes `python -m cli reminder-status <reminder_id>`. Both resolve the same Composition Root service. LLM text, logs, EventBus events, and in-memory caches are excluded as truth sources.

## Consequences

- Restart-safe status is available without inspecting SQLite manually.
- Failure is visible without exposing internal exception text.
- Existing component enums remain authoritative; no second domain enum is created.
- The current view represents one Reminder and its latest occurrence, not a full inbox.
