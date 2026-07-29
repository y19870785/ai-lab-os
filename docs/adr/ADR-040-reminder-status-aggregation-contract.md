# ADR-040：Reminder 状态聚合合同

## 状态

Accepted

## 验收记录

- 由 SP-009 Accepted；
- PR：#19；
- Merge Commit：`b1274d066cbc01053144cba8d5654a5f8c8a21da`；
- Accepted Date：`2026-07-16`。

## 背景

Reminder 生命周期事实分布在 UserTask、Reminder、Scheduler Job、JobRun 和
ReminderOccurrence 中。单个数据库 Row 或 EventBus Event 不能构成稳定的用户可见结果。

## 决策

`ReminderStatusView` 是站内读取合同。它按需从持久化 Service 组合，暴露标识符、计划
时间与 timezone、组件状态、最新 occurrence、最新脱敏 `FailureInfo` 和 retryability。

聚合状态规则：

- Reminder cancelled 时为 `cancelled`；
- Reminder 或最新 occurrence triggered 时为 `triggered`；
- Scheduler Job retrying 时为 `retrying`；
- Reminder 或 Scheduler failed 时为 `failed`；
- 其他情况为 `scheduled`。

API 暴露 `GET /reminders/{reminder_id}/status`，CLI 暴露
`python -m cli reminder-status <reminder_id>`。两者解析同一个组合根 Service。LLM 文本、
日志、EventBus Event 和内存 Cache 不作为权威来源。

## 后果

- 重启后仍可查询状态，无需人工查看 SQLite；
- 可以展示失败而不泄露内部异常文本；
- 既有组件 Enum 仍是权威，不创建第二个领域 Enum；
- 当前 View 表示一个 Reminder 及其最新 occurrence，不是完整 Inbox。
