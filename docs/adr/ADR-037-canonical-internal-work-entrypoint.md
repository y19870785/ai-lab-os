# ADR-037: Canonical Internal Work Entrypoint

## Status

Accepted

## Acceptance Record

- Accepted through SP-008
- PR: #16
- Merge Commit: `1858d4991379058948559cc96e2672df44e42b67`
- Accepted Date: 2026-07-16

## Context

New work can enter through direct application calls, direct CEO Assistant calls, CLI commands, and Scheduler dispatch. Rechecking at every downstream runtime would break work accepted before draining.

## Decision

- `ApplicationRuntime.execute()` is the canonical application boundary.
- Direct `CEOAssistant.run()` is also gated because it remains publicly callable.
- CLI business commands are included through `ApplicationRuntime.execute()` and do not duplicate the check.
- Scheduler due-job claim/dispatch is a separate producer boundary.
- A same-Task nested call is an accepted continuation; a detached child calling a canonical entrypoint is new work and must be readmitted.
- TaskRuntime, WorkflowRuntime, AgentRuntime, Reminder handlers, health, startup, shutdown, cleanup, recovery, and migration are excluded.
- Alpha Assistant direct invocation remains excluded because it is not registered by the production Composition Root.

## Consequences

Every included new-work path is rejected outside `READY`, while downstream same-Task work accepted in `READY` can complete without a second lifecycle decision. Ordinary child Tasks never receive a reusable bypass; Scheduler-owned job execution is the sole explicit spawned continuation.
