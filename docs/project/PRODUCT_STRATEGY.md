# AI-Lab OS 产品战略

- 战略任务：STRAT-001
- 状态：APPROVED / MERGED / MAIN QUALITY GATE PASSED / POST-MERGE RECONCILED / ARCHIVED
- 原始审计基线：`5f91d9da224daa9fbb2e68f7a3ba685411e93904`
- 最新验证 main 基线：`e4599632e38483780ef422c731a77bc01e85576c`（已包含 QUALITY-002）
- 日期：2026-08-06

## 正式产品定位

AI-Lab OS 是面向个人经营者和企业真实工作流的可信业务操作系统。AI-Lab 长期保存
业务事实、状态、规则、决策和执行证据，并通过可替换的 Agent Shell 与用户自然交互。
通用对话、渠道、Agent Loop 和通用工具优先复用成熟系统；业务数据、业务规则、确认、
审计和恢复必须由 AI-Lab 掌握。

Hermes 是第一个首选但可替换的 Agent Shell，不是 AI-Lab 的业务事实源、审批事实源、
最终成功证明或不可替换核心。

## 产品使命与目标用户

AI-Lab 要解决的不是“再造一个通用聊天 Agent”，而是让真实经营工作具备可持续的事实、
可解释的状态、受控的行动和可恢复的结果。核心用户包括：

- 需要统一管理任务、跟进、报价、知识和经营事实的个人经营者；
- 需要在企业微信等日常入口中调用可信业务能力的小型企业 Owner 与团队；
- 需要把 Agent 建议与实际业务写入、审批和执行证据分开的组织。

长期目标是让用户可以自然地提出工作意图，同时仍能回答：依据是什么、改变了什么、
谁确认了什么、外部系统是否真的成功、失败后如何恢复。

## 长期不变原则

1. Hermes Memory 不是业务事实源。
2. Hermes Conversation 不是审批事实源。
3. Hermes Tool Response 不是最终成功证明。
4. AI-Lab 是业务对象、状态、规则、确认、审计和执行结果的权威。
5. Hermes 不得直接访问 AI-Lab 数据库。
6. AI-Lab 不得 import 或依赖 Hermes 内部实现。
7. Agent Shell 必须可替换。
8. 业务功能优先于通用平台抽象。
9. 高风险动作必须经过显式确认或审批。
10. 失败必须可见，状态必须可恢复。

## 产品边界

### AI-Lab 必须掌握

- 业务对象与 canonical ID；
- 业务状态、状态迁移、revision 与 idempotency；
- 业务规则、权限前置条件和风险等级；
- View、Preview、Confirmation、Approval 与 Cancel 的可信语义；
- Audit、Verified Result、FailureInfo、Saga 和 Recovery；
- 业务 Reminder/Scheduler 及其持久化执行事实；
- 报价、客户跟进、企业知识、ERP 映射等领域模型。

### Agent Shell 优先提供

- 通用会话、渠道接入和多轮 Agent Loop；
- 通用 Skills、Browser、Computer Use 和工具发现；
- 通用 Cron、消息投递与渠道格式适配；
- 非权威的会话记忆、偏好提示和交互编排；
- 通用多 Agent 协作能力。

### 冻结扩张

AI-Lab 冻结通用 Agent Runtime、通用 Tool Runtime、通用 Workflow 平台、通用渠道平台
和通用多 Agent 编排的横向扩张。现有实现保留兼容性，不在 STRAT-001 中删除或弃用；
只有被真实业务闭环需要时才激活或收窄。冻结通用 Tool Runtime 不排除 MCP 作为中立
Adapter transport 候选，但 MCP 不能绕过 Trusted Interaction Boundary。

实际执行可以由 Agent Shell、AI-Lab 的正式外部系统 Adapter，或其他受控 Execution
Adapter 承担。无论执行者是谁，AI-Lab 始终掌握业务 Policy、Preview、Confirmation、
Approval、Audit、Status、Verified Result 与 Recovery。通用 Browser / Computer Use
能力优先复用成熟系统，不等于永久规定所有外部动作只能由 Agent Shell 执行。

## 产品事实与实现事实

v0.35.0 已证明 Composition Root、FailureInfo、DatabaseManager、Workspace、UserTask、
Reminder、Inbox、Waiting-For、Work Log、Agenda、Daily Review、revision、idempotency、
Saga、Action Hints、Review-to-Action、shutdown、restart 与静止 backup/recovery 的基础价值。
其中一部分是可直接复用的真实产品能力，一部分仍是基础设施骨架：

| 类型 | 当前事实 | 战略处理 |
|---|---|---|
| 真实产品能力 | UserTask、业务 Reminder、Inbox、Waiting-For、Work Log、Agenda、Daily Review | 作为业务闭环基座继续使用 |
| 可信基础设施 | Composition Root、FailureInfo、DatabaseManager、Workspace、revision、idempotency、Saga、lifecycle、recovery 等可信机制 | 继续作为 Trusted Business Core |
| 实验或未完成主链路 | Knowledge、Coordination、通用 Tool/MCP、Workflow、通用 Agent Runtime | 保留代码，冻结通用扩张，按业务需求重新激活 |
| 入口能力 | API、CLI、CEO Assistant | 保留兼容；自然交互逐步迁移到中立 Adapter Contract |
| 文档声明 | 早期十一层 Agent/Tool/Workflow/Coordination 平台愿景 | 视为历史技术路径，不再等同于长期产品定位 |

“全部自研”不是长期目标。早期技术层用于验证架构可行性，不能反向要求 AI-Lab 重复建设
已有成熟系统的通用能力。

## 目标架构

```text
企业微信 / Web / 语音 / 桌面
              ↓
可替换 Agent Shell（Hermes 为首选实现）
              ↓
中立 Adapter Contract
              ↓
Trusted Interaction Boundary
View / Preview / Confirm / Cancel / Status / Verified Result
              ↓
AI-Lab Business OS
业务事实 / 状态 / 规则 / 审计 / 恢复
              ↓
ERP / 文件 / NAS / 邮件 / 浏览器 / 数据库
```

Adapter 只能调用公开、版本化、中立的 AI-Lab contract。它不得读取 AI-Lab 数据库、
拼装内部 SQL、伪造 confirmation 或把 Shell 的 tool response 当成业务成功。AI-Lab
通过重新读取 canonical 状态、外部回执或可审计 reconciliation 产生 Verified Result。

## v0.36 至 v0.38 路线

### v0.36 可信自然交互与 Owner Pilot

v0.36 不由一个巨大 SP 承担，治理顺序固定为：

```text
STRAT-001
→ ARCH-001
→ SP-021
→ INT-001
→ PILOT-001
→ REL-036
```

- STRAT-001：冻结产品定位、所有权、路线与治理基线；本 PR 仅完成此项。
- ARCH-001：定义中立 Adapter Contract 与 Trusted Interaction Boundary；已获 Planning 授权，当前 Draft 等待独立审查，未授权实现。
- SP-021：在新架构基线上完整重规划可信对话工作交互；尚未启动。
- INT-001：实现 Hermes Adapter；尚未批准、尚未启动。
- PILOT-001：企业微信 Owner Pilot；尚未批准、尚未启动。
- REL-036：独立发布规划、验收、Tag 与 Release 授权；尚未批准、尚未启动。

PR #62 已 `CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001 /
IMPLEMENTATION_NEVER_AUTHORIZED`。其 View、Preview、Confirmation、CAS、idempotency 与
recovery 设计保留为 ARCH-001 和新 SP-021 的历史输入，但不构成任何启动或实现授权。

### v0.37 报价需求与客户跟进闭环

建立 Quote Request、Customer、Contact、Follow-up、Next Action 和相关审计事实，先完成
需求收集、责任归属、状态推进和人工确认，不提前实现自动价格计算。成功标准是一个真实
客户请求可以从入口进入 AI-Lab，形成可追踪业务对象并闭环到下一行动。

### v0.38 企业知识审核与引用闭环

建立 Knowledge Source、Document Version、Review Status、Citation 与有效期边界。
知识回答必须能够引用已审核来源，并区分草稿、有效、过期和撤回；Shell 的检索上下文不是
企业知识事实。该版本服务报价、培训和运营场景，而不是建设通用 RAG 平台。

## 更远期能力

- v0.39 候选：自动报价计算、报价版本、审批与发送前确认；需要新增产品、配方、规格、
  原料、包装、价格规则和 Quote Version 领域模型。
- v0.40 候选：主动提醒、经营分析和 ERP 集成；通用 Cron 由 Shell 提供，业务到期、
  规则触发和执行状态由 AI-Lab 掌握。
- 更后续：受控工具执行、Computer Use、多 Agent、研发编排与跨业务协作；必须在权限、
  Preview、Approval、Verified Result、Audit 和 Recovery 成熟后逐项启用。

## 治理分级

| 风险等级 | 适用变更 | 最低治理 |
|---|---|---|
| 高风险 | 架构边界、Schema、Migration、数据所有权、高风险执行 | 完整 RFC / ADR / SP / ACC 与独立审查 |
| 普通产品 | 单一业务闭环内的可验收功能 | SP + 自动验收 + 人工验收 |
| 低风险 | 文档、局部修复、无行为变化维护 | 轻量任务单 + CI |
| 技术实验 | 未承诺产品行为的可行性探索 | Spike + 结果报告 |

所有等级都保留 Owner 授权、事实来源一致、高风险动作独立审查、验收不能由实现者自证、
Tag 和 Release 独立授权等底线。

## 本规划的停止条件

- STRAT-001 已合并、通过 main Quality Gate、完成 post-merge reconciliation 并封存。
- 不得据此启动 ARCH-001、SP-021、INT-001、PILOT-001 或 REL-036。
- 若 Adapter 设计要求 Hermes 直连数据库、AI-Lab 依赖 Hermes 内部实现、或 Shell
  会话被当成审批事实，应停止并重新审查架构。
- 若无法定义 Verified Result 和恢复语义，不得启用对应高风险写操作。
