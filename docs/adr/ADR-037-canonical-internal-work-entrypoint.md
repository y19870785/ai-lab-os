# ADR-037: Canonical Internal Work Entrypoint

## Status

Proposed / SP-008 implementation candidate

## Context

New work can enter through direct application calls, direct CEO Assistant calls, CLI commands, and Scheduler dispatch. Rechecking at every downstream runtime would break work accepted before draining.

## Decision

- `ApplicationRuntime.execute()` is the canonical application boundary.
- Direct `CEOAssistant.run()` is also gated because it remains publicly callable.
- CLI business commands are included through `ApplicationRuntime.execute()` and do not duplicate the check.
- Scheduler due-job claim/dispatch is a separate producer boundary.
- TaskRuntime, WorkflowRuntime, AgentRuntime, Reminder handlers, health, startup, shutdown, cleanup, recovery, and migration are excluded.
- Alpha Assistant direct invocation remains excluded because it is not registered by the production Composition Root.

## Consequences

Every included new-work path is rejected outside `READY`, while downstream work accepted in `READY` can complete without a second lifecycle decision.
