# ADR-066：确定性引用解析与一次性确认状态机

## 元数据

| 字段 | 值 |
|---|---|
| ADR 编号 | ADR-066 |
| 状态 | Proposed / Pending Independent Review |
| 关联 RFC | RFC-030 |
| Product SP | SP-021 |
| 日期 | 2026-08-03 |

## 1. 背景

用户会说“第一条”“刚才那个任务”或“不是第一条，是第二条”。LLM 能提出意图候选，却不能安全决定数据库对象、revision 或是否已经执行。现有 CEO Assistant 的自然语言 handler 依赖显式 canonical ID，并没有统一 Preview/Confirm 门禁。

## 2. 决策

SP-021 采用两层安全边界：

1. LLM 只生成受限结构化 Proposal；确定性 resolver 只能在当前有效 Interaction View 内得到唯一 canonical target。
2. 所有高价值写入先生成零业务副作用的 Action Preview，再以持久 CAS、一次性 token、expected revision 和 canonical idempotency 执行。

任何模糊、过期、跨 workspace、类型冲突、unsupported action、参数不完整或 Provider failure 都 fail closed。

## 3. 引用解析规则

### 3.1 View 选择

- 默认只选 `(workspace, session_id, channel)` 唯一 current active View。
- 显式 View ID 仍需同一 workspace/session；不同 channel 继续必须由调用方显式携带引用上下文。
- 无 View、多个 current、过期或 superseded 均不 fallback 到历史列表。

### 3.2 序数引用（ordinal）

- 中文序数和数字规范化为 1-based `display_index`。
- 精确命中一项才成功；越界、重复或无法解析均失败。
- “任务/提醒/等待事项”等 type hint 必须与 `source_type` 精确兼容。
- 结果返回 View snapshot 中的 source type/ID/revision，随后 fresh canonical read。

### 3.3 指示引用（deictic）

- “最后一条”解析为当前 View 最大 index。
- “这条/上面的”只接受 channel adapter 提供的唯一 reply/reference token。
- “刚才那个”只接受本 session/channel 最近一次成功 resolution 或 pending Preview 的唯一 target；terminal/superseded 后失效。
- 多个语义候选不做概率选择，不以标题模糊查询数据库。

## 4. Proposal 确定性校验器

允许字段只有 reference type/value/type hint、allowlisted action、action-specific arguments。禁止 Provider 指定任意 canonical ID、confirmation、workspace、revision、idempotency key 或 service method。

```text
Provider output
-> strict schema
-> workspace/session/channel
-> current View
-> unique resolution
-> fresh canonical read
-> source state + allowed action
-> normalized arguments/time
-> expected revision
-> Preview
```

Mock Provider 与真实 Provider 使用同一 validator。Provider unavailable、timeout、invalid JSON、extra field 或 unsupported action 均为零 canonical side effect。

## 5. Preview 状态机

| 当前状态 | 事件 | 新状态 | Canonical 写入 |
|---|---|---|---|
| — | create | pending | 0 |
| pending | cancel | cancelled | 0 |
| pending | TTL | expired | 0 |
| pending | modify | superseded + new pending | 0 |
| pending | confirm CAS winner | confirmed | 尚未 |
| confirmed | canonical success | consumed | 1 次 |
| confirmed | safe failure/stale | failed | 0 或由 canonical facts 明确 |
| consumed | repeat confirm | consumed + same result | 0 新写入 |
| cancelled/expired/superseded/failed | confirm | 状态不变 + FailureInfo | 0 |

`confirmed` 表示执行 claim 已被唯一持有，不表示业务成功；只有 `consumed` 才表示 canonical service 成功并已保存可对账结果。

## 6. Confirm、Cancel 与 Modify

- Confirm 必须提交 preview ID、一次性 confirmation token 和完整 workspace/session/channel。
- token 服务端随机生成、数据库存 hash；不作为 user authorization 的替代。
- Confirm CAS winner 重读 canonical object，比较 expected/actual revision 和状态，再调用唯一 adapter。
- Cancel 只允许 pending → cancelled；重复 cancel 可幂等返回 cancelled。
- Modify 不编辑原 Preview。旧 Preview superseded，新 reference/arguments 重新验证后生成新 ID、token、expiry 与 idempotency key。
- 修改目标（“不是第一条，是第二条”）必须重新解析当前 View；若 View 已替换则要求先刷新。

## 7. 执行与结果事实

执行 adapter 只能调用现有 `UserTaskService`、`ReminderManagementService`、`WaitingForService`、`InboxService`、`WorkLogService`。它必须保留领域层 revision、claim、Saga 与 idempotency 语义，不直接写 repository/SQLite。

执行结果来自 service return + canonical read；执行后再刷新 Daily Review/Agenda。刷新失败不撤销已成功动作，而返回 `result_refresh_failed` 并保留 consumed result。

## 8. 并发、重启与 crash gap

- Preview state/revision/token 用单 transaction CAS claim；并发只有一个 caller 调 service。
- idempotency key 由服务端从 Preview identity 稳定生成，不接受 Provider 值。
- pending 重启后不自动执行；用户仍需显式确认且未过期。
- confirmed 重启后进入 reconciliation，不直接重放。先查询 canonical result/target facts；只有能证明未执行且安全重试才调用。
- 若某 canonical action 无可靠 idempotency/reconciliation，则它不能进入 SP-021 allowlist，直到前置缺口解决。

## 9. FailureInfo 语义

至少区分 View not found/expired/superseded、reference not resolved/ambiguous、action not allowed、Preview not found/expired/cancelled/consumed/superseded、stale revision、workspace mismatch、invalid proposal、provider unavailable、canonical failure、refresh failure。

所有 failure 都携带 trace，审计记录 View/Preview/target/revision/action/outcome；不得记录 token、secret 或依赖原始自然语言才能解释的关键事实。

## 10. 后果

### 正面

- 用户无需知道 canonical ID，安全性仍由确定性映射而非模型概率保证。
- Preview 前业务零写入；修改、取消、重复确认都有可验证状态。
- API、CLI 与未来渠道共享完全相同的核心语义。

### 代价

- 需要持久状态机、token、CAS、action-specific validator 与大量故障注入测试。
- 部分现有直接写入的 CEO handler 需要在实施期通过 shared contract 收口或明确兼容边界。

### 拒绝的替代方案

- 让 LLM 输出 database ID/service call：越权且不可审计。
- 用自然语言“确认”直接重跑原 prompt：无法稳定绑定对象、revision 或参数。
- 原地修改 Preview：破坏审计与 token/idempotency 边界。
- 仅依靠单进程锁：不具备重启和重复请求安全。

## 11. 状态

该决策为 Proposed / NOT ACCEPTED，不能据此开始实现。独立审查和 Owner Implementation Approval 是后续强制门禁。
