# ADR-031：Scheduler Action Handler

## 状态

Accepted for SP-005 candidate

## 决策

Scheduler Job 使用 `action_type` 与最小 `action_payload`，由 `ActionHandlerRegistry` 解析到显式注册的 Handler。现有 Workflow 行为封装为 `WorkflowActionHandler`，Reminder 使用 `ReminderActionHandler`。未注册 Action 必须失败并产生 FailureInfo。

## 原因

Scheduler 负责何时执行，不应依赖 CEO Assistant 或通过特殊 Workflow 名称模拟业务。显式 Handler 保持 Scheduler 与业务领域解耦，也让后续 Action 扩展无需修改 SchedulerRuntime 分派代码。

## 后果

- 旧 Job 默认迁移为 `action_type=workflow`，保持兼容。
- Handler 不拥有 Job 状态、claim 或 retry；这些职责仍属于 SchedulerRuntime/Persistence。
- Handler 不得在 Scheduler claim 事务内执行。
- Action payload 只能包含执行所需标识，不保存 UserTask 正文或私人 metadata。
