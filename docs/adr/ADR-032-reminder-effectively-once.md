# ADR-032：Reminder Effectively-Once Occurrence

## 状态

Accepted / SP-005 merged via PR #10

## 决策

不承诺 Handler exactly-once execution。ReminderOccurrence 通过数据库唯一约束 `UNIQUE(reminder_id, scheduled_at)`、同一记录重试和恢复逻辑，实现 effectively-once 成功记录。

## 原因

Reminder 与 Scheduler 分属不同 SQLite 数据库，业务 Handler 成功和 Job 终态提交之间存在不可消除的崩溃窗口。伪造跨库事务会掩盖真实状态。允许 Handler 重放并让领域写入幂等，可以在不引入分布式事务的情况下获得可验证恢复能力。

## 后果

- Trigger 事务同时提交 Occurrence 与 Reminder 的 triggered 状态。
- EventBus 发布发生在事务提交后，发布失败只影响 observability。
- Job terminal save 失败后可由 claim expiry 重试，已触发 Occurrence 不重复插入。
- 创建、重新安排和取消采用 pending 状态、补偿与 reconciliation。
- RUNNING Job 不允许修改 Reminder 时间；竞争窗口由 pending 状态和 scheduled-at 一致性校验阻止旧 Trigger。
- 外部通知投递、Outbox 和 recurring reminder 留给后续任务。
