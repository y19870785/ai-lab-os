# RFC-030：会话式工作交互与确认闭环

## 元数据

| 字段 | 值 |
|---|---|
| RFC 编号 | RFC-030 |
| Product SP | SP-021 — Conversational Work Interaction & Confirmation Session |
| 目标版本 | v0.36.0 Alpha / Conversational Work Assistant |
| 状态 | Planning Baseline / Pending Independent Review |
| 基线 | `5f91d9da224daa9fbb2e68f7a3ba685411e93904` |
| 关联决策 | ADR-065、ADR-066 |
| 验收合同 | ACC-021-01～ACC-021-21 |
| 更新日期 | 2026-08-03 |

## 1. 摘要与授权边界

SP-021 规划一个渠道无关的 `InteractionSessionService`，把“查看工作—引用条目—预览动作—确认/取消/修改—canonical 执行—事实刷新”收敛成同一 application contract。它不会创建第二套 Task、Reminder、Waiting-For、Inbox 或 Work Log 业务逻辑。

本文件只冻结规划合同。当前状态为：

```text
SP-021:
PLANNING_BASELINE_DEFINED /
DRAFT_PR_OPEN /
PENDING_INDEPENDENT_REVIEW /
IMPLEMENTATION_NOT_APPROVED /
NOT_STARTED

RFC-030:
PROPOSED / NOT_ADOPTED

ADR-065 / ADR-066:
PROPOSED / NOT_ACCEPTED

ACC-021:
PLANNING_BASELINE / NOT_EXECUTED
```

本轮没有产品代码、测试实现、Schema、Migration、依赖、版本、Tag 或 Release 变更。企业微信只会在未来作为合同消费者；签名、解密、`msgid` 排重、Outbox、部署和真实凭据均不属于 SP-021。

## 2. 当前代码事实审计

### 2.1 CEO Assistant 当前链路

当前链路为：

```text
cli/ceo.py:run_ceo_cli()
  -> applications/runtime.py:ApplicationRuntime.execute()
  -> applications/ceo_assistant/application.py:CEOAssistant.run()
  -> decide_intent()
  -> 各领域 handler
  -> UserTaskService / ReminderManagementService / WaitingForService /
     InboxService / WorkLogService / DailyReviewService
  -> 对应 Repository / SQLite
```

可复用事实：

- `ApplicationRequest` 携带完整 `WorkspaceKey`，`ApplicationRuntime` 是 CLI 与 API 的共同入口。
- `CEOAssistant` 已通过依赖注入调用 canonical services；Daily Review、Agenda、Inbox、Waiting-For、Reminder 和 UserTask 不需要复制。
- `core/daily_review/action_hints.py:build_action_hint()` 能从 canonical facts 生成确定性 `allowed_action`、必需参数、revision/idempotency/confirmation/claim/Saga 提示。
- 写动作当前由确定性 intent handler 直接执行，适合保留为兼容入口，但不能充当统一 Preview/Confirm 合同。

缺口：

- `cli/ceo.py` 的 `/new-session` 只返回提示文本，没有建立或轮换持久化 Interaction Session。
- `CEOAssistant._handle_chat()` 只把最近三条 Work Log 加入一次 Provider 请求；没有消息历史、Interaction View 或 Action Preview。
- `ApplicationRuntime._contexts` 是按 trace 保存的进程内字典，shutdown 后清空，不是会话存储。
- 当前自然语言写 handler 依赖显式 canonical ID，或直接执行已识别写动作；不存在“先零写入预览、后一次性确认”的通用门禁。
- Provider 自然语言回答不能作为执行成功证据。

### 2.2 API chat 当前链路

```text
api/routes/chat.py:POST /chat
  -> api/workspace.py:workspace_from_request()
  -> applications.models.ApplicationRequest
  -> ApplicationRuntime.execute()
  -> CEOAssistant.run()
  -> canonical service
  -> repository / SQLite
```

`ChatRequest` 只有输入、应用名、`session_id`、idempotency key 与 stream 标志；`ChatResponse` 没有 View、Preview、confirmation 或结构化执行结果字段。API 与 CEO Assistant 已共用 Application Runtime，但 typed domain routes 与 chat route 各自暴露能力，尚未共用 Interaction contract。

`api/middleware/context.py` 从 `X-Tenant-ID`、`X-Workspace-ID`、`X-Namespace`、`X-Session-ID`、`X-Agent-ID` 建立上下文；`workspace_from_request()` 将其传到领域层。SP-021 必须延续该链路，禁止 route 直接查库或依据自然语言文案判断成功。

### 2.3 Workspace、session、channel 与 trace

`core/workspace/models.py:WorkspaceKey` 的 canonical 隔离边界是 `tenant_id + workspace_id + namespace`；`user_id`、`session_id`、可选 `agent_id` 与 `trace_id` 是完整请求上下文。规划结论：

- Interaction View 和 Preview 必须存储并校验 canonical workspace isolation tuple；任何 lookup 均先带 workspace 过滤。
- `session_id` 表示一段交互上下文，不取代 workspace，也不能授权跨 workspace 解析。
- `channel` 是核心合同中的来源维度（`api`、`ceo_cli`、未来适配器），用于选择“当前 View/Preview”和审计，不进入 canonical 领域对象。
- 同一 session 可被不同入口显式继续，但必须提交同一 workspace；默认按 `(workspace, session_id, channel)` 选择当前 View，跨 channel 继续需显式 `interaction_view_id` 并再次校验 workspace/session。
- `trace_id` 每次请求变化，用于串联 proposal、preview、confirmation、canonical execution 与 refresh；它不是 session ID。

### 2.4 现有 persistence 评估

| 方案 | 重启/过期 | 并发/幂等 | 审计 | Schema 与成本 | 结论 |
|---|---|---|---|---|---|
| `core/memory/session.py:SessionMemory` | 进程退出即丢失；仅惰性 TTL | 无持久 CAS/唯一消费 | 不足 | 低 | 仅可做缓存，不能做事实源 |
| episodic/semantic/decision 通用 Memory | 可持久化 JSON | 无 Preview 专用状态约束、唯一消费与 workspace CAS | 通用 audit 语义不足 | 低到中 | 不作为执行权威 |
| Work Log / event | 可持久 | insert-only；不适合可变 pending 状态 | 适合结果引用 | 低 | 只作审计/结果来源，不保存可执行 Preview |
| 新增专用模型 | 可恢复、可清理 | 可做 CAS、唯一 idempotency 与原子消费 | 可记录结构化事实 | 中；新增 additive schema | 推荐 |
| 专用持久化 + 进程缓存 | 持久事实可恢复，缓存可丢 | DB 为唯一真相 | 完整 | 中 | 推荐实施形态 |

`core/database/migration.py` 只有 `CREATE TABLE IF NOT EXISTS` 的初始 schema 注册，没有版本化 migration runner；各领域 repository 也使用增量初始化。SP-021 实施必须新增专用逻辑数据库与可重复执行的 additive schema 初始化，并在实施前决定是否同时引入最小 schema-version 记录。规划 PR 不创建任何表或 migration。

### 2.5 Canonical services 与可复用安全机制

| 来源 | 现有安全能力 | SP-021 使用方式 | 已发现缺口 |
|---|---|---|---|
| `UserTaskService` | workspace 查询、revision/CAS、生命周期状态 | create/complete/cancel/reopen/update 委托；Preview 保存 expected revision | 历史 CEO 路径部分调用未强制 caller revision；adapter 必须显式读取并传递 |
| `ReminderManagementService` | get/cancel/reschedule、revision、scheduler bridge/Saga | cancel/reschedule 委托，不复制 scheduler 写入 | 时间解析只支持现有确定性子集；无法安全解析即拒绝 |
| `WaitingForService` | lifecycle CAS、append-only event、workspace | follow_up/snooze/resolve/cancel/reopen 委托 | 必须传 expected revision |
| `InboxService` | durable claim、跨服务 Saga、race/recovery | resolve/dismiss 委托，保留 claim/idempotency | 不得由 Interaction 层直接创建目标再改 Inbox |
| `WorkLogService` | canonical create/get/list、workspace | 创建 Work Log 或刷新事实；无 edit/complete/delete | 不支持的 mutation 必须 `action_not_allowed` |
| `DailyReviewService` | 五源只读聚合、排序/分页、source status | 生成 View 和执行后 refresh | `DailyReviewItem` 没有 source revision，View 创建时必须 hydrate canonical object |
| `build_action_hint()` | 纯函数 action hints | 作为 `allowed_actions` 基线 | 不是 authorization；仍需读取状态、revision 与 workspace |

### 2.6 Failure、trace、audit 与测试设施

`core/errors/models.py:FailureInfo` 已提供 code/category/component/operation/retryable/severity/trace/cause/details 与 secret-safe 序列化；`core/errors/mapping.py` 负责统一映射。`ToolAuditLogger` 是进程内且只覆盖 tool，`MemoryAuditor` 只覆盖 memory，因此不能替代 Interaction audit。

可复用测试包括：

- `tests/core/user_tasks/`：CAS、终态、restart、workspace closure。
- `tests/core/inbox/test_resolution_claims.py`：claim race、recovery、wrong workspace。
- `tests/core/reminders/`：management、repository 与 scheduler bridge/Saga。
- `tests/core/waiting_for/`：revision lifecycle、events、workspace。
- `tests/core/daily_review/`：action hints、source failure、排序分页。
- `tests/api/test_workspace_context.py` 与 chat/API tests：headers、session、workspace。
- `tests/applications/`：CEO intent、Daily Review、Waiting-For、failure presentation。
- `tests/core/errors/`：FailureInfo contract。

## 3. 目标组件边界

```text
API Route / CEO Assistant / future channel adapter
                    |
                    v
        InteractionSessionService (application layer)
          |       |         |             |
          v       v         v             v
     ViewStore  Proposal  PreviewStore  ExecutionAdapterRegistry
                   |          |             |
                   v          v             v
        deterministic validation      canonical services
                                               |
                                               v
                                     repositories / SQLite
                    |
                    v
             structured FailureInfo + AuditFact
```

核心 application contract 建议位于 `applications/interaction/`；API route 和 CEO Assistant 只做输入/输出适配与 channel-specific formatting。未来 WeCom gateway 只能调用此合同，不得拥有业务动作分支。

建议接口：

```python
create_view(query, workspace, session_id, channel, trace_id) -> InteractionResult
submit_message(text, workspace, session_id, channel, trace_id) -> InteractionResult
submit_proposal(proposal, workspace, session_id, channel, trace_id) -> InteractionResult
get_current_preview(workspace, session_id, channel, trace_id) -> InteractionResult
confirm_preview(preview_id, confirmation_token, workspace, session_id, channel, trace_id) -> InteractionResult
cancel_preview(preview_id, workspace, session_id, channel, trace_id) -> InteractionResult
modify_preview(preview_id, changes, workspace, session_id, channel, trace_id) -> InteractionResult
refresh(view_id, targets, workspace, session_id, channel, trace_id) -> InteractionResult
```

核心结果包含结构化 view/preview/execution/refresh/failure；自然语言渲染只在 channel adapter。

## 4. Interaction View 合同

```text
interaction_view_id: iv_<opaque random id>
workspace_key: canonical isolation tuple + request identity snapshot
channel: api | ceo_cli | future adapter key
session_id: non-empty canonical request session
created_at: aware UTC timestamp
expires_at: aware UTC timestamp
revision: integer, starts at 1
state: active | superseded | expired
items[]:
  display_index: 1-based contiguous integer
  source_type: user_task | reminder | waiting_for | inbox | work_log
  source_id: canonical ID
  source_revision: canonical revision or explicit null for immutable source
  status: canonical status snapshot
  reason_code: deterministic review/agenda reason
  display_title: sanitized presentation snapshot
  allowed_actions: deterministic action codes
```

规则：

1. View 只由 canonical query（优先 Daily Review/Agenda）成功结果创建；source failure 必须保留，不能伪装完整列表。
2. 稳定排序采用上游 read model 排序；编号从 1 开始、仅在本 View 内稳定，不是 canonical ID。
3. 创建时逐项 hydrate canonical object，获得真实 revision/status；对象消失或 workspace 不符则不进入可写 item，并记录 source failure。
4. 每次成功重新展示同一 `(workspace, session, channel)` 的当前列表，事务性创建新 View 并将此前 active View 标为 superseded。旧编号立即不可用于新写入。
5. 数据库可保留多个 View 供审计，但同一 scope 只有一个 current active View。显式读取旧 View可返回 superseded facts，不能解析动作。
6. 建议默认 TTL 30 分钟，配置范围 5～120 分钟；存 UTC，展示时使用 workspace/request timezone。
7. lookup 时惰性过期；后台 best-effort cleanup 只删除超过审计保留期的 terminal payload，不承担安全正确性。
8. View revision 表示 View record 的 CAS 版本；`source_revision` 表示编号建立时 canonical object 版本，二者不得混用。

## 5. 确定性 Reference Resolution

解析只接收当前 active、未过期、workspace/session/channel 匹配的 View。

### 5.1 ordinal 规则

1. 将“第一条/第一个/1号”等规范化为正整数 `n`。
2. 精确查找 `display_index == n`；0、负数、越界或重复索引均失败。
3. 若表述含类型（任务、提醒、等待事项），要求 item `source_type` 精确匹配允许同义词映射。
4. 返回唯一 `(source_type, source_id, source_revision)`；不进行标题模糊检索或跨 View fallback。

### 5.2 deictic 规则

- “最后一条”：当前 View 中最大 display index，仍需类型匹配。
- “这条/上面的”：仅在同一请求明确携带一个 UI reply/reference token 时解析；纯文本无锚点则失败。
- “刚才那个任务”：仅指本 session/channel 最近一次成功 resolve 或刚生成 Preview 的唯一目标，且类型必须是 task；取消/过期/supersede 后不再可引用。
- 同一输入出现两个不同候选、多个 active View、类型冲突或缺少锚点时返回 `reference_ambiguous` 或 `reference_not_resolved`，零写入。

LLM 只可提出 `{type, value, source_type_hint}`，不可指定任意 `source_id`。即便 proposal 携带 ID，validator 也必须拒绝，而非查询数据库。

## 6. Action Preview 合同

```text
action_preview_id: ap_<opaque random id>
interaction_view_id: required
workspace_key: required
session_id: required
channel: required
target_source_type: required
target_source_id: required canonical resolved ID
expected_revision: required for mutable targets
action: allowlisted canonical action code
arguments: normalized structured values only
effect_summary: deterministic template, never Provider assertion
created_at / expires_at: aware UTC
confirmation_state: pending | confirmed | cancelled | expired |
                    superseded | failed | consumed
idempotency_key: server-derived stable opaque key
confirmation_token_hash: stored hash only
revision: preview CAS revision
execution_result: canonical result reference or null
failure_info: structured failure or null
```

以下写入必须 Preview：Task create/update/complete/cancel/reopen，Reminder create/cancel/reschedule，Waiting-For create/follow_up/snooze/resolve/cancel/reopen，Inbox resolve/dismiss，Work Log create。只读 view/detail/refresh 不需要 Preview。

Preview 创建前后目标业务数据库必须零变化；只允许在 interaction 专用存储写入 Preview/audit facts。expected revision 来自 resolver 后再次 canonical read，arguments 经 action-specific schema 和确定性时间解析，effect summary 由模板渲染。

确认 token 是必要的防混淆能力：服务端生成高熵一次性 token，用户/adapter 回传，数据库只存 hash；token 绑定 preview、workspace、session 和 channel。CLI 可显示短确认码，API 返回 opaque token。token 不是 authorization，所有其他校验仍必须执行。

建议默认 Preview TTL 10 分钟，配置范围 1～30 分钟，且不得晚于关联 View expiry。

## 7. Preview 状态机与行为

```text
                   modify
             +-----------------> superseded
             |                       |
             |                       +--> new pending Preview
             |
created --> pending --cancel------> cancelled
             |  |
             |  +--TTL-----------> expired
             |
             +--confirm/CAS claim--> confirmed(executing)
                                      |       |
                                      |       +--safe failure--> failed
                                      +--canonical success----> consumed
```

- `pending` 是唯一可确认/取消/修改状态。
- Confirm 先在同一 transaction 以 Preview revision + state + token hash 做 CAS claim；只有 claim winner 可调用 canonical service。
- claim 后重读 target 并比较 workspace/status/revision/allowed action。stale revision 记录 actual revision，转 `failed`，不调用写服务。
- canonical 成功后保存 canonical result ID/revision，并转 `consumed`；响应必须通过 canonical get/review refresh 生成。
- 重复 Confirm 对 `consumed` 返回已保存的同一执行事实，不再次写入；对 `confirmed` 返回 in-progress/可查询，不抢执行。
- Cancel 将 pending 原子转 cancelled；之后 token 无效。
- Modify 无原地编辑：先把旧 pending CAS 为 superseded，再用重新解析/校验后的目标或参数创建新 pending Preview 与新 token/idempotency key。
- “不是第一条，是第二条”必须重新走当前 View resolution；旧 Preview superseded。
- 进程重启不会自动执行 pending；pending 可在 TTL 内恢复并由显式 confirm 继续。
- 进程在 canonical commit 后、interaction result commit 前退出时，恢复流程使用 Preview idempotency key 和 canonical service/result事实对账；不能盲重放。若目标 service 目前无法查询幂等结果，该 action 在实现前是 blocking gap。

## 8. LLM Proposal 边界

```json
{
  "reference": {"type": "ordinal", "value": 1, "source_type_hint": "waiting_for"},
  "requested_action": "waiting_for_follow_up",
  "arguments": {
    "note": "已经电话催过",
    "next_review_time_text": "后天下午"
  }
}
```

确定性流水线：

```text
natural language
-> Provider proposal (no side effect)
-> strict schema / size / enum validation
-> workspace + session + channel validation
-> current View validation
-> deterministic unique reference resolution
-> fresh canonical read
-> state + allowed_actions validation
-> argument completeness and normalization
-> deterministic time parsing
-> expected revision capture
-> confirmation policy
-> durable Action Preview
```

拒绝任意数据库 ID、View 外对象、不支持 action、缺失参数、不安全时间、跨 workspace、自动确认与 Provider 发起的 service call。Mock Provider 走相同 validator；Provider unavailable、timeout、malformed JSON 或 schema failure 均返回 FailureInfo 且 canonical DB 零副作用。禁止从失败文本猜测动作。

## 9. Canonical execution 映射

| 用户动作 | Preview 动作 | Canonical 方法 | 安全要求 | 刷新来源 |
|---|---|---|---|---|
| 完成/取消/重开任务 | `task_complete/cancel/reopen` | `UserTaskService.complete/cancel/reopen` | workspace + expected revision + Preview idempotency | service get + Review/Agenda |
| 修改任务 | `task_update` | `UserTaskService.update` | field allowlist + expected revision | service get + Review |
| 取消/改期提醒 | `reminder_cancel/reschedule` | `ReminderManagementService.cancel/reschedule` | revision + scheduler bridge/Saga + idempotency | management get + Review/Agenda |
| 跟进/延期/解决/取消/重开等待事项 | `waiting_for_*` | `WaitingForService` 同名 lifecycle 方法 | expected revision + append-only event | service get/events + Review |
| Inbox 转换/丢弃 | `inbox_resolve_* / dismiss` | `InboxService.resolve_to_* / dismiss` | durable claim + Saga/idempotency | Inbox get + target get + Review |
| 创建 Work Log | `work_log_create` | `WorkLogService.create_from_input` | workspace + idempotency boundary | service get/list + Review |
| 查看/刷新 | 无 Preview | `DailyReviewService` / `DailyAgendaService` / service get | read-only | canonical read model |

Interaction adapter 禁止直接 SQLite、复制业务状态机、跳过 workspace/revision/claim/Saga/idempotency，或用 LLM 成功文案替代数据库结果。

## 10. FailureInfo、trace 与 audit

最小错误码：

`interaction_view_not_found`、`interaction_view_expired`、`interaction_view_superseded`、`reference_not_resolved`、`reference_ambiguous`、`action_not_allowed`、`preview_not_found`、`preview_expired`、`preview_cancelled`、`preview_already_consumed`、`preview_superseded`、`stale_revision`、`workspace_mismatch`、`invalid_proposal`、`provider_unavailable`、`canonical_execution_failed`、`result_refresh_failed`。

所有失败均复用 `FailureInfo`，保持具体 code/category/component/operation/retryable/trace/details；details 只保留 opaque IDs、revision、action 和安全状态，不记录 secret、token、完整 prompt 或不必要正文。

专用 immutable `interaction_audit_events` 至少记录 workspace tuple、session/channel、View/Preview ID、target type/ID、expected/actual revision、action、confirmation outcome、canonical outcome、trace、failure code 和时间。日志不依赖自然语言即可重建事实。

`result_refresh_failed` 不回滚已成功 canonical action：Preview 保持 consumed，响应明确“执行已成功但刷新失败”，并允许安全重试只读 refresh。

## 11. 时间、过期、重启与并发

- 权威时间为可注入 clock 的 aware UTC；输入时间按请求 workspace timezone 解析，持久化 UTC。
- TTL 由 lookup/confirm 强制检查，cleanup 不是安全门禁；时钟向后漂移不得延长已记录 `expires_at`。
- View 默认 30 分钟、Preview 默认 10 分钟且不超过 View；配置变更不追溯修改已创建对象。
- 重启恢复 active/pending/confirmed/terminal records；只恢复状态，不自动执行 pending。
- 并发 confirm 由 Preview CAS claim 决出唯一 winner；canonical idempotency key 是第二道门禁。
- 客户端重复 submit 以 `(workspace, session, request idempotency key, operation)` 唯一约束返回同一 View/Preview。
- confirmed 卡住的记录由 recovery job 对账 canonical facts：能证明成功则 consumed；能证明未执行且 action 可安全重试才重试；无法证明则 failed/manual reconciliation，绝不猜测。

## 12. Schema 与 Migration 结论

结论：**SP-021 实施需要新增专用 additive schema，也需要明确的 schema initialization/migration step；本规划 PR 不创建它们。**

建议逻辑实体：

1. `interaction_views`：workspace/session/channel/current pointer、revision、state、TTL。
2. `interaction_view_items`：稳定编号、canonical source snapshot、allowed actions。
3. `action_previews`：target/revision/action/arguments/state/token hash/idempotency/result/failure。
4. `interaction_audit_events`：不可变结构化审计事实。
5. 可选 `interaction_requests`：请求 idempotency 与已生成结果引用；若合并进 Preview/View 唯一键可省略。

约束必须包括 workspace-first 索引、同 scope 唯一 active View、Preview idempotency 唯一键、state/revision CAS 与外键/应用级 referential checks。旧数据库采用 `CREATE TABLE/INDEX IF NOT EXISTS` additive 初始化，不重写现有领域表；在 Phase 0 冻结 schema version 策略和升级/回滚测试。

## 13. 实施拆分建议

单一大 PR 会同时跨 schema、application、五个领域 adapter、Provider、API/CLI 和恢复测试，审查风险过高。推荐一个 Product SP、四个有序子 PR，不建立多套 session：

1. **SP-021A — Interaction persistence + View/Reference**：schema init、repository、TTL/CAS、View hydration、deterministic resolver、workspace/restart tests。
2. **SP-021B — Preview/Confirmation + canonical adapters**：Preview 状态机、token/idempotency、五域映射、race/recovery/failure injection。
3. **SP-021C — Proposal + shared entrypoints**：strict Proposal validator、Mock/provider failure、API 与 CEO Assistant 同一 application contract、channel formatting。
4. **SP-021D — ACC-021 evidence closure**：21 项端到端、restart、workspace、并发、审计与 Review refresh 证据；只允许修复在已批准范围内发现的缺陷。

依赖顺序 A → B → C → D。每一阶段都必须独立 Quality Gate、无直写领域库、可回滚到上一阶段；Schema 首次进入 A，SP-022/企业微信不进入任何阶段。

## 14. 已定、待批准、阻塞与延期

### 14.1 已由仓库事实确定

- workspace isolation tuple 不可绕过；session/channel 不替代它。
- 所有写入必须委托 canonical services；Daily Review/Action Hint 可复用但不是执行授权。
- Provider 仅提出 proposal，确定性代码解析/校验，Preview 前 canonical DB 零写入。
- 进程内 SessionMemory 不足；持久化 Preview 与 CAS/idempotency 是重启安全前提。
- Work Log 不承担 mutable confirmation state。

### 14.2 需 Owner 在 Implementation Approval 前批准

- 专用 schema 的最终表名、版本记录方案和默认 TTL（建议 View 30 分钟、Preview 10 分钟）。
- 四子 PR 切分与每阶段授权是否沿用同一 Implementation Approval。
- confirmation token 在 CLI/API 的具体展示形式。

### 14.3 实施前阻塞项

- 为每个允许 action 证明 canonical idempotency/result reconciliation；无法证明者不得进入 allowlist。
- 冻结 Interaction failure-code 到 HTTP/application status 映射。
- 冻结清理保留期与 confirmed recovery 判定表。

### 14.4 延后 SP-022

企业微信签名、解密、`msgid`、Outbox、rate limit、渠道部署和凭据；SP-022 只能消费 SP-021 shared contract。

### 14.5 不进入 v0.36

通用 Agent/会话平台、自动 Tool Calling、Recurring Reminder、外部客户通知、Web UI、OAuth/JWT/RBAC、强多租户、多实例/高可用、语音/图片/文件理解与生产 SLA。

## 15. 风险与验收门禁

最高风险依次为：canonical commit 与 Preview result commit 之间的 crash gap、Inbox/Reminder Saga 重放、跨 workspace reference、stale revision、Provider 输出注入。实现必须以 ACC-021 矩阵和故障注入证明，而不是以演示文案证明。

Planning Baseline 只有在独立审查、合并和 Owner 明确签发 Implementation Approval 后才能实施。当前不得开始任何 Phase。

## 16. 相关文档

- `docs/adr/ADR-065-persistent-interaction-view-action-preview.md`
- `docs/adr/ADR-066-deterministic-reference-confirmation-state-machine.md`
- `docs/acceptance/SP-021-conversational-work-interaction.md`
- `docs/project/SP-021-IMPLEMENTATION-TASK.md`
- `docs/rfc/028-daily-review-read-model.md`
- `docs/rfc/029-local-daily-operating-loop.md`
