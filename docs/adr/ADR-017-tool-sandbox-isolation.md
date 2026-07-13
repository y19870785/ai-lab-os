# ADR-017: Tool Sandbox Isolation

**Status:** Accepted
**Version:** v0.18.0
**Date:** 2026-07-12

## Context

Tools may execute arbitrary Python code, shell commands, or external API calls. Without isolation, a misbehaving or malicious tool could block the event loop, consume excessive resources, or crash the runtime.

## Decision

Implement a layered sandbox approach:

**Phase 1 (current):** `ToolSandbox` wraps tool execution with `asyncio.wait_for` for timeout enforcement. Exceptions are caught and returned as `ToolResult(success=False, error=...)`. This prevents event-loop blocking and crash propagation.

**Phase 2 (future):** Docker-based sandbox for Python/Shell tools — full process isolation, memory limits, filesystem isolation.

**Phase 3 (future):** Browser sandbox for browser-use tools — isolated browser context with network policy.

## Why Not Full Sandbox Now?

- Current builtin tools (Echo, Calculator, DateTime, UUID) are pure Python with no I/O — they don't need Docker isolation.
- Premature Docker dependency would add complexity and slow development velocity.
- The `ToolSandbox` abstraction is designed so that swapping `asyncio.wait_for` for a Docker executor requires zero changes to ToolExecutor or any tool implementation.

## Consequences

- **Positive:** Clean abstraction; timeout enforcement today; Docker-ready tomorrow.
- **Negative:** Current sandbox does not protect against CPU-intensive infinite loops (only async timeouts work).
