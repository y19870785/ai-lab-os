# ADR-070：Preview 与 Confirmation 作为 AI-Lab Canonical Facts

- Status: Proposed
- Date: 2026-08-06
- Governance Task: ARCH-001
- Related RFC: RFC-032
- Implementation: NOT_APPROVED / NOT_STARTED

## 背景（Context）

现有 Action Hint 的 `requires_confirmation` 是确定性展示元数据，Inbox/Waiting-For 的“确认”是局部业务
流程；Shell conversation 和自然语言短语都缺少 actor、Workspace、Preview revision、expiry、risk 与 Policy
绑定，不能作为通用审批事实。

## 决策（Decision）

Preview 与 Confirmation 由 AI-Lab 创建、持久化并审计。Preview 必须零业务副作用，拥有 canonical ID、
Workspace/actor/policy binding、target revision、normalized parameters、external-effect summary、risk、required
approvals、expiry 和自身 revision。

Confirmation 必须引用有效 Preview ID/revision 和限域 confirmation token，并匹配 authoritative actor、
Workspace、risk、expiry、Policy 与 expected Interaction revision。Modify 改变目标、参数、副作用、risk、Policy
或 revision 时必须重新 Preview，旧 Confirmation/Approval 失效。

Acknowledgement、Confirmation、Approval、Authorization 与 Execution Permission 是不同事实。自然语言“好的”
只能作为输入意图，不能由 Shell 直接升级为 canonical Confirmation。

## 后果（Consequences）

正面结果：确认可以跨请求、重启、渠道与 Shell 恢复，同时保持主体与计划一致；高风险 Approval 有明确证据。

代价与风险：后续需要 token 安全、expiry、CAS、redaction 和 policy snapshot/reference 设计。ARCH-001 不创建
Schema、token 实现或账户绑定。

## 被拒绝的方案（Rejected Alternatives）

- Conversation text 或 Shell memory 作为 approval evidence：缺少权威绑定与生命周期。
- Shell 自行生成 confirmation：可绕过 AI-Lab Policy 与 stale-preview 检查。
- Modify 后继续复用旧 confirmation：用户同意的动作已改变。

## 状态与授权（Status and Authorization）

本 ADR 在 ARCH-001 Draft Planning PR 中保持 Proposed。SP-021 尚未启动，Implementation 未授权。
