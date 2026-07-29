# ADR-011：模型无关原则

## 状态
Accepted (2026-07-12)

## 背景
AI-Lab 的 `MODEL_POLICY.md` 规定“业务层禁止直接绑定具体模型”。该原则必须由架构机制落实，不能只停留在政策文档中。

## 决策
Provider Layer is the **sole enforcement point** for model agnosticism:

1. 所有 LLM 访问都通过 `LLMProvider.generate()`，不得直接调用 `openai.ChatCompletion.create()`。
2. 所有 Embedding 访问都通过 `EmbeddingProvider.embed()`，不得直接调用 `openai.Embedding.create()`。
3. 所有向量访问都通过 `VectorProvider.search()`，不得直接调用 `chromadb.Collection.query()`。

Upper layers import from `core.providers.llm`, not from `openai`, `anthropic`, or `ollama`.

Switching from OpenAI to a local model requires:
- Changing one `ProviderConfig` entry
- Zero changes to Agent or Knowledge code

## Enforcement
- 代码审查规则：在 `core/providers/` 之外出现任何 `import openai`、`import chromadb` 或 `import anthropic` 都视为违规。
- All provider adapter packages go in `core/providers/{type}/adapters/` (future)
- Test suites use MockProvider, never mock real SDKs directly

## 后果
- Adds one extra abstraction layer (the cost of agnosticism)
- Enables A/B testing of different models with zero code changes
- Makes local-first deployment (Ollama) a config option, not a rewrite
