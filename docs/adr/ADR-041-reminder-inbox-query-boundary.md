# ADR-041: Reminder Inbox Query Boundary

## Status

Proposed / SP-010 implementation candidate

## Context

单条 Reminder 聚合状态已经由 ADR-040 定义，但列表查询需要跨 UserTask、Reminder、Scheduler Job 与 ReminderOccurrence 读取事实。它们并不共享一个数据库连接，也没有可诚实声明的跨库 SQL JOIN。

## Decision

Composition Root 创建唯一 `ReminderInboxService`。该服务通过 Reminder Repository 的稳定 SQL 分页读取候选记录，用关联 UserTask 校验 workspace，然后复用 ADR-040 的共享聚合函数读取 Scheduler Job 与最新 Occurrence。

Repository 排序固定为 `remind_at ASC, id ASC`。Service 采用固定 100 条扫描批次，只保留 `limit + 1` 个匹配项，以此计算 `has_more`。API、CLI 与 CEO Assistant 共用同一服务和 `ReminderInboxPage`，不得各自拼接状态。

## Consequences

- 查询结果来自持久化真相，重启后不丢失；
- 内存占用受页大小和扫描批次约束；
- workspace 隔离由 UserTask metadata 归属决定；
- 跨库读取不是快照事务，极窄并发窗口可能看到不同组件的相邻 revision；
- 本轮不新增 Schema、索引或复制表。
