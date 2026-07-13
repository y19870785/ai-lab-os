# ADR-011: Model Agnostic Principle

## Status
Accepted (2026-07-12)

## Context
AI-Lab's MODEL_POLICY.md states "业务层禁止直接绑定具体模型". This principle needs an architectural enforcement mechanism — not just a policy document.

## Decision
Provider Layer is the **sole enforcement point** for model agnosticism:

1. All LLM access goes through `LLMProvider.generate()` — never through `openai.ChatCompletion.create()`
2. All embedding access goes through `EmbeddingProvider.embed()` — never through `openai.Embedding.create()`
3. All vector access goes through `VectorProvider.search()` — never through `chromadb.Collection.query()`

Upper layers import from `core.providers.llm`, not from `openai`, `anthropic`, or `ollama`.

Switching from OpenAI to a local model requires:
- Changing one `ProviderConfig` entry
- Zero changes to Agent or Knowledge code

## Enforcement
- Code review rule: any `import openai` / `import chromadb` / `import anthropic` outside `core/providers/` is a violation
- All provider adapter packages go in `core/providers/{type}/adapters/` (future)
- Test suites use MockProvider, never mock real SDKs directly

## Consequences
- Adds one extra abstraction layer (the cost of agnosticism)
- Enables A/B testing of different models with zero code changes
- Makes local-first deployment (Ollama) a config option, not a rewrite
