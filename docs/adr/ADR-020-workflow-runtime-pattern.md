# ADR-020: Workflow Runtime Pattern

**状态：** Accepted
**版本：** v0.20.0
**日期：** 2026-07-12

## 上下文

AI-Lab 需要从单次 Agent 调用升级为多步骤任务编排。需要决定：Workflow 是作为 Agent 的扩展（Agent 内部循环），还是独立为一层。

## 决策

**Workflow 独立为一层**，位于 Application 和 Agent 之间：

- WorkflowRuntime 是任务调度中心
- Agent Runtime 是被调度的执行单元
- Agent 不需要知道自己在 Workflow 中

理由：
1. 职责分离：Agent 负责「如何执行」，Workflow 负责「何时执行什么」
2. 可组合：同一个 Agent 可被不同 Workflow 复用
3. 可恢复：Checkpoint 属于 Workflow 层，Agent 不应感知

## 替代方案

1. **Agent 内部循环**：ReAct / Chain-of-Thought 循环在 Agent 内部。拒绝——Agent 与任务编排耦合，无法跨 Agent 编排。
2. **LangGraph 风格 StateGraph**：作为独立库引入。拒绝——引入外部依赖，不如自建轻量 Runtime。

## 后果

- **正面**：清晰的层边界，Agent 和 Workflow 可独立演进。
- **负面**：多了一层间接调用，每步都走 Workflow→Agent，但这是必要的代价。
