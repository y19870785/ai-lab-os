# RFC-034：Quote Request 可信写入合同

## 状态

- **状态**：DRAFT / NOT_ADOPTED
- **任务**：SP-022
- **日期**：2026-08-15
- **设计 Base**：`f01a8c74ab280af25b1d15453daf0a2216f05c6a`
- **相关决策**：ADR-074、ADR-075
- **实现状态**：NOT_AUTHORIZED

## 摘要

本 RFC 规划 Quote Request 的 canonical identity、workspace 隔离、revision/CAS、idempotency、状态机、稳定失败合同以及 Verified Result。它不创建代码、Schema 或运行时入口；任何实现均需要独立授权。

## Canonical identity 与引用

- `quote_request_id` 由 AI-Lab 在首次 create 时生成，格式规划为 `qr_<32 lowercase hex>`。生成后永久稳定、不可更名、不可回收或复用于另一业务事实。
- `customer_id` 与 `contact_id` 指向 ADR-074 规定的 Quote bounded context entity。Quote Request 保存 ID 引用，不以内嵌快照建立第二身份。
- `waiting_for_id` 是对 Waiting-For canonical item 的可选引用；Quote 不复制其 owner、status、due date 或 follow-up history。
- `next_action_id` 仅标识 Quote aggregate 内的 child value，不得与 Waiting-For ID 或 Action Hint ID 混用。
- 每个对象都持有完整 `WorkspaceKey`，或所有 repository get/list/create/transition/link 条件都必须同时匹配完整 WorkspaceKey。任何跨 workspace ID 引用、查询、关联或写入返回 `quote.workspace_mismatch`，不得泄露目标是否存在。

## Revision 与并发

- 新建 Quote Request 的 revision 固定为 `1`。
- 每个成功 mutation 原子地将 revision 增加 `1`；只读、重复返回相同结果的幂等重试不递增 revision。
- transition、update、cancel、reopen 和 link mutation 必须携带 `expected_revision`，repository 使用 workspace + ID + revision 的 CAS 条件。
- stale revision 返回 `quote.revision_conflict`，不得静默覆盖、自动重放为新 revision 或只记录 warning。
- 冲突响应返回当前可见 revision 或安全的重新读取指引，但不得跨 workspace 泄露状态。

## 幂等合同

- create 和每个 transition 都要求调用方提供 workspace-scoped `idempotency_key`；服务持久化 key、operation、规范化 payload digest 与 canonical result reference。
- 同 workspace、同 operation、同 key、同 payload 的重试返回原 Quote ID、revision 与 Verified Result，不重复生成 Quote、Audit、Waiting-For、Next Action 或投影事件。
- 同 key 不同 payload、不同 operation 或试图跨 workspace 复用时返回 `quote.idempotency_conflict`，不产生业务写入。
- persistence outcome 不明时保持可恢复的 pending/unknown 记录；调用方必须用同 key 重试或查询 reconciliation 状态，不得换 key 猜测重做。

## 最小状态机

状态：`DRAFT`、`QUALIFIED`、`READY_FOR_QUOTE`、`CLOSED_WON`、`CLOSED_LOST`、`CANCELLED`。

| 起始状态 | 目标状态 | 前置条件 | 人工确认 |
|---|---|---|---|
| create | DRAFT | Customer、Contact 与需求描述通过校验 | 是，create 写入前确认 |
| DRAFT | QUALIFIED | Customer/Contact 可读且需求完整 | 是 |
| QUALIFIED | READY_FOR_QUOTE | owner、需求范围和 Next Action 已确定 | 是 |
| READY_FOR_QUOTE | CLOSED_WON | 成交事实与证据存在 | 是 |
| READY_FOR_QUOTE | CLOSED_LOST | 未成交原因存在 | 是 |
| DRAFT/QUALIFIED/READY_FOR_QUOTE | CANCELLED | cancellation reason 存在 | 是 |
| CANCELLED | DRAFT | reopen reason 存在，重新校验引用 | 是 |

`CLOSED_WON` 与 `CLOSED_LOST` 是 terminal，不能 reopen；`CANCELLED` 是可恢复终态且只允许显式人工确认后回到 `DRAFT`。任何未列出的跃迁返回 `quote.invalid_transition`。LLM 推断、Inbox capture 或 projection refresh 均不能代替人工确认。

## 稳定错误合同

所有失败使用 `FailureInfo`，至少包含稳定 `code`、`category`、`component=quote_request`、`operation`、`retryable` 与安全 detail。

| 条件 | 机器代码 | 分类 | 可重试 |
|---|---|---|---|
| workspace mismatch / 跨域引用 | `quote.workspace_mismatch` | authorization | false |
| 对象不存在 | `quote.not_found` | not_found | false |
| stale expected revision | `quote.revision_conflict` | conflict | true |
| 同 key 异 payload/operation | `quote.idempotency_conflict` | conflict | false |
| 非法状态跃迁 | `quote.invalid_transition` | validation | false |
| 字段或引用校验失败 | `quote.validation_failed` | validation | false |
| canonical persistence 失败 | `quote.persistence_failed` | persistence | true |
| 下游 read projection 失败 | `quote.projection_failed` | downstream | true |

projection failure 不回滚已验证的 canonical Quote mutation；它必须记录独立失败和 repair cursor。persistence outcome unknown 时不得宣称成功。

## Verified Result、Audit 与成功语义

- command accepted、HTTP 2xx、CLI exit 0、Inbox claim 完成或 tool response 均不等于 mutation completed。
- mutation 提交后，服务必须按相同 WorkspaceKey canonical read-back，并验证 ID、revision、state、idempotency result 与目标引用。
- 只有 read-back 匹配且 Audit 已持久化，才产生 Verified Result；CLI/API 可以据此声明业务成功。
- Audit 归 AI-Lab Audit boundary 所有，记录 operation、actor/binding、workspace、Quote ID、before/after revision、state transition、idempotency digest reference、trace/correlation ID、result/failure code 与时间。
- `FailureInfo` 归统一错误合同所有；trace/correlation 关联 command、canonical write、projection 和 reconciliation，但不能取代 canonical ID。
- CEO Assistant 只有在 Slice D 获得独立授权后才能展示同一 Verified Result。LLM 文本、自然语言确认或模型自报不得成为成功证据。

## 恢复边界

跨 Inbox 与 Quote persistence 不声明原子事务。ADR-075 定义 claim、target create、canonical verification、linkage、completion 的 durable Saga；canonical Quote 成功而 projection 失败时保留 Quote 成功事实并安排可幂等 repair。

## 非目标与授权

- 不实现 pricing、报价单、ERP/CRM、外发或审批系统。
- 不修改 `project_state.json` 或发布状态。
- 本 RFC 为 `DRAFT / NOT_ADOPTED`；不授权任何 Slice、Ready 或 Merge。
