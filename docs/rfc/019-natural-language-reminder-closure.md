# RFC-019: Natural-Language Reminder Closure

## Status

Adopted

## Adoption Record

- Implemented by SP-009
- Merged via PR #19
- Approved Head: `42697e2787d9d9e33f4a7b40c3dd0ea092dcf742`
- Merge Commit: `b1274d066cbc01053144cba8d5654a5f8c8a21da`
- Adoption Date: `2026-07-16`

## SP-014B Compatibility Record

- SP-014B merged through PR #33 as `22f85db16a43e7d09a903859a26ac6a310370d81`.
- With explicit `上午/下午/晚上`, the existing deterministic parser accepts Chinese hour numerals `一` through `十二`, including existing `半`、`一刻` and Arabic-digit minute combinations.
- Chinese hours without a period, 后天、星期、相对/模糊时间、中文分钟、二刻/三刻、Recurring Reminder and LLM time parsing remain unsupported.
- ACC-014 scenario K passed after this compatibility fix; the parser architecture and future time-parsing route are unchanged.

## Context

SP-004 and SP-005 introduced durable UserTask, Reminder, Scheduler Job, JobRun, and ReminderOccurrence records, but the user-facing CEO Assistant path did not create or query that complete chain. SP-009 proposes the first user-testable product slice without adding external notification delivery.

## User Outcome

A supported Chinese reminder sentence creates one UserTask, one Reminder, and one persistent one-shot Scheduler Job. The user receives machine-readable IDs, can query aggregate status through the API or CLI, restart the process without losing state, and later observe one triggered or failed occurrence.

## Supported Language Subset

The deterministic parser accepts `今天/明天` plus `HH:MM`, `HH：MM`, or `上午/下午/晚上 H 点` forms. With an explicit `上午/下午/晚上` period, `H` may be an Arabic numeral or one of `一` through `十二`; Chinese hours without a period are intentionally unsupported. `半`、`一刻` and explicit Arabic-digit minutes are also consumed completely. Expressions such as next week, relative or fuzzy times, Chinese minute numerals, recurring schedules, holidays, or missing times fail with `reminder.time_unsupported`; past times fail with `reminder.time_in_past`. LLM output never determines time.

## Task Versus Reminder

Task due date and Reminder scheduling are separate concepts. Explicit task forms such as `添加任务：...` create only a UserTask; when they contain a supported time, that time is persisted as the task's UTC `due_at` without creating a Reminder or Scheduler Job. An unsupported task time creates a task without `due_at` and reports that the time was not recognized. Explicit reminder markers require a supported future `due_at` and never degrade to task-only success.

## Time Contract

`SystemSettings.timezone_name` supplies the IANA interpretation zone (`AI_LAB_TIMEZONE`, default `Asia/Shanghai`). `Clock.now()` is an aware UTC instant. User input is interpreted in the configured zone, persisted as UTC, and returned as an aware ISO-8601 value together with the zone name.

## Orchestration Ownership

`NaturalLanguageReminderOrchestrator` is injected by the Composition Root. CEO Assistant parses intent and calls this service; it does not access repositories or construct Scheduler Jobs. The orchestrator delegates Reminder and Job creation to the existing `ReminderSchedulerBridge`, preserving the SP-005 Saga and reconciliation ownership.

## Saga And Compensation

The three SQLite databases are not presented as one transaction. UserTask is created first. Bridge failure leaves any recoverable Reminder failure in the established Saga and marks UserTask metadata `scheduling_status=failed`; the response is a non-success `FailureInfo`. A later retry with the same idempotency key reuses the deterministic UserTask and reconciles the matching Reminder instead of fabricating success.

## Idempotency

The API accepts `Idempotency-Key` (or the request field). When neither is supplied, `/chat` generates a fresh non-empty request key, so two independent no-key requests create distinct chains. Only a SHA-256 hash is persisted. A stable UserTask ID is derived from workspace scope and that hash. The same explicit key and normalized intent return the existing chain; the same key with a different intent returns `reminder.idempotency_conflict`. Titles are not globally deduplicated.

## Failure Semantics

- unsupported or missing time: `reminder.time_unsupported`;
- past time: `reminder.time_in_past`;
- disabled Reminder/Scheduler: `reminder.unavailable` before UserTask creation;
- Saga scheduling failure: `reminder.scheduling_failed` with recoverable IDs;
- trigger failure: persisted occurrence and Scheduler retry/final failure, never `triggered`.

## Status Aggregation

`ReminderStatusView` reads persisted UserTask, Reminder, Scheduler Job, and latest ReminderOccurrence. It exposes `scheduled`, `retrying`, `triggered`, `failed`, or `cancelled`, plus stable IDs, latest failure, and retryability. It does not use LLM output, logs, EventBus, or process memory as truth.

## API And CLI Visibility

- natural-language creation: `POST /chat`;
- aggregate query: `GET /reminders/{reminder_id}/status`;
- occurrences: `GET /reminders/{reminder_id}/occurrences`;
- CLI: `python -m cli reminder-status <reminder_id>`.

All production paths use the shared Composition Root and admission/security boundaries.

## Restart And Effectively-Once Behavior

SQLite Reminder and Scheduler persistence restore scheduled work on startup. The existing unique occurrence key and one-shot terminal Job semantics prevent duplicate successful occurrences across repeated ticks, recovery, and restart.

## Acceptance Strategy

The integration test uses the public `/chat` endpoint, real FastAPI lifespan, real Composition Root, real SQLite stores, real Scheduler/Reminder handler, explicit mock provider, and a fixed injected clock. It verifies creation, idempotent retry, restart, due execution, one occurrence, and post-restart status. A separate injected handler fault verifies retry/failure visibility.

## Known Limitations

No external notification, inbox UI, recurring reminder, complex date language, LLM time parsing, user timezone UI, distributed scheduling, multi-user authorization, or Web UI is included. The visible result is in-app query state.
