# ADR-043：Reminder 管理协调边界

**状态：** Accepted
**日期：** 2026-07-17

## 验收记录

- 由 SP-011 Accepted；
- PR：#23；
- Approved Head：`beb99115dd273a9fe55e86d21e65f714e7f7f52f`；
- Merge Commit：`5c4b442b2b5c7f934ac381020ba8b310976d5d3a`；
- Accepted Date：2026-07-17。

## 背景

Reminder 取消和重新计划会同时影响 Reminder 与 Scheduler 持久化。若 API、CLI 和
CEO Assistant 分别实现规则，会产生互相冲突的 terminal、Workspace、idempotency 与
recovery 行为。

## 决策

创建由组合根拥有的 `ReminderManagementService`。它解析工作空间可见 Reminder、执行
terminal 规则、映射稳定 failure、记录 hashed reschedule idempotency metadata，并将写入
委托给既有 `ReminderSchedulerBridge` Saga。

API、CLI 和 CEO Assistant 可以格式化结果，但不得直接更新 Reminder Repository 或
Scheduler Job。精确 ID 必须经过 Workspace 检查；标题匹配只有在得到唯一可见结果时执行。

取消操作是幂等的。Triggered 和 failed Reminder 不得取消。Reschedule 可以恢复 failed
Reminder，但 triggered 与 cancelled 保持 terminal。Bridge failure 以
`reminder.cancellation_failed` 或 `reminder.rescheduling_failed` 返回，并保留可查询的
持久化恢复状态。

## 后果

- 所有用户入口共享一个管理合同；
- 既有 Saga/reconciliation 是唯一跨数据库协调机制；
- 不宣称跨 SQLite 原子事务；
- 外部通知、批量操作、模糊解析、身份与 RBAC 延期处理。
