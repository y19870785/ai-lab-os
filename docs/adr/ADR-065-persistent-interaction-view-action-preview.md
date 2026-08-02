# ADR-065：使用专用持久化保存 Interaction View 与 Action Preview

## 元数据

| 字段 | 值 |
|---|---|
| ADR 编号 | ADR-065 |
| 状态 | Proposed / Pending Independent Review |
| 关联 RFC | RFC-030 |
| Product SP | SP-021 |
| 日期 | 2026-08-03 |

## 1. 背景

SP-021 要在用户看到编号化工作列表后，安全保存引用映射和待确认动作。状态必须支持 TTL、workspace 隔离、重启恢复、并发确认、一次性消费、idempotency 和结构化审计。

当前 `core/memory/session.py:SessionMemory` 是进程内字典，shutdown 清空且只有惰性 TTL；`ApplicationRuntime._contexts` 同样是进程内状态。通用 Memory 可以保存 JSON，却没有 Preview 状态约束、CAS consume 或请求唯一键。Work Log/事件是业务事实或审计流，不适合成为 mutable pending execution authority。

## 2. 决策

如果 SP-021 获得 Implementation Approval，实施应新增一个专用 logical database（建议 `interaction.db`）及 additive schema initialization/migration step。数据库是真相源，进程内对象只能是可丢弃缓存。

建议逻辑实体：

- `interaction_views`：workspace tuple、session、channel、state、revision、created/expiry/current scope。
- `interaction_view_items`：1-based display index、source type/ID/revision、status/reason/title/action snapshot。
- `action_previews`：View/target/revision/action/arguments、token hash、idempotency、state/result/failure。
- `interaction_audit_events`：不可变的结构化 lifecycle 与 execution facts。
- 可选 `interaction_requests`：若 View/Preview 表不能清晰承载 request-level idempotency，再独立创建。

所有 lookup 和唯一键必须以 canonical workspace isolation tuple 为前缀。View current replacement、Preview state transition 和 confirm claim 使用 transaction + revision CAS。Preview token 只存 hash。过期判定在每次 read/transition 强制执行，cleanup 仅负责容量。

本决策不批准具体 DDL，也不在 Planning PR 创建 Schema/Migration。Phase 0 必须先冻结表结构、schema version 策略、升级/回滚与旧数据库初始化测试。

## 3. 方案比较

| 方案 | 重启 | 并发/幂等 | 审计 | 风险 | 结论 |
|---|---|---|---|---|---|
| 纯 SessionMemory | 丢失 | 无持久 CAS | 不完整 | 重启后无法判断确认结果 | 拒绝 |
| 通用 Memory JSON | 可恢复 | 缺少状态/唯一约束 | 语义松散 | 容易把内容存储误作执行权威 | 拒绝 |
| Work Log/event | 可恢复 | insert-only，不适合 pending | 强 | 无法安全 consume/cancel/modify | 仅作审计引用 |
| 每个 channel 自建状态 | 不一致 | 重复实现 | 碎片化 | API/CLI 语义漂移 | 拒绝 |
| 专用持久化 + 可丢缓存 | 可恢复 | CAS + unique idempotency | 结构化 | 新 schema 与恢复复杂度 | 接受建议 |

## 4. 生命周期约束

- 同一 `(workspace, session, channel)` 只有一个 active current View；新 View 原子 supersede 旧 View。
- Preview TTL 不晚于关联 View；View superseded 时，其 pending Preview 必须不可执行，并转 superseded 或在 confirm 时 fail closed。
- pending Preview 重启后保持 pending，但绝不自动执行。
- confirm 先 CAS claim；并发只有一个 winner。
- canonical commit 后发生 crash，必须按 idempotency/result facts 对账；不能将“无 interaction result”解释为“未执行”。
- terminal records 在审计保留期内保存；清理不得删除仍用于 idempotency/reconciliation 的事实。

## 5. Schema 与 migration 影响

现有 `core/database/migration.py` 只有固定 schema 的幂等初始化，没有正式版本迁移序列。实施至少需要：

1. 新逻辑数据库路径由 `DatabaseManager` 绑定和拥有连接；
2. `CREATE TABLE/INDEX IF NOT EXISTS` 可重复初始化；
3. 旧数据目录首次升级和重复启动测试；
4. schema 不完整/版本不支持时 fail closed；
5. backup/restore 将新数据库纳入静止数据集；
6. 不重写现有 Task、Reminder、Inbox、Waiting-For 或 episodic 表。

是否引入全局 migration framework 不属于 SP-021；优先采用对本数据库最小、显式的 schema-version 记录，避免扩成平台工程。

## 6. 后果

### 正面

- Preview 在重启、重复请求和并发确认中仍可证明一次性消费。
- workspace、TTL、revision 与 idempotency 由数据约束而非提示词保障。
- API、CEO Assistant 与未来 channel 共享同一事实源。
- 可用结构化 audit 重建动作，不依赖自然语言全文。

### 代价

- 新增数据库、repository、schema upgrade、cleanup 与 recovery 测试。
- canonical commit 和 interaction result commit 跨数据库，必须做 idempotent reconciliation，不能假装原子事务。
- 备份/恢复清单需要纳入 `interaction.db`。

### 风险控制

- action adapter 未证明 canonical idempotency 前不得进入 allowlist。
- token、prompt、secret 与不必要正文不得进入 audit。
- 多实例/HA 不在 v0.36 范围；但设计不能依赖“单进程所以无需幂等”。

## 7. 状态

该决策当前仅为 Proposed。只有 Planning PR 经独立审查并合并、Owner 明确签发 SP-021 Implementation Approval 后，才能创建 schema 或代码。
