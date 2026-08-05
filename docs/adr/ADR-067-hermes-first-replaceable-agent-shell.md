# ADR-067：Hermes 作为首个可替换 Agent Shell

- Status: Proposed
- Date: 2026-08-06
- Governance Task: STRAT-001
- Related RFC: RFC-031
- Final Independent Review: Passed / Ready Authorized / Merge Authorized / Not Merged

## 背景（Context）

AI-Lab 已有 API、CLI、CEO Assistant 以及早期 Agent Runtime、Tool、Workflow 和
Coordination 骨架。Hermes 能提供更成熟的通用对话、Agent Loop、Skills、渠道、Browser、
Computer Use 和调度能力。若 AI-Lab 继续复制这些平台能力，会分散对真实业务闭环的投入；
若直接依赖 Hermes 内部实现，又会把 Hermes 变成不可替换核心并破坏业务事实所有权。

## 决策（Decision）

Hermes 被选为第一个首选 Agent Shell，但必须通过中立、版本化的 Adapter Contract 接入。
AI-Lab 的产品架构和领域模型不得要求 Hermes 才能运行；其他 Shell 应能通过相同 contract
实现同等业务交互。

强制约束如下：

- Hermes 不得直接访问 AI-Lab 数据库；
- AI-Lab 不得 import、链接或依赖 Hermes 内部模块、私有协议和存储布局；
- Hermes Memory 不是业务事实源；
- Hermes Conversation 不是审批事实源；
- Hermes Tool Response 不是最终成功证明；
- Shell 只呈现或转交 AI-Lab 生成的 Preview、Confirmation、Approval 和结果状态；
- Adapter transport 可以评估 HTTP/API 或 MCP，但 transport 不改变所有权边界；
- 必须以 contract tests 证明至少能用非 Hermes fake adapter 完成交互协议。

通用 Agent、渠道、Skills、Browser、Computer Use 与通用 Cron 优先由 Agent Shell 提供。
AI-Lab 保留业务 Reminder/Scheduler，因为其到期事实、业务状态、幂等、审计和恢复属于业务
核心，而不是通用唤醒设施。

“优先由 Agent Shell 提供”不是永久执行者限制。实际执行可以由 Agent Shell、AI-Lab 的
正式外部系统 Adapter，或其他受控 Execution Adapter 承担；AI-Lab 始终掌握业务
Policy、Preview、Confirmation、Approval、Audit、Status、Verified Result 与 Recovery。

## 结果（Consequences）

正面结果：

- 可以更快复用成熟交互生态，把研发集中到可信业务闭环；
- Shell 可升级或替换，不迁移 AI-Lab canonical business facts；
- 渠道故障或会话丢失不改变审批、执行与恢复事实；
- MCP 保持为可选 transport，而不是新的产品核心。

代价与风险：

- 需要维护明确的 Adapter version 与 compatibility tests；
- Shell 能力与 AI-Lab 业务能力必须分别发布和诊断；
- 身份映射、timeout、重试和 streaming/final result 区分需要 ARCH-001 明确定义；
- 在 Adapter 完成前，现有入口需要继续保留。

## 被否决的方案（Rejected Alternatives）

### 将 Hermes 作为 AI-Lab 内部运行时

否决。它会造成实现强绑定，使 Shell 升级直接影响业务核心，并诱导数据库直连。

### AI-Lab 继续自建完整通用 Agent 平台

否决作为默认路线。已有代码可以保留，但通用扩张冻结；真实业务需求可在独立审查后复用
局部组件。

### 只允许 MCP

否决。MCP 可以作为 Adapter transport 候选，但不应成为唯一协议或绕过可信交互语义。

## 状态与授权（Status and Authorization）

本 ADR 在 STRAT-001 Draft PR 中为 Proposed。它不授权接入 Hermes、企业微信或实现
Interaction，也不授权启动 ARCH-001、SP-021、INT-001、PILOT-001 或 REL-036。
