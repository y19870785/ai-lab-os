# PILOT-001 Phase 0 Hermes / 企业微信发现证据

## 1. 结论

PILOT-001-P0R 已在授权的 Preview-only 范围内完成真实环境发现。真实 Owner 企业微信私聊可以经
Hermes normal Agent、local stdio MCP、Pilot binding/policy authority 到达 AI-Lab，并创建 canonical
Interaction、Preview 与 AuditEvidence；全过程没有创建 UserTask，也没有执行 Confirm、Execute、Verify
或 Recover。

Fresh Owner Ingress Evidence 的最终结论为：

```text
FRESH_OWNER_INGRESS_EVIDENCE:
UNSUPPORTED

PHASE_0:
STOPPED_PENDING_INGRESS_BRIDGE_DESIGN
```

原因不是 WeCom 或 MCP 不兼容，而是 Vanilla Hermes 最终只把模型构造的 tool arguments 传给 AI-Lab。
真实 channel event metadata 没有通过模型不可伪造的旁路到达 AI-Lab。该结论禁止被 Preview 成功、
static Owner binding 或 `transport=mcp-stdio` 所升级解释。

## 2. P0-E 最终复验

| 检查项 | 结果 |
|---|---|
| Hermes Gateway | `active` |
| WeCom Owner DM | `AVAILABLE` |
| Allowed Owner Count | `1` |
| Owner Identity Match | `PASS` |
| WeCom DM Policy | `allowlist` |
| WeCom Group Policy | `disabled` |
| Raw MCP Tools | `7 EXACT` |
| Hermes 可见 AI-Lab Tools | `preview / status / view`，`3 EXACT` |
| Resources / Prompts | `DISABLED / DISABLED` |
| Parallel Tool Calls | `DISABLED` |
| AI-Lab Provider | `mock` |
| AI-Lab Real Provider Called | `NO` |
| Repository-side P0-E Change | `NONE` |

Owner raw WeCom ID、WeCom Secret、Hermes Provider Secret 与任何 Authorization header 均未写入 Git、
本文、测试 fixture 或控制台证据。

## 3. P0-R 实施边界

独立 Pilot composition 显式注入 `Pilot001OwnerBindingResolver` 与
`Pilot001OperationPolicyResolver`。通用 MCP composition 继续使用 disabled binding/policy authority，
默认 fail closed。

Binding 分类固定为 `PILOT_GRADE_LOCAL_SINGLE_OWNER_BINDING`，只证明当前 assertion 与本机预配置的
单 Owner binding 匹配，明确属于 `NOT_PRODUCTION_IDENTITY_AUTHENTICATION`。`binding_evidence_id` 是
AI-Lab 生成的 deterministic digest，不包含 raw Owner ID。

唯一 operation/policy 为：

```text
canonical_operation: user_task.create
policy_reference: pilot-001/user-task-create/v1
risk_level: medium
requires_confirmation: true
requires_approval: false
canonical_commit_required: true
expected_external_effects: ()
preview_ttl_seconds: 900
source: wecom_owner_pilot
```

Execution、Verification、Canonical Commit 与 Approval authority 继续 Disabled；Coordinator 为
Disabled / Unbound。未修改 core Interaction contract、UserTask runtime 或 DB schema。

## 4. 真实 Message A

2026-08-12，由 allowlist 中唯一 Owner 发送一条新的真实企业微信 DM：

```text
PILOT-001 Phase 0：请只生成任务预览，不要确认或执行。
明天下午 3 点跟进测试客户的 5000 盒护发精油报价。
```

脱敏链路证据：

```text
Real Owner WeCom DM
→ Hermes Gateway
→ normal Agent
→ ai_lab_interaction_preview
→ local stdio MCP
→ Pilot001OwnerBindingResolver
→ Pilot001OperationPolicyResolver
→ TrustedInteractionAdapter
→ InteractionService
→ canonical Interaction
→ canonical Preview
→ AuditEvidence
```

Hermes session 记录到 1 条匹配的真实 Owner message，并调用 Preview tool。模型在构造完整参数期间有多次
fail-closed 尝试；最终只有 1 个 canonical Interaction 被创建。失败尝试没有创建 UserTask，也没有绕过
binding/policy authority。

## 5. Preview 证据

| 字段 | canonical 值 / 结果 |
|---|---|
| operation | `user_task.create` |
| lifecycle | `AWAITING_CONFIRMATION`（包含 `PREVIEWED` audit transition） |
| Preview status | `ACTIVE` |
| title | `明天下午3点跟进测试客户的5000盒护发精油报价` |
| description | `跟进测试客户的5000盒护发精油报价` |
| priority | `medium` |
| canonical normalized due_at | `2026-08-13T07:00:00+00:00` |
| timezone | `Asia/Shanghai` |
| Owner-facing local presentation | `2026-08-13 15:00:00 Asia/Shanghai` |
| source | `wecom_owner_pilot` |
| risk | `medium` |
| requires_confirmation | `true` |
| requires_approval | `false` |
| canonical_commit_required | `true` |
| expected_external_effects | `()` |
| execution_status | `NOT_STARTED` |
| status / view read-back | `PASS / PASS` |

对应 audit 顺序为 `interaction.requested`、`interaction.resolution_started`、`interaction.resolved`、
`interaction.previewed`、`interaction.awaiting_confirmation`。MCP success 只表示 Preview 创建成功，绝不表示
UserTask success。

## 6. 零业务副作用

| 计数 | 值 |
|---|---:|
| UserTask Before | 3 |
| UserTask After Message A | 3 |
| UserTask After No-New-Event Replay | 3 |
| UserTask Created | 0 |
| Target Business Mutation | 0 |
| Message A canonical Interaction Created | 1 |
| Controlled Replay additional Interaction Created | 1 |

第二个 Interaction 是任务书明确授权的 Preview/Audit/idempotency 发现证据，不是业务对象。

## 7. Fresh Owner Evidence 字段与来源矩阵

| 字段 / 边界 | 原始生成者 | 到达 Agent 的方式 | 到达 AI-Lab 的有效方式 | 模型能否重填 | 分类 | AI-Lab 能否辨别真伪 |
|---|---|---|---|---|---|---|
| sender / user identity | WeCom event；adapter 从 `body.from.userid` 读取 | `SessionSource`、session context | 仅模型填写的 `ShellAssertion.channel_identity`，另与本地 static binding 比较 | 能 | `CHANNEL_ORIGINATED → MODEL_CONTROLLED` | 不能判断本次调用是否对应新事件 |
| WeCom message/event id | WeCom payload；缺失时 adapter 可 fallback 生成 | `MessageEvent.message_id`、transcript/session context | 仅模型填写的 `ShellAssertion.message_id/correlation` | 能 | `CHANNEL_ORIGINATED → MODEL_CONTROLLED` | 不能 |
| receive timestamp | WeCom adapter 在接收边界生成 UTC 时间 | `MessageEvent.timestamp`、transcript | 无模型外旁路；MCP contract 不注入 | 能省略或另填 correlation | `CHANNEL_ORIGINATED / NOT_PROPAGATED_AUTHORITATIVELY` | 不能 |
| conversation / chat id | WeCom payload，DM 时可由 sender identity 派生 | `SessionSource.chat_id`、session key/contextvars | 无模型外旁路 | 能在 tool args 中构造其他相关值 | `CHANNEL_ORIGINATED / NOT_PROPAGATED_AUTHORITATIVELY` | 不能 |
| channel identity | WeCom adapter 与 allowlist boundary | session context | `ShellAssertion.channel_identity` 是 tool argument | 能 | `MODEL_CONTROLLED`（在 AI-Lab boundary） | 只能验证 static equality，不能验证 freshness |
| Hermes gateway inbound boundary | Hermes adapter/gateway | `MessageEvent` | 不进入 MCP envelope | 不适用 | `SHELL_ORIGINATED` | 不可见 |
| Agent invocation boundary | Hermes runner | context prompt/contextvars | 不进入 MCP envelope | 模型可见其中一部分 | `SHELL_ORIGINATED` | 不可见 |
| LLM context boundary | Hermes runner | user text + session context | 模型据此构造 JSON | 能读取并重新表达 | `MODEL_CONTROLLED` | 不能 |
| tool-call construction boundary | LLM | JSON arguments | 原样进入 MCP client | 能 | `MODEL_CONTROLLED` | 不能 |
| MCP client invocation boundary | Hermes MCP handler | `call_tool(tool_name, arguments=args)` | 原样 arguments；没有 provenance injection | 上游已由模型控制 | `MODEL_CONTROLLED` | 不能 |
| AI-Lab MCP server boundary | local stdio MCP | tool arguments + AI-Lab 本地 static config | canonical binding/policy resolution | tool arguments 可伪造；本地 config 不可由模型改写 | `MODEL_CONTROLLED + SHELL_LOCAL_STATIC` | 只能验证 static binding，不具备 fresh-event 判别力 |

Hermes 的 session context 使用 contextvars 保存 platform、chat、user 与 message 信息，但 MCP handler 对正常
tool invocation 仍直接调用 `session.call_tool(tool_name, arguments=args)`。其中复制 context 的逻辑只服务于
MCP elicitation callback，不会把入站 provenance 注入普通 tool arguments。

## 8. 无新事件重放（No-New-Event Replay）

在没有发送第二条企业微信消息的情况下，受控本地 protocol test 从 Git-ignored Pilot config 内部读取 identity，
构造相同业务参数与新的 benign idempotency key，再次调用 `ai_lab_interaction_preview`。测试没有打印 raw
Owner ID，没有调用 confirm/execute，结果为：

```text
NO_NEW_WECOM_EVENT=YES
CONTROLLED_MCP_REPLAY=ACCEPTED
ADDITIONAL_CANONICAL_PREVIEW=CREATED
USER_TASK_CREATED=0
```

因此模型可以复现形成有效 Preview 所需的全部 AI-Lab 输入。AI-Lab 没有 channel-originated、
model-independent、non-forgeable 的 fresh-event evidence，无法判断第二次调用并非新的 WeCom inbound。

## 9. 最终停止状态

```text
P0_E_ENVIRONMENT_READY
P0_R_IMPLEMENTATION_AUTHORIZED
P0_R_DRAFT_PENDING_INDEPENDENT_REVIEW
FRESH_OWNER_INGRESS_EVIDENCE_UNSUPPORTED
STOPPED_PENDING_INGRESS_BRIDGE_DESIGN
PHASE_1_NOT_AUTHORIZED
PHASE_2_NOT_AUTHORIZED
IMPLEMENTATION_NOT_APPROVED_BEYOND_AUTHORIZED_PHASE_0_SCOPE
REAL_BUSINESS_MUTATION_NOT_AUTHORIZED
```

本 PR 不设计或实现 ingress bridge，不修改 Hermes source，不增加 Hook、Plugin、Slash Command 或 gateway
patch，不暴露 confirm/recover，不启动 QUALITY-003、REL-036 或 v0.36.0。
