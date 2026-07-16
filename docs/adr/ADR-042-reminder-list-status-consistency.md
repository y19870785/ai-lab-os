# ADR-042: Reminder List Status Consistency

## Status

Proposed / SP-010 implementation candidate

## Context

Reminder 的用户状态由 UserTask、Reminder、Scheduler Job 与最新 ReminderOccurrence 共同决定。若列表与单条详情各自维护判断逻辑，同一 Reminder 可能在两个入口显示不同状态。

## Decision

ADR-040 的 `aggregate_reminder_status()` 是用户层状态的唯一聚合函数。单条 `ReminderStatusView` 与列表 `ReminderInboxItem` 必须调用同一个共享构建路径，统一输出 `scheduled`、`retrying`、`triggered`、`failed` 或 `cancelled`。

Scheduler 的 `completed` 等底层状态可以作为附加字段返回，但不得替代用户状态。LLM、EventBus、日志和内存缓存不得参与状态判断。API、CLI 和自然语言列表只消费 `ReminderInboxService` 的持久化结果。

## Consequences

- 单条详情与 Inbox 对同一 Reminder 返回相同用户状态；
- 状态规则修改只发生在 ADR-040 的共享实现；
- Inbox 可以附带底层诊断字段而不暴露第二套状态真相；
- 跨数据库读取仍不是快照事务，极窄并发窗口可能观察到相邻 revision。
