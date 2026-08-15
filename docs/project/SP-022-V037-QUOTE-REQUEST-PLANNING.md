# SP-022 — v0.37 Quote Request 规划基线

> 状态：PLANNING_BASELINE_PROPOSED / PENDING_INDEPENDENT_PLANNING_REVIEW / IMPLEMENTATION_NOT_AUTHORIZED / ACC_022_NOT_EXECUTED
> 日期：2026-08-15
> Canonical Base：`f01a8c74ab280af25b1d15453daf0a2216f05c6a`

## 目标与边界

SP-022 只规划客户报价需求的可信写入闭环，不实现报价计算、ERP/CRM 集成、自动外发、身份/RBAC 或跨 workspace 共享。当前仓库版本仍为 v0.35.0 Alpha，`project_state.json` 的 Current Product SP 仍为 None；本规划不改变任何机器治理状态。

本规划包由 [RFC-034](../rfc/034-quote-request-trusted-write-contract.md)、[ADR-074](../adr/ADR-074-quote-follow-up-next-action-ownership.md)、[ADR-075](../adr/ADR-075-inbox-to-quote-request-reconciliation.md) 与 [ACC-022](../acceptance/SP-022-quote-request.md) 共同组成。它们均为待独立审查的规划合同，不构成产品实现授权。

## Canonical 对象与所有权摘要

| 对象 | 唯一 owner | SP-022 关系 |
|---|---|---|
| Quote Request | Quote bounded context | 新 canonical aggregate；持有状态、revision 与审计关联 |
| Customer / Contact | Quote bounded context 内的 canonical entity | 仅在本边界内建模；不得同时引用第二套同名 canonical store |
| Follow-up | Waiting-For canonical domain | Quote 只保存 Waiting-For ID 引用；不得复制责任人、状态或到期事实 |
| Next Action | Quote Request child value | 由 Quote 状态转换产生；Daily Review 只读投影，Action Hint 只展示 |
| Audit | AI-Lab Audit/Verified Result boundary | 记录 mutation、失败与 read-back 证据，不由 LLM 文本代替 |

所有 create/read/list/transition 必须带完整 `WorkspaceKey`，并在 repository 查询和写入条件内强制隔离。跨 workspace 引用、存在性探测与写入均 fail closed。

## 可信写入合同摘要

- Quote Request ID 一次生成、全局稳定且永不复用；Customer/Contact/Follow-up 引用必须与 Quote Request 属于同一 workspace。
- revision 从 `1` 开始；每个 mutation 使用 expected revision/CAS，成功后递增 1，stale revision 不得覆盖。
- create 与 transition 使用 workspace-scoped idempotency key；同 key 同 payload 返回同一 canonical result，同 key 异 payload返回稳定冲突。
- 最小状态机为 `DRAFT -> QUALIFIED -> READY_FOR_QUOTE -> CLOSED_WON/CLOSED_LOST/CANCELLED`，仅 `CANCELLED` 可经人工确认 reopen 为 `DRAFT`；非法跃迁 fail closed。
- command accepted、HTTP 2xx 或 CLI exit 0 本身不是业务成功。只有持久化后的 canonical read-back 与匹配 revision/audit evidence 才能形成 Verified Result。
- 错误必须映射稳定 `code/category/component/operation/retryable`，覆盖 workspace mismatch、not found、revision/idempotency conflict、invalid transition、validation、persistence 与 downstream projection failure。

完整合同见 RFC-034；本文件不替代其字段与失败语义。

## 交付切片

| 切片 | 内容 | 授权边界 |
|---|---|---|
| A — Canonical Core | domain、repository、persistence、state machine、audit、CLI/API | 需要单独实现授权；不得夹带其他 Slice |
| B — Capture Integration | Inbox -> Quote Request、idempotency、reconciliation | 需要 Slice A 完成后单独授权 |
| C — Read Projection | Daily Review projection、Next Action presentation | 只读消费 canonical read model；不得反向写 Quote |
| D — Conversational Entry | CEO Assistant intent mapping | `SEPARATE_AUTHORIZATION_REQUIRED / NOT_PART_OF_INITIAL_IMPLEMENTATION_AUTHORIZATION` |

CEO Assistant 当前为 `FREEZE`。Daily Review 与 CEO Assistant 均不得暗中进入首个 core implementation slice。

## 治理交付与成功标准

| 阶段 | 交付物 | 当前状态 |
|---|---|---|
| 规划 | 本文件、RFC-034、ADR-074、ADR-075、ACC-022 | 待独立 planning review |
| 实现 | Slice A；其余 Slice 分别授权 | NOT_AUTHORIZED |
| 验收 | ACC-022 场景逐项执行并保留证据 | 0_EXECUTED / NOT_PASSED |

未来实现只有在 CLI/API 获得 canonical read-back、匹配 revision、Audit 与 Verified Result 后才能声明业务成功。Inbox reconciliation、Daily Review projection 与 CEO Assistant 分别按 Slice B/C/D 验证；真实 Provider 不参与写入正确性证明。

## 非目标与禁止事项

- 不修改 `project_state.json`，不把 v0.37 标为 Current Product SP。
- 不创建 Quote domain、API、CLI、container、factory、数据库或产品测试实现。
- 不把 RFC 标为 Adopted、ADR 标为 Accepted、ACC 标为 Passed。
- 不授权 Ready、Merge、Tag、Release 或任何后续实现。
