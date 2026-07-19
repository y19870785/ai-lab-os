# ADR-052：Inbox Resolution Idempotency

Status: Proposed

## 决策

SQLite 持久化 claim 是跨进程唯一解析权来源。进程内 `asyncio.Lock` 只可减少同一 Service 实例的重复工作，不是正确性或一致性边界。

`inbox_resolution_claims` 以 `inbox_item_id` 为主键，内部状态仅有：

- `claimed`
- `target_created`
- `completed`

解析顺序固定为：

1. 在 `BEGIN IMMEDIATE` SQLite transaction 中校验 Inbox workspace 与 pending 状态。
2. 在创建任何目标对象前插入唯一 claim，并记录解析类型与确定性 target key/ID。
3. 已存在同类型未完成 claim 时恢复该 Saga；已存在不同类型 claim 时立即返回冲突，禁止调用目标 Service。
4. UserTask 和 Work Log 使用由 Inbox Item ID 派生的确定性 ID；Reminder 使用确定性 orchestrator idempotency key，创建后写入真实 Reminder ID。
5. 目标创建完成后将 claim 更新为 `target_created`。
6. Inbox 最终状态与 claim `completed` 在同一个 Inbox SQLite transaction 中提交。

## 原因

Inbox 与既有目标对象分布在不同正式 Store 中，当前架构没有跨 SQLite 数据库的统一事务协调器。单纯在目标创建后做 Inbox revision CAS，无法阻止两个进程以不同类型各自创建目标并产生孤儿对象。

持久化 claim 把“选择唯一解析类型”前移到任何外部写入之前。不同类型竞争只有 claim 赢家能调用目标服务；同类型竞争使用相同确定性 key/ID，因此最多产生一个目标。

若进程在 claim 后崩溃，claim 仍保持 `claimed`，后续同类型请求继续幂等创建或检查目标。若在目标记录后崩溃，`target_created` claim 允许新进程跳过创建并直接完成 Inbox。无需人工删除 claim。

## 失败行为

- 目标创建失败：Inbox 保持 `pending`，同类型 claim 保持可恢复状态
- 不同类型竞争：在目标创建前返回 409 `inbox.already_resolved`
- 冲突 details 至少包含 `claimed_type`、`target_id`、`claim_state`
- Inbox/claim 最终提交失败：返回可重试的 `inbox.resolve_failed`
- 已 completed 的重复解析：返回稳定的 409 `inbox.already_resolved`
- 异常不静默吞掉，并发布不含原始长文本的失败事件

## 后果

- claim 创建早于目标对象创建，结构性阻止不同类型孤儿目标
- 跨 API worker、CLI 进程和独立 Service 实例维持唯一解析类型
- 同类型失败可由新进程继续，无永久卡死
- 不宣称不同数据库之间具备原子提交
- 后续若引入统一事务/outbox，可保持现有 API 语义并替换内部协调方式
