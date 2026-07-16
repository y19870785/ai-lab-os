# ADR-036: Shutdown Admission Policy

## Status
Accepted

## Acceptance Record
Implemented by SP-007 and merged via PR #14.

Merge Commit: `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`

Accepted Date: 2026-07-16

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
