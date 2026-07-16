# ADR-036: Shutdown Admission Policy

## Status
Proposed / SP-007 implementation candidate

## Scope
SP-007 rejects new work at FastAPI protected business routes only. Direct `ApplicationRuntime`, `CEOAssistant`, and CLI execution paths are explicitly excluded and are planned for SP-008 candidate.

## Context
During shutdown, new work must be rejected before components are closed.

## Decision
1. First shutdown action: transition to DRAINING
2. Business admission gate rejects all non-READY states
3. Shutdown uses _shutdown_task for single-owner concurrency
4. Health/metrics remain accessible during DRAINING/STOPPED
5. Cleanup failures are tracked and reported; all components get a cleanup chance

## Consequences
- DRAINING response: HTTP 503 with Retry-After: 1
- Failed component cleanups result in FAILED final state
- DatabaseManager closes last
