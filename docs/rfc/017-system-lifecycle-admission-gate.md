# RFC-017: System Lifecycle Admission Gate

## Status
Adopted

## Adoption Record
Implemented by SP-007. Merged via PR #14.

Merge Commit: `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`

Adoption Date: 2026-07-16

## Context
SystemContainer currently uses boolean flags (_started, _starting, _stopped) to track lifecycle. New work can be admitted during shutdown, accessing partially closed components. There is no unified admission gate.

## Decision
1. Replace boolean flags with a canonical SystemLifecycleState enum
2. Add ensure_accepting_work() that raises FailureException unless READY
3. FastAPI protected business-route dependencies use the gate
4. Health endpoints bypass the gate via unguarded access
5. CREATED state can shut down directly to STOPPED (no component cleanup)

## Consequences
- All business API calls are rejected during DRAINING/STOPPED with HTTP 503
- Draining responses include Retry-After: 1
- Concurrent shutdown is idempotent via _shutdown_task
- RESTART is not supported: STOPPED -> STARTING is forbidden

## Admission Scope
SP-007 admission scope is limited to FastAPI protected business routes through `get_system()` and `ensure_accepting_work()`.

Excluded from SP-007: direct `ApplicationRuntime` calls, direct `CEOAssistant` calls, and CLI entry points. These paths do not currently receive an injected admission callback and are not represented as covered by this RFC.

SP-008 — Internal Work Admission Boundary is Candidate / Not started / No branch / No PR. It will define the canonical internal execution boundary and inject the lifecycle admission callback there without duplicating lifecycle flags in business modules.
