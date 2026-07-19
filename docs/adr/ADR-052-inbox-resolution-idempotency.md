# ADR-052：Inbox Resolution Idempotency

Status: Proposed

## 决策

Inbox 解析采用“显式状态保护 + 确定性目标标识 + 可恢复重试”策略：

1. 只有 `pending` 项目可以进入解析。
2. 同一 Inbox Item 的进程内解析由 item ID 锁串行化。
3. UserTask 和 Work Log 使用由 Inbox Item ID 派生的确定性目标 ID。
4. Reminder 使用由 Inbox Item ID 派生的既有 orchestrator idempotency key。
5. 目标创建成功后，以 revision 条件更新 Inbox 状态。
6. 已解析或已 dismissed 的项目返回 `inbox.already_resolved`，并携带现有解析类型与目标 ID。

## 原因

Inbox 与既有目标对象分布在不同正式 Store 中，当前架构没有跨 SQLite 数据库的统一事务协调器。新增一套跨域事务框架会超出 MVP 范围。

确定性目标标识提供等价幂等保护：即使目标创建成功后 Inbox 状态更新暂时失败，重试也只能命中同一目标对象，再完成 Inbox 状态更新，不会创建第二个目标。

## 失败行为

- 目标创建失败：Inbox 保持 `pending`，返回 `inbox.resolve_failed`
- Inbox 更新失败：返回可重试的 `inbox.resolve_failed`，包含已知目标 ID
- 重复解析：返回 409 `inbox.already_resolved`
- 异常不静默吞掉，并发布不含原始长文本的失败事件

## 后果

- 满足 MVP 的重复调用安全和失败可恢复性
- 不宣称不同数据库之间具备原子提交
- 后续若引入统一事务/outbox，可保持现有 API 语义并替换内部协调方式
