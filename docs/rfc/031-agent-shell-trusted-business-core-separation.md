# RFC-031：Agent Shell 与可信业务核心分离

- 状态：Proposed
- 治理任务：STRAT-001
- 日期：2026-08-06
- Original audit base：`5f91d9da224daa9fbb2e68f7a3ba685411e93904`
- Latest validated main base：`e4599632e38483780ef422c731a77bc01e85576c`（已包含 QUALITY-002）
- 规划分支：`docs/strat-001-product-strategy-realignment`
- 独立审查：FINAL REVIEW PASSED / READY AUTHORIZED / MERGE AUTHORIZED / NOT MERGED
- 产品实施：NOT_APPROVED / NOT_STARTED

## 摘要

AI-Lab 将从“包含通用 Agent 平台能力的本地 AI Operating System”校准为可信业务
操作系统。通用自然交互由可替换 Agent Shell 提供，业务对象、状态、规则、确认、审批、
审计、Verified Result 和 Recovery 由 AI-Lab Business OS 提供。两者只通过中立、
版本化的 Adapter Contract 相连。

## 动机

v0.35.0 已形成可靠的本地业务事实和运行基础，但早期 Agent Runtime、Memory、Tool、
Workflow、MCP 和 Coordination 层与 Hermes/OpenClaw 等成熟系统存在明显重合。继续横向
扩张会把资源投入通用平台竞争，同时弱化 AI-Lab 在真实业务规则、证据和恢复方面的独立
价值。

分离后，AI-Lab 可以复用成熟 Shell 的渠道、Agent Loop、Skills、Browser 和 Computer
Use，同时保持业务事实权威和高风险动作控制。

## 目标

- Agent Shell 可替换，Hermes 只是第一个首选实现；
- AI-Lab 不依赖任何 Shell 内部实现；
- Shell 无法绕过 Preview、Confirmation、Approval、Audit 和 Verified Result；
- 会话中断、Shell 重启或 Adapter 重试不会丢失业务状态或重复执行；
- 已有 API、CLI 和领域服务保持兼容，迁移由后续任务单独规划。

## 非目标

- 本 RFC 不实现 Adapter、Interaction 或企业微信；
- 不修改 Schema、Migration、运行时或产品代码；
- 不删除、弃用或迁移现有模块；
- 不选择 MCP 为唯一 transport；
- 不启动 ARCH-001、SP-021、INT-001、PILOT-001 或 REL-036。

## 架构边界

```text
User Channel
  → Replaceable Agent Shell
  → Neutral Adapter Contract
  → Trusted Interaction Boundary
  → AI-Lab Business OS
  → External Systems
```

### Agent Shell 职责

- 维护通用 conversation/session；
- 运行 Agent Loop、Skills 和通用工具；
- 连接企业微信、Web、语音和桌面等渠道；
- 展示 AI-Lab 返回的 View、Preview、Confirmation、Status 和 Verified Result；
- 在 contract 允许范围内传递用户身份、workspace 和 correlation context。

### AI-Lab 职责

- 校验身份上下文、workspace、revision、idempotency 和业务规则；
- 生成零副作用 Preview 和持久化 Confirmation/Approval；
- 执行或委托业务动作，记录 canonical status 与 audit；
- 用内部状态、外部回执或 reconciliation 形成 Verified Result；
- 显式暴露失败，提供可恢复状态。

实际执行可以由 Agent Shell、AI-Lab 的正式外部系统 Adapter，或其他受控 Execution
Adapter 承担。该选择属于后续架构与集成设计，不改变 AI-Lab 对业务 Policy、Preview、
Confirmation、Approval、Audit、Status、Verified Result 与 Recovery 的权威。

## 不可违反的约束

```text
Hermes Memory != Business Fact Source
Hermes Conversation != Approval Fact Source
Hermes Tool Response != Final Success Proof
```

- Hermes 不得直接访问 AI-Lab 数据库；
- AI-Lab 不得 import、链接或依赖 Hermes 内部实现；
- Adapter 不得生成或修改 canonical business ID；
- Shell 不得将自然语言“确认”直接转换成未绑定 Preview 的写入；
- Tool success 只能作为待验证 evidence，不能直接成为 Verified Result；
- MCP 可以是 transport 候选，但不得改变上述所有权。

## 中立 Adapter Contract 的最低要求

ARCH-001 应进一步定义并验收：

- 版本协商与 capability discovery；
- 结构化 identity、workspace、session、correlation 和 causation；
- View / Preview / Confirm / Cancel / Status / Verified Result 操作；
- Preview ID、revision、expiry、risk level 和 required approvals；
- idempotency key、重试、timeout 和重复消息语义；
- FailureInfo 到渠道展示的稳定映射；
- streaming 与最终 canonical result 的区分；
- audit reference 和 recovery guidance；
- Shell 替换 contract tests；
- transport independence，包括 HTTP/API 与 MCP 候选。

## Interaction 状态原则

Preview 必须零业务副作用，并绑定明确业务动作、参数、当前 revision、风险等级与有效期。
Confirmation 必须引用同一个有效 Preview。高风险动作还必须满足独立 Approval。执行过程
可能异步，但必须可查询 Status；只有 AI-Lab 生成的 Verified Result 才能结束成功状态。

## 兼容与迁移原则

- 现有 API、CLI、CEO Assistant 和领域服务不在 STRAT-001 中改变；
- 后续 Adapter 应优先委托 canonical application services，不复制领域规则；
- 现有通用 Agent/Tool/Workflow/Coordination 代码先冻结，不立即删除；
- 所有删除或弃用必须有独立依赖审计、兼容方案和 Owner 授权；
- 业务 Reminder/Scheduler 保留，通用 Cron 和渠道投递由 Shell 优先提供。

## 风险

- Adapter 过早绑定 Hermes 私有协议，造成名义可替换、实际不可替换；
- 双方同时持久化业务状态，形成 split-brain；
- 把 transport acknowledgement 误写成业务成功；
- 在没有稳定 identity/approval 模型前开放高风险执行；
- 为追求统一而把已有领域能力重新抽象成通用平台。

## 决策与后续门禁

RFC-031 在 STRAT-001 合并前保持 Proposed。合并后是否 Adopted 由独立审查和 Owner 授权
决定。后续顺序固定为：

```text
STRAT-001 → ARCH-001 → SP-021 → INT-001 → PILOT-001 → REL-036
```

PR #62 继续保持 Open、Draft 和冻结；不得据此启动 SP-021 Implementation。
