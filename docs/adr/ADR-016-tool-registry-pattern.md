# ADR-016：Tool Registry 模式

**状态：** Accepted
**版本：** v0.18.0
**日期：** 2026-07-12

## 背景

AI-Lab 需要支持跨多个类别、数量可能超过 100 的 Tool。每个 Tool 必须能够按名称、类别、
Tag 和 capability 发现，并延迟实例化以避免启动成本。

## 决策

采用 Registry + Factory 模式：

- `ToolRegistry` 保存每个 Tool 的 `ToolInfo` 元数据与 `ToolFactory` callable；
- 注册时不得实例化 Tool；
- 第一次 `get(name)` 时调用 factory，并缓存实例；
- `search()` 支持按类别、Tag 和名称模式过滤。

## 已考虑的替代方案

1. **注册时直接实例化**：拒绝。会预加载全部 Tool，增加启动成本和低频 Tool 的内存占用；
2. **Service Locator / DI container**：拒绝。对当前需求过重，字典式 Registry 已足够且易测；
3. **仅使用自动发现**：拒绝。显式注册可以控制 Tool 元数据，自动发现可在其上分层实现。

## 后果

- **正面：** 延迟加载、启动成本低、结构简单且易测；
- **负面：** Factory 必须无副作用；缓存意味着 Tool 状态会跨调用保留，无状态 Tool 可接受，
  有状态 Tool 需要额外注意。
