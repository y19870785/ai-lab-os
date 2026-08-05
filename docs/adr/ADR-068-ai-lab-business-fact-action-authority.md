# ADR-068：AI-Lab 作为业务事实与行动权威

- Status: Proposed
- Date: 2026-08-06
- Governance Task: STRAT-001
- Related RFC: RFC-031

## 背景（Context）

自然语言 Agent 可以保存记忆、保持会话、调用工具并返回成功文本，但这些能力不能证明
业务状态已经合法改变。把 Shell memory、conversation 或 tool response 当成权威会产生
重复写入、伪确认、错误成功、无法审计和无法恢复等风险。

AI-Lab 已有 canonical 业务对象、FailureInfo、revision、idempotency、Saga、Workspace、
Work Log 和本地恢复基础，适合承担业务事实与行动权威。

## 决策（Decision）

AI-Lab 是以下内容的唯一业务权威：

- 业务对象、canonical ID 与状态；
- 业务规则、风险等级和允许的状态迁移；
- View 与零副作用 Preview；
- Confirmation、Approval 与 Cancel 事实；
- execution intent、idempotency、状态和外部关联；
- Audit、FailureInfo、Verified Result 与 Recovery。

Agent Shell 可以理解自然语言、生成候选请求、呈现确认和调用 Adapter，但没有权限自行
创建上述事实。

## 可信行动协议

```text
View
→ Preview(current revision, action, parameters, risk, expiry)
→ Confirm or Cancel
→ Approval when required
→ Execute(idempotency key)
→ Status
→ Verified Result or Visible Failure
→ Recovery / Reconciliation when required
```

Preview 不得产生业务副作用。Confirmation 必须绑定未过期的同一个 Preview；Approval
必须满足风险策略并独立记录。Execute 的传输成功不等于业务成功。Verified Result 只能由
AI-Lab 根据 canonical state、可验证外部回执或 reconciliation 生成。

## 记忆与知识边界

- Hermes Memory 可保存对话连续性和非权威偏好，但不是业务事实源；
- Hermes Conversation 可以承载确认界面，但不是审批事实源；
- 被采纳的业务决策、依据和版本由 AI-Lab 保存，模型隐式推理不进入权威记录；
- 企业知识的 source、version、review status、citation、expiry 与 withdrawal 归 AI-Lab；
- Shell cache、向量片段或生成答案不能替代已审核企业知识。

## 外部系统执行

对 ERP、文件、NAS、邮件、浏览器或数据库的动作，AI-Lab 至少保存：

- 业务意图与目标对象；
- Preview、Confirmation/Approval 和发起身份；
- idempotency/correlation 标识；
- 执行状态、错误和重试状态；
- 外部引用或回执；
- 验证方法、Verified Result 与恢复建议。

Browser 或 Computer Use 可以由 Shell 执行，但 AI-Lab 仍负责动作是否被授权以及结果是否
得到验证。无法验证的响应必须保持 pending、unknown 或 failed，不得报告最终成功。

## 结果（Consequences）

正面结果：

- 更换 Shell 不会丢失业务、审批或审计事实；
- 会话断线和工具重试可以依靠 idempotency 与 status 恢复；
- 高风险动作拥有可审查的授权链；
- 企业知识和经营分析可以建立在稳定来源上。

代价与风险：

- AI-Lab 需要新增明确的 Preview、Confirmation、Approval 与 execution receipt 领域模型；
- 外部系统必须设计验证与 reconciliation，而不能只看 HTTP/tool success；
- 现有部分入口尚未覆盖完整可信行动协议，因此不得提前宣称能力完成。

## 被否决的方案（Rejected Alternatives）

### 以 Agent 对话记录作为审批记录

否决。自然语言可能含糊、被截断、被重写或缺少对具体 Preview 的绑定。

### 以 Tool Response 作为成功证明

否决。传输确认、页面文本或模型总结不等于 canonical external state。

### 让 Hermes 直接读写 AI-Lab SQLite

否决。它绕过领域规则、revision、idempotency、审计和恢复，并使 Shell 不可替换。

## 状态与授权（Status and Authorization）

本 ADR 在 STRAT-001 Draft PR 中为 Proposed。它只建立规划基线，不修改 Schema 或运行时，
不授权实现 Interaction、高风险执行或任何后续任务。
