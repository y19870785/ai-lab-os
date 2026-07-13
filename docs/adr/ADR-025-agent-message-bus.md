# ADR-025: Agent Message Bus Design

**Date:** 2026-07-13
**Status:** Accepted

## Context

Agent 间通信需要可靠的消息传递机制。选项：
1. 直接函数调用（耦合高）
2. 共享内存队列
3. 基于 EventBus 的消息总线

## Decision

采用 **基于 EventBus 的 AgentMessageBus**。

理由：
- 解耦：Agent 不直接依赖彼此
- 可观测：所有消息通过 EventBus 发布，可审计
- 类型安全：AgentMessage 是 Pydantic 模型
- 支持点对点、广播、请求-响应三种模式
- 消息历史可回溯

## Consequences

- AgentMessageBus 依赖底层 Event Bus
- 消息异步传递，需要处理超时
- 广播需预先知道接收者（由 Orchestrator 管理）
