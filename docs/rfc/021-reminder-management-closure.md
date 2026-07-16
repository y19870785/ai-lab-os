# RFC-021: Reminder Management Closure

**Status:** Proposed / SP-011 implementation candidate
**Scope:** Reminder management, actionable inbox semantics, deterministic responses, and local CLI output
**Merge status:** Draft PR / Awaiting ChatGPT review / Not merged

## Context

SP-009 created a persistent natural-language Reminder chain and SP-010 made reminders discoverable. Users still need one shared boundary for resolving, viewing, cancelling, and rescheduling reminders. The existing cross-database Reminder/Scheduler Saga remains authoritative; this RFC does not introduce a second transaction model.

## User Problems

- A future cancelled reminder appeared in broad `upcoming` results even though it was not actionable.
- API, CLI, and CEO Assistant could otherwise drift into separate management rules.
- Deterministic Reminder operations received Mock/LLM mode text even when no provider was used.
- Captured Windows CLI output depended on an external encoding override.

## Management Boundary

`ReminderManagementService` is created once by the Composition Root. It owns workspace validation, resolution, terminal-state rules, stable failures, idempotency metadata, and delegation to `ReminderSchedulerBridge`. API routes, CLI commands, and CEO Assistant do not write Reminder or Scheduler persistence directly.

## Resolution and Ambiguity

An exact Reminder ID is accepted only when its linked UserTask belongs to the request workspace. Title matching is limited to the current workspace. A unique exact or substring match resolves; multiple matches fail closed with `reminder.ambiguous` and bounded candidates; no visible match returns `reminder.not_found`.

## Cancellation Semantics

Scheduled or retrying reminders are cancelled through the existing Bridge Saga. The Reminder and Scheduler Job become cancelled, repeated cancellation is idempotent, and no occurrence is created at the old due time. Triggered and failed reminders are terminal for cancellation. Partial failure returns `reminder.cancellation_failed`; the persisted pending/failure state remains queryable.

## Rescheduling Semantics

Scheduled, retrying, and failed reminders may be rescheduled. Triggered and cancelled reminders reject the operation with `reminder.terminal_state`. The Bridge updates the existing one-shot Scheduler Job where possible, keeps the UserTask relation, and moves the Reminder back to scheduled only after coordination succeeds. The previous failure code is retained in `management_reschedule` audit metadata while current `last_failure` is cleared.

## Saga and Compensation

Reminder and Scheduler databases remain separate durability boundaries. Management operations reuse Bridge pending states and reconciliation behavior. They never claim cross-database atomicity and never return success after a Bridge failure. Query aggregation maps a pending management state carrying `last_failure` to visible `failed` until recovery.

## Idempotency

Cancellation is naturally idempotent. Rescheduling accepts an explicit idempotency key. A SHA-256 digest, never the raw key, is stored with the target UTC instant. The same key and target reuse the persisted result; the same key with a different target fails with `reminder.idempotency_conflict`. Rescheduling reuses the existing Scheduler Job ID and does not create duplicate active jobs.

## Pending Inbox Semantics

`view=pending` means `status in (scheduled, retrying)` and `scheduled_for >= now`. Explicit combinations such as `status=cancelled&time_scope=upcoming` remain valid. No-parameter API and CLI list calls continue to return all reminders for compatibility. The deterministic phrase "查看我的提醒" selects pending items and reports terminal counts separately.

## Deterministic Response Boundary

Reminder creation, inbox, detail, cancellation, and rescheduling are deterministic application responses. They set an internal response marker so provider-mode notices are not appended. Ordinary LLM-backed chat preserves its existing explicit Mock mode notice. No response text is stripped at API or presentation boundaries.

## CLI UTF-8 Boundary

The CLI reconfigures stdout and stderr to UTF-8 with replacement only when the stream supports `reconfigure`. JSON uses `ensure_ascii=False`; diagnostics go to stderr. The process does not change the Windows system code page or require a persistent `PYTHONIOENCODING` setting.

## Workspace Isolation

All management and status reads validate the linked UserTask's server-owned workspace metadata. Cross-workspace IDs return `reminder.not_found`, avoiding existence disclosure. This is logical workspace isolation, not a user identity, RBAC, or strong multi-tenant security model.

## Acceptance Strategy

Tests cover cancellation without occurrence, restart-safe rescheduling, old-time suppression, exactly one new-time occurrence, terminal rules, unique/ambiguous resolution, failure injection, pending filters, deterministic responses, real Composition Root wiring, real FastAPI lifespan, SQLite persistence, and subprocess UTF-8 JSON output.

## Known Limitations

External notification, system notification, recurring reminders, batch management, fuzzy semantic search, multi-turn references, user identity, RBAC, strong multi-tenancy, Web UI, and distributed scheduling remain out of scope. Cross-SQLite inbox reads are not snapshot transactions, and deep sparse pagination remains a performance observation point.
