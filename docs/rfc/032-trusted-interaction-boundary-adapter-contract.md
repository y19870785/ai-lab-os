# RFC-032：可信交互边界与中立 Adapter Contract

- 状态：Adopted
- 治理任务：ARCH-001
- 日期：2026-08-06
- 授权 Base：`7bf12b1f4206608f0c67223546e8400eb9066c8e`
- Adopted by：ARCH-001 / PR #66 / Merge Commit `4f9eab191fc0d99898ee69a2b42912017e4740e3`
- 关联 ADR：ADR-069、ADR-070、ADR-071、ADR-072
- 产品实现：NOT_APPROVED / NOT_STARTED

## 摘要

定义 Shell-neutral、Transport-neutral、版本化的 Trusted Interaction Adapter Contract，使可替换 Agent
Shell 与 AI-Lab Business OS 在不共享数据库、私有模块或业务事实存储的前提下协作。合同覆盖 View、
Preview、Confirm、Cancel、Modify、Status、Verified Result 与 Recovery；AI-Lab 始终拥有 Policy、
Preview、Confirmation、Approval、Audit、Status、Verified Result 与 Recovery。

## 背景与问题

v0.35.0 有可靠的 canonical domains、Workspace scope、revision/CAS、idempotency、Saga、FailureInfo 与
局部恢复，但没有统一 Interaction aggregate。当前 API chat、CEO Assistant、Action Hint、Inbox confirmation、
ToolResult 和 Workflow checkpoint 不能分别等同 trusted request、canonical confirmation、verified success
或 recovery authority。直接接入 Hermes 会固化这些语义缺口。

## 目标

- 使 Hermes 成为首个首选但可替换的 Shell，并允许 Fake/Reference Adapter 运行相同 contract vectors；
- 保证 HTTP、Python API、MCP 或其他 transport 只改变 serialization，不改变 domain ownership；
- 以 canonical ID、Workspace、actor、revision、idempotency、correlation、FailureInfo 与 audit 串联交互；
- 明确 Preview 零业务副作用、Confirmation 权威绑定、执行状态、验证证据和恢复语义；
- 为 SP-021、INT-001、PILOT-001 和 REL-036 提供分离的规划输入。

## 非目标

不创建 Python model、Schema、Migration、endpoint、adapter、MCP 连接、企业微信集成、worker、scheduler job
或 contract test；不删除现有 Agent/Tool/Workflow/Coordination；不启动任何后续任务。

## 架构决定

```text
Channel
  -> Replaceable Agent Shell
  -> Transport Projection
  -> trusted-interaction/v1 Adapter Contract
  -> Trusted Interaction Application Boundary
  -> Canonical Domain Services / Repositories / AI-Lab Database
  -> Controlled Execution Adapter / External System
```

Shell 和外部 Adapter 不得直接访问 AI-Lab 数据库。AI-Lab 不 import Shell 私有实现。MCP 只可作为
transport 候选。任何 transport 的 success response 都不能覆盖 canonical Interaction status。

## 合同信封

请求必须包含 contract version、operation、request/trace/correlation IDs、可选 Interaction ID、channel/
shell/adapter/transport 标识、identity 与 Workspace assertions、expected revision、idempotency key 和 normalized
operation payload。AI-Lab 返回 authoritative/provisional 标记、canonical IDs、revision、status、FailureInfo
reference、audit reference 和 allowed next actions。

assertion 在 AI-Lab 解析前不是权威事实。相同 idempotency key 不同 normalized payload、Workspace、actor、
operation 或 target revision 必须以 conflict 失败。

## 操作语义

| 操作 | 允许的副作用 | 权威结果 | 核心门禁 |
|---|---|---|---|
| View | 无业务写 | canonical view + provenance | resolved actor/workspace + read policy |
| Preview | 仅 Preview/audit 写入；业务零副作用 | Preview ID/revision/expiry/risk/policy | target revision 与 policy 可解释 |
| Confirm | 仅 Confirmation/audit 写入 | Confirmation ID + status | actor/workspace/token/preview revision/expiry/risk/CAS |
| Cancel | Interaction transition；按阶段决定是否需恢复 | authoritative status | expected revision、execution race、policy |
| Modify | 旧 Preview 作废并创建新 Preview | new Preview | 重新解析、policy 与 risk；旧 confirmation 不继承 |
| Status | 无业务写 | authoritative status/sub-status | caller view permission |
| Verified Result | verification/canonical commit 事实 | AI-Lab verified result | operation-specific evidence 与 commit policy |
| Recovery | 受控重查、补偿、commit 或人工决议 | recovery evidence/status | RECOVERY_REQUIRED、owner claim、CAS |

## Interaction 与成功语义

Interaction lifecycle 与 resolution/execution/verification/recovery 子状态分离。`SUCCEEDED` 只能在 operation
要求的 Verified Result 与 canonical commit 均完成后进入。Tool invocation accepted、external attempt、external
acknowledgement、HTTP 2xx 和 ToolResult success 均不是最终成功。结果不确定时保持 UNCERTAIN / VERIFYING
或 RECOVERY_REQUIRED，禁止盲重试。

## Preview、Confirmation 与 Approval

Preview 是 Workspace-bound、actor-bound、policy-bound、revisioned、expirable、auditable 的 canonical fact，
并记录 normalized parameters、target revision、external effects、risk 与 required approvers。Confirmation token
为单用途、限域、可安全持久化验证的 capability reference，绑定 Preview ID/revision、Interaction、Workspace、
actor constraints、risk 和 expiry。

自然语言“确认”仅是 Shell observation；只有 AI-Lab 完成身份、Workspace、Preview、token、revision、expiry、
risk 与 Policy 匹配后才形成 Confirmation。Acknowledgement、Confirmation、Approval、Authorization 与
Execution Permission 不可互换。

## 身份与 Workspace

Channel identity、Shell identity/session 和 external principal 都是不同主体。AI-Lab 通过已验证、可撤销且可
审计的 binding 解析 AI-Lab User、Tenant、Owner、WorkspaceKey、Operator 与 Approver。Conversation 不等于
Workspace，Shell Session 不等于 AI-Lab Session。缺失、冲突、不可信或跨 Workspace 映射均 fail closed；
不得通过自然语言或 Shell memory 猜测 Workspace、Owner 或 Approver。

## 可靠性

Channel、Shell、transport、API、domain command、Execution Adapter、external system、verification 和 recovery
各自拥有独立 retry 语义。timeout-before-acceptance 可以用同 key 重试；timeout-after-possible-side-effect 先查
Status/verify，不得重放。duplicate/out-of-order 事件必须通过 idempotency 与 revision/CAS 判定。restart 后从
durable Interaction/Execution/Recovery evidence 恢复，不以 conversation 或进程内 checkpoint 恢复业务事实。

## FailureInfo 与审计

复用现有 FailureInfo，不创建平行 error model。domain-safe failure 与 internal diagnostic 分离；transport 和
channel 只能投影并脱敏，不能把失败改写为成功。Adapter/transport/authentication/authorization/identity/
workspace/policy/stale/expired/conflict/external/verification/uncertain/commit/recovery failure 均保留 trace correlation
与用户 next action。

canonical Audit Envelope 至少关联 Request、Trace、Interaction、Workspace、Tenant/Owner、Actor/Approver、
Channel/Shell/Adapter/Transport、Operation/Risk、Preview/Confirmation/Execution、Canonical Object、External
Reference、Idempotency、Policy、Transition、Verified Result、Recovery、timestamps 与 FailureInfo。日志不是
canonical audit，secret/token/raw external response 不进入用户展示或未脱敏证据。

## Contract Test 策略

后续以固定 Clock、Fake identity/policy/executor 验证八个操作及 zero-side-effect、CAS、expiry、duplicate、
out-of-order、timeout、uncertain outcome、restart、response loss 和 recovery。相同 vectors 必须适用于非 Hermes
Fake Adapter 与 Hermes Adapter；transport-specific tests 只验证 projection。ARCH-001 不实现这些测试。

## 被拒绝的方案

- Hermes 直连数据库、Hermes memory 作为业务状态、conversation text 作为 approval；
- Tool response 或 HTTP 2xx 作为 canonical success；
- MCP 作为产品核心或 transport-specific domain contract；
- 自然语言推断 Workspace、Shell 生成未验证 Confirmation、timeout 后盲重试；
- 用一个巨大 SP 同时实现 domain、adapter、channel、pilot 与 release；
- 立即删除现有通用 runtimes，或重新打开、合并、cherry-pick PR #62。

## 风险与缓解

- 过度平台化：SP-021 必须以真实业务 operation allowlist 驱动；
- domain/Interaction 双状态：每个 operation 定义 commit point、verifier 与 recovery owner；
- 身份能力未完成：PILOT 前 fail closed，不用 header/text 伪装强身份；
- 外部系统不可幂等：限制为单次执行、显式审批与 uncertain recovery；
- 敏感 audit：最小化、redaction、digest/reference，限制访问。

## 后续门禁

SP-021 只规划 canonical Interaction Domain；INT-001 只规划/实现 Shell Adapter；PILOT-001 只做企业微信
Owner Pilot；REL-036 独立收集 release evidence。四项均 `NOT_STARTED`，需要单独 Owner 授权。

本 RFC 已由 ARCH-001 / PR #66 合并采纳。Adopted 只确认架构合同；SP-021、INT-001、
PILOT-001、REL-036 与任何产品实现仍需单独授权。
