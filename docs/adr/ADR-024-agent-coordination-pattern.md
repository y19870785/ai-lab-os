# ADR-024: Agent Coordination Pattern

**Date:** 2026-07-13
**Status:** Accepted

## Context

AI-Lab 需要支持多 Agent 协作。有两种主要模式：
1. **Peer-to-Peer**：Agent 直接互相发现和通信
2. **Orchestrator**：中心协调器管理 Agent Team

## Decision

采用 **Orchestrator 模式**。

理由：
- 单入口：Application 层只需和 Orchestrator 交互
- 可控：协调逻辑集中管理，便于审计和调试
- 可扩展：未来可在 Orchestrator 下增加 Scheduler/Planner 策略
- 与 AI-Lab 分层架构一致：每层有单一职责入口

## Consequences

- Agent Runtime 保持独立，不感知其他 Agent
- Orchestrator 成为 Multi-Agent 唯一入口
- 通信通过 AgentMessageBus 而非直接调用
- 任务委派复用 Task Runtime
