# RFC-018: Internal Work Admission Boundary

## Status

Proposed / SP-008 implementation candidate

## Context

SP-007 rejects new FastAPI business requests after the system leaves `READY`, but direct process-internal calls could still enter `ApplicationRuntime`, `CEOAssistant`, or Scheduler dispatch without the FastAPI dependency. SP-008 closes that gap without adding a second lifecycle truth.

## Goals

- Reuse `SystemContainer` lifecycle states and SP-007 `FailureInfo` codes.
- Check new internal work once at its outermost canonical boundary.
- Preserve work accepted before the transition to `DRAINING`.
- Fail construction when a production entrypoint lacks admission injection.

## Non-goals

- In-flight counters, drain timeouts, forced cancellation, or waiting for all work.
- Gates on initialization, shutdown, health, diagnostics, persistence, or cleanup.
- New product behavior, database changes, or distributed admission.

## Audit Findings

| Path | Classification | Decision |
|---|---|---|
| `ApplicationRuntime.execute()` | Direct application work | Canonical gated entrypoint |
| `CEOAssistant.run()` | Direct assistant work | Gated; nested runtime dispatch reuses accepted scope |
| CLI one-shot and interactive commands | New user work | Covered through `ApplicationRuntime.execute()` |
| Scheduler `_tick()` claim/dispatch | Background producer | Gated before claim and task creation |
| Task/Workflow/Agent execution | Accepted downstream work | No repeated gate |
| Reminder Bridge API operations | API-admitted work | No repeated gate |
| Reminder Scheduler handler | Scheduler-admitted work | No repeated gate |
| Recovery, migration, health, start, shutdown | System operation | Excluded |
| Alpha Assistant direct invocation | Prototype outside production composition | Excluded until it becomes a registered product entrypoint |

## Canonical Work Entrypoints

The included boundaries are `ApplicationRuntime.execute()`, direct `CEOAssistant.run()`, and Scheduler due-job dispatch. CLI commands do not own a second gate because every business command invokes the shared `ApplicationRuntime` instance.

## Admission Ownership

`WorkAdmissionGate` owns admission semantics and reads the same `LifecycleStateMachine` instance held by `SystemContainer`. `SystemContainer.ensure_accepting_work()` delegates to this gate, so API and internal callers share one failure contract.

## Dependency Injection Strategy

The Composition Root constructs one lifecycle and one gate before runtime construction. `ApplicationRuntime`, `CEOAssistant`, Scheduler, and `SystemContainer` receive that gate explicitly. Their constructors require the dependency, so production omission fails during construction. Standalone tests use an explicit test-only permissive admission object.

`core.system` uses lazy public exports to avoid an import cycle between the narrow system contract and application modules.

## Accepted-work Semantics

`WorkAdmissionGate.admit()` is a synchronous context manager backed by a task-local `ContextVar`. The outer call checks lifecycle once. Nested application or assistant calls inherit the accepted scope and do not re-read lifecycle. When an outer call passes in `READY`, a later transition to `DRAINING` does not reject that already accepted call.

## Scheduler and Reminder Boundary

Scheduler checks admission before a due job is claimed or a background execution task is created. A lifecycle rejection ends that tick without claiming, persisting a run, invoking a handler, or publishing a work-started event. Reminder Bridge owns no background tick; API operations remain API-admitted and reminder handler execution inherits Scheduler admission.

## Failure Propagation

Internal callers receive the original `FailureException`. Codes remain centralized:

- `CREATED` / `STARTING`: `system.not_ready`
- `DRAINING`: `system.draining`
- `STOPPED`: `system.stopped`
- `FAILED`: `system.failed`

All use category `unavailable`, component `system.lifecycle`, operation `admit_request`, and `retryable=true`.

## Alternatives Considered

- Repeating a check in API, runtime, assistant, task, and workflow layers was rejected because it can terminate already accepted work after shutdown starts.
- Injecting `SystemContainer` into business modules was rejected because it creates a broad dependency and a construction cycle.
- Passing a caller-controlled metadata flag was rejected because it permits accidental admission bypass.

## Compatibility

SP-007 HTTP 503 behavior, `Retry-After: 1`, public health endpoints, API authentication, and CORS behavior remain unchanged. Product version remains `0.33.0`.

## Testing Strategy

Tests cover all lifecycle states, complete `FailureInfo`, exact-once nested checking, side-effect-free rejection, accepted-work races, Scheduler dispatch rejection, real Composition Root identity wiring, API/security regression, lifecycle regression, and the full suite.

## Known Limitations

There is still no in-flight counter, drain timeout, forced cancellation, distributed gate, or zero-downtime guarantee. Recovery and migration policy remains explicitly outside this work-admission boundary.
