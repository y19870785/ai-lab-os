# ADR-057 — Reuse Inbox Resolution Claims for Waiting-For Conversion

Status: Accepted

## 背景

Unified Inbox 已通过 `inbox_resolution_claims` 协调 Inbox 到 UserTask、Reminder 与 Work Log 的跨数据库转换，并使用 `CLAIMED`、`TARGET_CREATED`、`COMPLETED` 三阶段恢复崩溃。Waiting-For 已是独立 canonical domain，持久化于 `followups.db`。为 Waiting-For 新建第二套转换表或状态机会复制幂等与恢复语义。

## 决策

1. Waiting-For 成为 Inbox 的新增 external target；`InboxSuggestedType.WAITING_FOR` 与 `InboxResolvedType.WAITING_FOR` 的值均为 `waiting_for`。
2. Inbox-to-Waiting-For 转换复用现有 `inbox_resolution_claims`，不新建第二套 Saga 表或转换状态机。
3. external target validation 继续要求 `target_key`；`TARGET_CREATED` / `COMPLETED` 继续要求 `target_id`，不修改 claim 状态机。
4. Waiting-For target ID 由 Inbox Item ID 稳定确定性派生；同一 Inbox Item 的所有重试使用同一 ID，不按文本相似度去重。
5. `WaitingForService.create(..., waiting_for_id=...)` 是唯一目标创建入口；InboxService、API 与 CLI 不直接访问 Waiting-For Repository。
6. `inbox.db` 与 `followups.db` 之间不声称跨数据库原子事务。
7. 转换按照 `CLAIMED → TARGET_CREATED → COMPLETED` 推进，允许在进程退出或持久化中断后从 durable claim 恢复。
8. 如果确定性 target ID 已存在，仅当已有 Waiting-For 的 `inbox_item_id` 与当前 Inbox Item 一致时允许恢复；其他同 ID 对象视为冲突，不得覆盖。
9. 同一个 Inbox Item 最多创建一个 Waiting-For；重复确认返回同一稳定目标或明确的已完成/类型冲突，不产生第二个对象。
10. UserTask、Reminder、Work Log、Note 与 Dismiss 的现有 Inbox resolution 行为和 response contract 保持兼容。

## Saga 流程

```text
claim Inbox resolution as WAITING_FOR
→ reserve deterministic target ID
→ create through WaitingForService
→ record TARGET_CREATED
→ complete Inbox resolution
```

Waiting-For metadata 最少保留 `inbox_item_id` 与 `inbox_source`，不得复制敏感 metadata、Workspace 凭据或不必要的原始上下文。

## 失败与恢复

- claim 类型冲突通过现有 Inbox conflict FailureInfo 返回。
- 目标创建失败时 Inbox 保持未完成 claim，不伪造 resolved 状态。
- 目标已创建但 Inbox 未完成时，重试验证来源关联后记录/恢复 `TARGET_CREATED` 并完成 resolution。
- Workspace 隔离继续由一等 `WorkspaceKey` 与 scoped repository 查询保证。
- Saga 不删除失败证据，也不通过 LLM 判断对象是否相同。

## 后果

- Waiting-For 转换沿用已验收的幂等、竞争与 crash-recovery 模型。
- InboxService 未来需要注入 WaitingForService，并增加 `resolve_to_waiting_for()`；API/CLI 只是 canonical Service 的适配层。
- 跨数据库仍是可恢复的 Saga，而非原子事务。
- 现有 Inbox target 类型无需改变其业务语义。

## 不包含

本 ADR 不实现 enum、Schema、Service、API、CLI 或生产代码，也不批准 SP-017 实施。它不引入自动 Reminder、Scheduler、外部通知、Recurring、LLM 写入或第二份 Inbox response contract。
