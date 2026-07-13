# ADR-021: Workflow State Machine

**状态：** Accepted
**版本：** v0.20.0
**日期：** 2026-07-12

## 上下文

Workflow 有 11 种状态（CREATED → READY → PLANNING → RUNNING → WAITING → RETRYING → PAUSED → RESUMED → COMPLETED / FAILED / CANCELLED），状态转换必须严格受控。

## 决策

采用**中心化状态机（WorkflowStateMachine）**：

- 所有状态转换通过 `transition()` 方法
- 非法转换抛出 `WorkflowStateError`
- 状态转换表集中定义在 `_VALID_TRANSITIONS` 中
- 任何模块不得直接修改 Workflow 状态字段

## 为什么不用事件驱动状态机

事件驱动状态机（如 `transitions` 库）适合复杂的事件→状态映射，但 Workflow 的状态转换是线性的、可预测的。中心化状态机更直观、更易调试。

## 状态转换表

| 当前状态 | 允许的下一状态 |
|---------|--------------|
| CREATED | READY |
| READY | PLANNING, CANCELLED |
| PLANNING | RUNNING, FAILED, CANCELLED |
| RUNNING | WAITING, PAUSED, COMPLETED, FAILED, CANCELLED |
| WAITING | RUNNING, RETRYING, CANCELLED |
| RETRYING | RUNNING, FAILED, CANCELLED |
| PAUSED | RESUMED, CANCELLED |
| RESUMED | RUNNING |
| COMPLETED | (终态) |
| FAILED | RETRYING |
| CANCELLED | (终态) |

## 后果

- **正面**：状态转换可预测、可审计、可测试。
- **负面**：新增状态需修改状态机核心表，但这迫使团队在新增状态前充分思考。
