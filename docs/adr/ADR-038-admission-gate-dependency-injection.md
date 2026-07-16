# ADR-038: Admission Gate Dependency Injection

## Status

Proposed / SP-008 implementation candidate

## Context

Business modules need lifecycle admission without depending on `SystemContainer` or duplicating lifecycle error mappings.

## Decision

The Composition Root creates one `LifecycleStateMachine` and one `WorkAdmissionGate`. The same gate is injected into `SystemContainer`, `ApplicationRuntime`, `CEOAssistant`, and Scheduler. Constructors require the narrow `WorkAdmission` contract. `SystemContainer.ensure_accepting_work()` delegates to the gate.

The gate exposes a synchronous accepted-work context. Task-local nesting prevents duplicate lifecycle checks and preserves already accepted work. Test-only standalone components receive an explicit permissive implementation; production construction has no implicit permissive fallback.

Lazy exports in `core.system.__init__` prevent a package import cycle while preserving the existing public import surface.

## Consequences

- Production wiring fails closed when admission is omitted.
- Business modules do not import or retain `SystemContainer`.
- Lifecycle codes and `FailureInfo` construction remain centralized.
- No I/O, await, lock wait, or external side effect occurs during admission.
