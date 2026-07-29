# ADR-010：Provider Registry 模式

## 状态

Accepted（2026-07-12）

## 背景

Provider Layer 需要管理 LLM、Embedding、Vector 和 Storage 等多种 Provider，每种类型
又可能有多个实现，例如 OpenAI 与 Ollama、Chroma 与 FAISS。系统必须能够确定哪些
Provider 可用，以及如何访问它们。

## 决策

采用 Registry + Factory 模式：

- `ProviderRegistry` 保存 Provider factory callable，而不是实例；第一次 `get()` 时延迟
  创建，并支持按类型、名称和 capability 查询；
- `ProviderFactory` 由配置驱动，读取 `ProviderConfig` 列表，按 `enabled` 过滤、按
  `priority` 排序、完成初始化，并提供 `get_llm()`、`get_embedding()` 等类型化入口。

业务代码不得直接调用 `MyProvider()`；所有访问统一经过 `registry.get(type, name)`。

## 已考虑的替代方案

- **Service Locator**：拒绝。依赖隐式且不利于测试；
- **DI container**：拒绝。对当前规模过度设计，并引入框架依赖；
- **直接实例化**：拒绝。违反依赖倒置，也无法热切换。

## 后果

- Provider 生命周期由 `registry.shutdown_all()` 集中管理；
- 可通过扫描注册元数据发现 capability；
- Mock Provider 与真实 Provider 可在不改调用代码的前提下替换；
- 测试可以创建独立 Registry 并注册 Mock Provider，隔离简单。
