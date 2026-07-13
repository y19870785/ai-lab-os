# ADR-016: Tool Registry Pattern

**Status:** Accepted
**Version:** v0.18.0
**Date:** 2026-07-12

## Context

AI-Lab needs to support a growing number of tools (100+) across multiple categories. Each tool must be discoverable by name, category, tag, and capability. Tools must be lazily instantiated to avoid startup cost.

## Decision

Adopt **Registry + Factory** pattern:

- `ToolRegistry` holds `ToolInfo` metadata and a `ToolFactory` callable for each tool.
- Tools are NOT instantiated at registration time.
- On first `get(name)`, the factory is called and the instance is cached.
- `search()` supports filtering by category, tag, and name pattern.

## Alternatives Considered

1. **Direct instantiation at registration** — Rejected. Would eagerly load all tools, increasing startup cost and memory for rarely-used tools.
2. **Service Locator / DI container** — Rejected. Overkill for current needs; simple dict-based registry is sufficient and testable.
3. **Auto-discovery only** — Rejected. Explicit registration gives control over tool metadata; auto-discovery will be layered on top.

## Consequences

- **Positive:** Lazy loading, low startup cost, simple and testable.
- **Negative:** Factory functions must be pure (no side effects); cached instances mean tool state persists across calls — acceptable for stateless tools but requires attention for stateful ones.
