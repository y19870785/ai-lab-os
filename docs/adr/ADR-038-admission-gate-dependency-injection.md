# ADR-038: Admission Gate Dependency Injection

## Status

Accepted

## Acceptance Record

- Accepted through SP-008
- PR: #16
- Approved Head: `536d1563baaecf5d50eeefc93dfdb0dbbfe3c659`
- Merge Commit: `1858d4991379058948559cc96e2672df44e42b67`
- Accepted Date: 2026-07-16

## Context

Business modules need lifecycle admission without depending on `SystemContainer` or duplicating lifecycle error mappings.

## Decision

The Composition Root creates one `LifecycleStateMachine` and one `WorkAdmissionGate`. The same gate is injected into `SystemContainer`, `ApplicationRuntime`, `CEOAssistant`, and Scheduler. Constructors require the narrow `WorkAdmission` contract. `SystemContainer.ensure_accepting_work()` delegates to the gate.

The gate exposes a synchronous accepted-work context whose capability is bound to the current `asyncio.Task` identity. Same-Task nesting prevents duplicate lifecycle checks and preserves already accepted work. ContextVar copying into an ordinary child Task does not transfer ownership, so detached child work must pass lifecycle admission again.

Scheduler receives the same narrow contract and is the only component that calls `spawn_accepted_task()`. That method creates a fresh capability owned by the Scheduler job Task, allowing the already accepted job to complete after DRAINING without granting general child-task bypass. Test-only standalone components receive an explicit permissive implementation; production construction has no implicit permissive fallback.

Lazy exports in `core.system.__init__` prevent a package import cycle while preserving the existing public import surface.

## Consequences

- Production wiring fails closed when admission is omitted.
- Business modules do not import or retain `SystemContainer`.
- Lifecycle codes and `FailureInfo` construction remain centralized.
- No I/O, await, lock wait, or external side effect occurs during admission.
- Detached Tasks cannot turn copied context into an admission capability.
- Accepted capability propagation is explicit and limited to Scheduler-owned job Tasks.
