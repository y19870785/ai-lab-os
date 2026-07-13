# ADR-018: Adapter Pattern

**状态：** Accepted
**版本：** v0.19.0
**日期：** 2026-07-12

## 上下文

AI-Lab 需要接入多种外部工具系统：MCP、HTTP API、Shell、Docker、Browser 等。每种外部系统有不同的通信协议、连接方式和工具发现机制。

## 决策

采用 **Adapter Pattern + Protocol 隔离**：

- `ToolAdapterProtocol`：所有适配器的统一接口（initialize / shutdown / discover / health）
- `AdapterRegistry`：统一管理所有适配器实例
- 每种适配器（MCP / HTTP / Shell）各自实现 `ToolAdapterProtocol`
- 适配器负责将外部工具包装为 `ToolProtocol`，注册到 `ToolRegistry`

上层（Agent Runtime → ToolExecutor）只依赖 `ToolProtocol`，完全不知道 Adapter 的存在。

## 替代方案

1. **直接在 ToolExecutor 中处理 MCP**：拒绝。违反单一职责，导致 ToolExecutor 膨胀。
2. **每种外部系统独立接入**：拒绝。缺乏统一管理，生命周期失控。

## 后果

- **正面**：新增外部系统只需实现一个 Adapter，不影响现有代码。
- **负面**：Adapter 层增加了一次间接调用，性能开销可忽略（毫秒级）。
