# ADR-010: Provider Registry Pattern

## Status
Accepted (2026-07-12)

## Context
Provider Layer needs to manage multiple provider types (LLM/Embedding/Vector/Storage), each with potentially multiple implementations (OpenAI vs Ollama, Chroma vs FAISS). At any given time, the system must know which providers are available and how to access them.

## Decision
Use **Registry + Factory** pattern:
- **ProviderRegistry**: Stores provider factories (callables), not instances. Lazy instantiation on first `get()`. Supports lookup by type, name, and capability.
- **ProviderFactory**: Configuration-driven. Reads `ProviderConfig` list, filters by `enabled`, sorts by `priority`, initializes all, exposes typed getters (`get_llm()`, `get_embedding()`, etc.).

No business code ever calls `MyProvider()` directly. All access goes through `registry.get(type, name)`.

## Alternatives Considered
- **Service Locator pattern**: Rejected — less testable, implicit dependencies
- **DI container**: Rejected — over-engineered for current scale, adds framework dependency
- **Direct instantiation**: Rejected — violates Dependency Inversion, no hot-swap

## Consequences
- Provider lifecycles are centralized (registry.shutdown_all())
- Capability discovery works by scanning registered provider metadata
- Mock providers can be swapped for real ones without changing calling code
- Test isolation is trivial: create a new registry, register mock providers
