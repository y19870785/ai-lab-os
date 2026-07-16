# ADR-035: System Lifecycle State Machine

## Status
Accepted

## Acceptance Record
Implemented by SP-007 and merged via PR #14.

Merge Commit: `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`

Accepted Date: 2026-07-16

## Scope
The state machine is the source of truth for `SystemContainer` and FastAPI protected-route admission in SP-007. Direct application, CEO Assistant, and CLI execution admission is deferred to SP-008 candidate.

## Context
The system needs a single source of truth for its operational state.

## Decision
Use LifecycleStateMachine with states: CREATED, STARTING, READY, DRAINING, STOPPED, FAILED. Transitions are protected by asyncio.Lock. Invalid transitions raise InvalidLifecycleTransitionError.

## Consequences
- Only READY state accepts work
- CREATED -> STOPPED is a valid shutdown-before-start path
- No restart from STOPPED
