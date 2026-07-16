# RFC-017: System Lifecycle Admission Gate

## Status
Proposed / SP-007 implementation candidate

## Context
SystemContainer currently uses boolean flags (_started, _starting, _stopped) to track lifecycle. New work can be admitted during shutdown, accessing partially closed components. There is no unified admission gate.

## Decision
1. Replace boolean flags with a canonical SystemLifecycleState enum
2. Add ensure_accepting_work() that raises FailureException unless READY
3. FastAPI dependencies and internal entry points use the same gate
4. Health endpoints bypass the gate via unguarded access
5. CREATED state can shut down directly to STOPPED (no component cleanup)

## Consequences
- All business API calls are rejected during DRAINING/STOPPED with HTTP 503
- Draining responses include Retry-After: 1
- Concurrent shutdown is idempotent via _shutdown_task
- RESTART is not supported: STOPPED -> STARTING is forbidden
