# PILOT-001 — 企业微信 Owner 可信任务捕获规划基线

> 英文识别名：WeCom Owner Trusted Task Capture
> 状态：PLANNING_AUTHORIZED / DESIGN_BASELINE_IN_PROGRESS / IMPLEMENTATION_NOT_AUTHORIZED / REAL_PILOT_NOT_STARTED
> PR 门禁：OPEN / DRAFT / PENDING_INDEPENDENT_REVIEW / NOT_READY / NOT_MERGE_AUTHORIZED
> 唯一规划 Base：`836100b9bb90418203c7237470cb793810b958fa`

## 1. 任务背景

AI-Lab 已经拥有持久化 `UserTask`、`WorkspaceKey`、可信交互（Trusted Interaction）状态机、
Shell-neutral Adapter 与本地 stdio MCP 投影。当前缺少的不是另一套任务系统，而是一条在真实但受控的
入口中证明这些能力能够协同工作的最小链路。

PILOT-001 规划真实 Owner 通过企业微信私聊向 Hermes 表达自然语言工作意图，再由 AI-Lab 完成
权威身份与 Workspace 绑定、Operation Policy 解析、Canonical Preview、明确确认、内部执行、独立
验证、Canonical Commit Evidence、审计和恢复。连接企业微信只是入口条件，不是 Pilot 成功本身。

## 2. Pilot 目标与用户价值

Pilot 只允许一项真实业务 Mutation：

```text
user_task.create
```

它要证明一条真实 Owner 指令能够变成唯一、持久、重启后仍可读取并可验证的 AI-Lab `UserTask`，
同时让 Owner 在写入前看见规范化结果并选择确认、修改或取消。

代表场景：

```text
明天下午 3 点跟进 XX 客户的 5000 盒护发精油报价。
```

其中客户、数量与报价只是 `UserTask` 的业务描述。本 Pilot 不创建 Quote、Customer、Contact 或
Pricing 等新 canonical domain。

## 3. Pilot 范围与安全等级

首选 Agent Shell 为 Hermes，真实 Channel 为 WeCom / 企业微信私聊，Transport 为 local stdio MCP。
运行边界固定为：

```text
SINGLE_OWNER
DM_ONLY
LOCAL_HOST
ALLOWLISTED
TEXT_ONLY
```

身份安全等级固定为：

```text
PILOT_GRADE_LOCAL_SINGLE_OWNER_BINDING
NOT_PRODUCTION_IDENTITY_AUTHENTICATION
```

该等级依赖本地主机安全、专用 Hermes 实例、企业微信私聊、Owner allowlist 与 AI-Lab 固定绑定配置，
不宣称 Production Authentication、Enterprise IAM、RBAC、OAuth 或强多租户认证。

## 4. 用户旅程与系统链路

用户旅程：

1. Owner 在企业微信私聊中输入任务意图；
2. Hermes / LLM 生成临时结构化建议（Provisional Structured Proposal）；
3. AI-Lab 从本地 Pilot 配置解析权威 actor 与 Workspace，并校验 Shell/Channel 一致性；
4. AI-Lab 只允许 `user_task.create`，校验结构化时间并生成 Canonical Preview；
5. Owner 确认、修改或取消准确 Preview；
6. 确认后由 AI-Lab 内部协调器启动执行，而不是由 MCP Shell 调用 execute；
7. `UserTaskService.create()` 持久化唯一 UserTask；
8. 独立 VerificationPort 重新读取业务对象；
9. Canonical Commit Authority 再次确认持久事实并形成证据；
10. 只有证据完整时 Interaction 才进入 `SUCCEEDED`，结果再投影给 Hermes。

```text
WeCom Owner DM
  → Hermes WeCom ingress
  → Hermes Agent / LLM
  → Provisional Structured Proposal
  → local stdio MCP
  → PilotOwnerBindingResolver
  → PilotOperationPolicyResolver
  → TrustedInteractionAdapter
  → InteractionService / Canonical Preview
  → Owner Confirmation
  → PilotInteractionCoordinator
  → InteractionService.start_execution()
  → PilotUserTaskExecutionPort
  → UserTaskService
  → PilotUserTaskVerificationPort
  → PilotUserTaskCanonicalCommitAuthority
  → VerifiedResult + CanonicalCommitEvidence
  → Interaction SUCCEEDED
```

永久语义：

```text
Hermes Tool Response != Business Success
MCP Tool Completion != Business Success
Business Success = SUCCEEDED + VerifiedResult + required CanonicalCommitEvidence
```

## 5. 信任边界、身份与 Workspace

### 5.1 不可信输入

LLM 输出、聊天文本、Hermes Memory、Shell Session ID、Conversation ID、`ShellAssertion`、
`asserted_workspace`、`channel_identity`、用户名文本与 OS Username 都不是权威身份或 Workspace 来源。

### 5.2 权威绑定

规划 `PilotOwnerBindingResolver` 从 AI-Lab 自己的 Pilot Binding Config 读取：

```text
actor_id
tenant_id
workspace_id
namespace
binding_evidence_id
expected_shell
expected_channel
expected_wecom_identity
```

Resolver 生成现有 `ResolvedShellContext`，其中完整 `WorkspaceKey` 与 `actor_id` 只来自该固定配置。
Shell 提供的 `channel`、`shell`、`channel_identity` 仅用于与配置做一致性校验；缺失或不一致时 fail
closed，不猜测、不自动绑定、不回退到 default Workspace。

### 5.3 威胁模型

至少防范：伪造 Owner 文本、LLM 自报 Workspace、错误 Shell/Channel、被转发的群聊消息、跨 Workspace
访问、stale Preview、旧 Confirmation 重放、重复 execute、崩溃后重复创建、日志或测试夹具泄露凭据。
本地主机或专用 Hermes 实例已经被完全攻破不在本 Pilot 的可证明安全范围内，因此不得把 Pilot 等级
外推为生产认证。

## 6. 凭据所有权与数据最小化

企业微信凭据只属于 Hermes / Channel configuration。AI-Lab 不保存 `WECOM_SECRET`、WeCom Bot
Secret、Hermes Provider API Key、Hermes `config.yaml`、Memory DB 或 Session DB。

任何 Credential 不得进入 Git、`project_state.json`、Preview、Interaction correlation、
`AuditEvidence`、`FailureInfo`、日志、测试、fixture 或 snapshot。安全 metadata 仅允许：

```json
{
  "interaction_id": "<interaction-id>",
  "pilot_id": "PILOT-001"
}
```

不得持久化完整原始聊天、完整 Prompt、Provider Response 或 Authorization Header。

## 7. 操作策略（Operation Policy）

`PilotOperationPolicyResolver` 只接受以下固定策略：

```yaml
canonical_operation: user_task.create
risk_level: medium
requires_confirmation: true
requires_approval: false
canonical_commit_required: true
expected_external_effects: []
policy_reference: pilot-001/user-task-create/v1
```

Shell 只可建议 `title`、`description`、`priority`、`due_at` 与 `timezone`。`task_id`、Workspace、actor、
source、risk、policy、confirmation、approval 与 commit 要求全部由 AI-Lab 决定。无策略或非白名单
operation 一律拒绝。

## 8. 自然语言、时间与 Preview

Hermes 可把“明天下午三点”解释成例如 `2026-08-12T15:00:00+08:00`，但该解释只是 Provisional
Proposal。AI-Lab 必须收到带 offset 的结构化时间，验证 IANA timezone 与 instant 一致性，再生成
Canonical Preview。Owner 确认的是 Preview，不是 LLM 猜测。

用户可见 Preview 至少显示：

```text
即将创建任务

标题：跟进 XX 客户的 5000 盒护发精油报价
时间：2026-08-12 15:00
时区：Asia/Shanghai
优先级：Medium
```

Owner 可以确认、修改或取消。Modify 必须创建新 Preview revision 并使旧 Preview、旧 token、旧
Confirmation 和旧 Approval 失效；Confirmation 必须精确绑定 Interaction、Preview ID、Preview
revision、Interaction revision、actor、Workspace、expiry 与 idempotency key。

## 9. MCP / Hermes 永久边界与 Phase 0 兼容门禁

MCP 继续只暴露七项既有工具：

```text
ai_lab_interaction_preview
ai_lab_interaction_modify
ai_lab_interaction_confirm
ai_lab_interaction_cancel
ai_lab_interaction_status
ai_lab_interaction_view
ai_lab_interaction_recover
```

不得新增 approve、execute、run、dispatch、verify、canonical_commit、audit_dump、raw_db、raw_sql、
repository、tool_executor、workflow_runtime 或 agent_runtime tool。Hermes 永远没有直接 Execute、Verify
或 Commit 权限。

Phase 0 必须通过真实进程链 `Real Hermes Process → Hermes MCP Client → AI-Lab stdio MCP Server`
验证 Server Startup、Protocol Negotiation、`tools/list`、Tool Schema、Preview、Status 与 Clean Shutdown。
文档或 SDK major version 推测不能替代真实运行证据。若不兼容，立即 STOP / REPORT，不擅自降级
AI-Lab MCP、改 Hermes 依赖/源码、强制升级或加入非标准 compatibility hack。

## 10. 确定性 UserTask 身份（Deterministic UserTask Identity）

同一 Interaction 永远映射同一 `task_id`。规划算法为：

```text
seed = UTF8("pilot-001:user-task:create:" + interaction_id)
task_id = "ut_" + SHA256(seed).hexdigest()
```

算法版本固定在 `pilot-001/user-task-create/v1` policy 中。ExecutionPort、VerificationPort 与
Canonical Commit Authority 必须独立使用同一算法；不得接受 Shell 提供的 ID，也不得使用随机业务
Task ID。重复请求、进程崩溃或不确定执行结果都只能重新定位同一对象，不能创建第二个 UserTask。

## 11. 执行、验证与 Canonical Commit

### 11.1 执行端口（PilotUserTaskExecutionPort）

ExecutionPort 只依赖 `UserTaskService` 与 Pilot Config，并调用：

```python
await user_task_service.create(
    workspace_key=fixed_workspace,
    task_id=deterministic_task_id,
    title=preview_title,
    description=preview_description,
    priority=preview_priority,
    due_at=preview_due_at,
    timezone=preview_timezone,
    source="wecom_owner_pilot",
    metadata={"interaction_id": interaction_id, "pilot_id": "PILOT-001"},
)
```

它禁止依赖 `SQLiteUserTaskRepository`、`DatabaseManager`、raw SQLite、Hermes Python package、
Hermes Memory、`ToolExecutor`、`WorkflowRuntime` 或 `AgentRuntime`。

### 11.2 内部协调器（PilotInteractionCoordinator）

`Confirm != Shell Execute`。Confirm 使 canonical Interaction 进入 `AUTHORIZED` 后，AI-Lab 内部
协调器调用 `InteractionService.start_execution()`；进入 `VERIFYING` 后再由内部协调器调用
`InteractionService.verify()`。协调器不暴露成 MCP tool。

### 11.3 验证端口（PilotUserTaskVerificationPort）

VerificationPort 不相信 ExecutionPort 返回 success，而是通过 `UserTaskService.get()` 独立 read-back，
至少核对对象存在、deterministic `task_id`、固定 Workspace、Preview 中的 title/due_at/priority、
`source=wecom_owner_pilot` 与 `metadata.interaction_id`。任一不一致都不是 VERIFIED。

VerificationPort 不依赖进程内 dict、临时 callback、ExecutionPort return object 或 Hermes Session。
重启后只凭 `interaction_id`、固定 Workspace 与 deterministic ID 即可重查。

### 11.4 Canonical Commit 权威（PilotUserTaskCanonicalCommitAuthority）

Canonical Commit Authority 不执行写入。它独立读取真实 UserTask，确认持久化事实满足 Preview，才形成
包含 `canonical_object_id`、`canonical_revision`、outcome 与 `evidence_digest` 的
`CanonicalCommitEvidence`。缺少 VerifiedResult 或所需 Commit Evidence 时不得进入 `SUCCEEDED`。

## 12. Composition Root 规划

当前 `create_system()` 在构造 `UserTaskService` 之前构造 `InteractionService`。后续实现首选一个
fail-closed、可延迟绑定的 Pilot Port Bundle：

```text
创建未绑定的 Pilot Port Bundle
  → 作为四个 trusted ports 传入 create_system()
  → SystemContainer 构造完成
  → 将 system.user_task_service 与固定 Pilot Config 绑定到 bundle
  → 校验绑定完成
  → system.start()
```

未绑定、UserTask disabled、配置缺失或重复绑定都必须 fail closed。Planning PR 不修改
`core/interaction/**` 或 `core/system/**`；若独立实现审查认定必须调整 composition root，只能在后续获批
Implementation PR 中做最小变更。

## 13. Recovery 与重启验证

Execution outcome 为 `UNCERTAIN` 时 Interaction 进入 `RECOVERY_REQUIRED`，协调器立即停止。Recovery
只允许重新验证 canonical object，不得再次调用 `UserTaskService.create()`、自动重试 execute 或创建
第二个 UserTask。

重启验收必须证明 UserTask 仍存在、Interaction 仍为 `SUCCEEDED`、结果与证据可重新查询；若崩溃发生
在执行结果落库前，Recovery 仍能凭 deterministic ID 找到同一对象并补全验证，而不是重执行。

## 14. Shell 最终结果投影

现有 `AdapterResponse` 尚未投影真实业务对象结果。后续实现可做 backward-compatible additive change，
仅新增 Optional 字段：

```text
canonical_object_id
canonical_revision
verified_result_id
verified_outcome
```

字段只能来自 canonical Interaction，Shell 不可写；没有 VerifiedResult / Commit Evidence 时不得伪造。
现有 `final` 定义不变：`SUCCEEDED`、`FAILED`、`CANCELLED`、`EXPIRED` 为 true，其余状态为 false；
`final=true` 仍不等于 business success。

## 15. Pilot 分阶段门禁

### Phase 0 — 传输与身份冒烟（Transport / Identity Smoke）

使用真实 WeCom、Hermes、MCP stdio 与 AI-Lab，但 `NO BUSINESS EXECUTION`。验证 allowlist、启动、协议、
工具白名单、Owner Binding、mismatch fail-closed、Preview、Status 与 Clean Shutdown。

### Phase 1 — 真实 Preview-Only 流量（Real Preview Only）

使用真实 Owner、WeCom、Hermes 和业务语言，但 `NO USER TASK WRITE`。ExecutionPort 保持 disabled，人工
核对 title、description、due_at、timezone、priority、Modify 与 Cancel。Phase 1 人工验收完成前，
Phase 2 为 `NOT_AUTHORIZED`。

### Phase 2 — 单一 Canonical Mutation（One Canonical Mutation）

只开放 `user_task.create`，闭环为 Preview → Owner Confirm → Internal Execute → Independent Verify →
Canonical Commit Evidence → SUCCEEDED。不得同时开放 update、cancel task、reminder、waiting-for、inbox、
quote、customer 或 message.send。

每一 Phase 的执行都需要后续独立实现/验收授权；本 Planning PR 不授权任何 Phase 运行。

## 16. 验收与证据原则

正式验收以 `docs/acceptance/PILOT-001-wecom-owner-pilot.md` 为唯一计划。至少覆盖一条真实 Owner 场景、
restart 与重复请求，以及 wrong channel/shell/identity、缺 binding/policy、unsupported operation、stale/
expired Preview、旧 Confirmation、Shell execute/approve 不存在、uncertain/recovery no re-execution 与跨
Workspace 拒绝。

自动化测试通过只能证明合同和实现行为，不等价于真实企业微信 Pilot 通过。真实成功必须同时具备
Automated Evidence、Real Integration Evidence、Manual Owner Evidence、Restart Evidence 与 Negative
Evidence。

## 17. Disable Strategy、Rollback 与 Stop 条件

Disable Strategy：默认不配置 Pilot Binding/Policy，Ports 未绑定即 fail closed；可通过移除本地 allowlist
或关闭 Pilot feature flag 立即禁止 Preview 与 execution，同时保留 canonical audit/status 读取。

Rollback：停止 Hermes MCP 入口并禁用 Port Bundle；不删除 Interaction、UserTask 或证据，不修改数据库
历史，不自动补偿已验证创建的任务。若需要撤销业务对象，由 Owner 使用既有 UserTask lifecycle 明确处理，
不得由 Pilot Recovery 偷偷取消。

立即 STOP / REPORT 的条件包括：MCP 真实兼容失败、identity/Workspace 无权威绑定、existing canonical
contract 存在真实语义缺陷、凭据可能泄露、unexpected business write、duplicate UserTask、verification
不能独立 read-back、uncertain outcome 被重执行，或实现需要新的永久架构决策。

## 18. 禁止范围与已知限制

禁止 Quote/Customer/Contact/Pricing、Reminder Delivery、Recurring Reminder、自动外发、群聊、多用户、
RBAC/OAuth/JWT/IAM、Remote/HTTP/Public MCP、Browser/Computer Use、通用 Tool/Workflow/Agent Runtime 与
Multi-Agent 扩张。AI-Lab 使用 `AI_LAB_PROVIDER_MODE=mock`；允许 Hermes 使用其独立真实 Provider，但
Hermes LLM 输出仍只是 provisional input。QUALITY-003 / QUALITY-004 与 REL-036 保持未授权、未启动。

已知限制：Pilot 安全依赖单机与专用实例；Phase 0 尚未真实验证 Hermes MCP SDK compatibility；真实
WeCom 身份可用字段与 Hermes 配置仍需在验收环境核实；AdapterResponse additive projection 尚未实现；
Pilot Port Bundle 与 Coordinator 尚未实现。

## 19. 后续实现文件范围建议

后续获得独立实现授权后，建议新增：

```text
applications/pilot_owner/binding.py
applications/pilot_owner/policy.py
applications/pilot_owner/ports.py
applications/pilot_owner/coordinator.py
tests/applications/pilot_owner/**
tests/integration/test_pilot_001_*.py
```

可能需要最小调整：

```text
core/system/factory.py
applications/trusted_interaction_adapter/models.py
applications/trusted_interaction_adapter/service.py
applications/trusted_interaction_adapter/mcp_server.py
```

不得直接修改 UserTask repository、Interaction repository、数据库 schema、Hermes 源码或 MCP 依赖版本。
最终文件范围必须由独立实现审查确认。

## 20. RFC / ADR 判断

```text
RFC / ADR Required: NO
```

理由：RFC-031、RFC-032 与 ADR-067～072 已经永久定义 Shell 可替换性、业务事实所有权、版本化 Adapter
Contract、Preview/Confirmation canonical authority、Verified Result 与 identity/Workspace fail-closed。
PILOT-001 只为既有边界增加一个受控 binding、单 operation policy 和 UserTask ports，不改变永久架构。
若后续发现必须改变这些合约，则 STOP / REPORT，不能在 Planning PR 自行分配新编号。

## 21. 授权边界

本文件只完成规划基线。它不授权配置 Hermes、连接企业微信、运行 Phase 0/1/2、实现 Resolver/Ports/
Coordinator、修改 runtime、转 Ready、Merge、启动 REL-036 或创建 v0.36。下一步是对 Draft PR 进行独立
规划审查。
