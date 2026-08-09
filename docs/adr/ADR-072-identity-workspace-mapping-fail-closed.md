# ADR-072：Identity 与 Workspace 映射失败关闭

- Status: Accepted
- Date: 2026-08-06
- Governance Task: ARCH-001
- Related RFC: RFC-032
- Accepted by: ARCH-001 / PR #66 / Merge Commit `4f9eab191fc0d99898ee69a2b42912017e4740e3`
- Implementation: NOT_APPROVED / NOT_STARTED

## 背景（Context）

当前本地 Alpha 通过 Bearer token 和 header/profile 构造 WorkspaceKey，适合既有受控边界，但不能证明
Channel User、Shell Identity、AI-Lab User、Owner、Operator、Approver 与 Workspace 的权威关系。Conversation
与 Shell Session 也不等于 Workspace 或 AI-Lab Session。

## 决策（Decision）

Channel/Shell 提供的 identity、session 与 workspace 值都视为 assertion。AI-Lab 通过已验证、可撤销、可审计
的 binding 权威解析 AI-Lab User、Tenant、Owner、WorkspaceKey 与 role，并在 Interaction boundary 与 canonical
domain service 两层执行权限及 Workspace scope。

缺少映射、验证失败、多个映射冲突、role 不足、跨 Workspace、主体与 Preview/Confirmation 不匹配时均
fail closed 并返回 FailureInfo。不得从自然语言、conversation title、Shell memory 或历史工具参数猜测
Workspace、Owner 或 Approver。

跨渠道或跨 Shell Confirmation 仅在各入口都绑定同一 authoritative actor，且 Policy 允许对应 channel 时成立。
External Principal 与 AI-Lab actor 分开记录。

## 后果（Consequences）

正面结果：Shell 替换和多渠道不会削弱 Workspace 隔离；Confirmation 与 Approval 有明确主体。

代价与风险：后续需要账户 binding、撤销、角色与 recovery 设计；在这些能力完成前可用操作必须收窄并
fail closed。ARCH-001 不实现 OAuth、企业微信身份、多租户 Schema 或账户绑定。

## 被拒绝的方案（Rejected Alternatives）

- 直接信任 workspace header：transport assertion 不是 authority。
- Conversation/Session 自动映射 Workspace：生命周期和所有权不同。
- 用自然语言推断 Owner/Approver：存在跨 Workspace 与冒名风险。

## 状态与授权（Status and Authorization）

本 ADR 已由 ARCH-001 / PR #66 合并接受。PILOT-001 与任何身份实现仍未获授权。
