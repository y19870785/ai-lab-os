# AI-Lab 路线图

**最后更新：** 2026-08-09
**当前版本：** v0.35.0 Alpha / GitHub Pre-release Published
**当前 Product SP：** None
**当前 Governance Task：** None
**下一规划治理项：** None

Roadmap 只描述版本范围、里程碑与候选任务。已完成 SP 的 PR、Head、merge commit 和验收状态以根目录 `project_state.json` 为唯一机器可读来源；用户可见版本变化记录在 `CHANGELOG.md` 和版本化 Release Notes。

## 版本与 SP 的关系

- 产品版本由若干 SP 共同组成；SP 编号是开发批次，不等同于产品版本。
- 每个产品版本必须明确功能范围、验收结果、Tag 和 Release Notes。
- 候选 SP 不代表已经批准、排期或启动。

## v0.34.0 Alpha 阶段

目标成熟度：**Alpha / local-first / single-user-oriented**。

### 包含范围

- Canonical UserTask
- Reminder Core 与持久化 Scheduler bridge
- Reminder Inbox 与 Reminder Management
- Natural-language Reminder 的确定性时间子集
- Intent Safety
- Daily Agenda
- Unified Inbox 与 Capture-to-Action
- API、CLI 与 CEO Assistant 共享 canonical Composition Root 和领域服务
- Bearer Token / CORS 本地 API 安全边界
- `project_state.json`、版本、文档职责、Release Notes 与自动一致性检查收口

### 不包含范围

- 外部通知投递
- Recurring Reminder
- Web UI
- 完整 Knowledge 主链路
- 用户身份、OAuth、JWT、RBAC 与强多租户
- 企业级部署、高可用或 production-ready 承诺
- Docker 与长期运行的正式发布验证

### 发布门禁

v0.34.0 Tag 与 GitHub Release 只能在以下条件完成后创建：

1. SP-015 通过审查并合并；（已完成）
2. main Quality Gate 通过；（已完成）
3. post-merge acceptance 完成；（已完成）
4. SP-015A 合并且 main Quality Gate 通过；（已完成）
5. SP-015R 合并且 main Quality Gate 通过；（已完成）
6. Owner 与 ChatGPT 独立授权 Tag 与 GitHub Release。（已完成）

发布授权已完成。授权 Tag 为 `v0.34.0`，授权 Release 类型为 Pre-release；实际 Tag 存在性与目标、Release 发布状态、URL 和时间以 GitHub Tags and GitHub Releases 为准。

## v0.35.0 Alpha 已发布 Pre-release

目标发布名称为 `v0.35.0 Alpha — Local Daily Operating Loop`。SP-016、SP-017、
SP-018、SP-019 与 SP-020 已完成验收并封存；当前没有 Product SP 或下一候选 SP。
REL-035 已完成 Release PR 合并、main Quality Gate、Release Head 冻结、annotated Tag
远端验证和 GitHub Pre-release 发布，并在最终对账后封存。STRAT-001 也已完成合并、
main Quality Gate、post-merge reconciliation 和封存；当前 Product SP 与 Current Governance Task 均为 None：

| 候选 SP | 方向 | 状态 |
|---|---|---|
| SP-016 | Canonical Waiting-For Domain & Agenda Closure | COMPLETED / ARCHIVED |
| SP-017 | 跟进交互与捕获闭环——确定性 Waiting-For 交互、Inbox 捕获确认和持久化 Inbox-to-Waiting-For 转换 | COMPLETED / ARCHIVED |
| SP-018 | Work Log Query Boundary & Context Closure | COMPLETED / POST_MERGE_VERIFIED / RECONCILED / ARCHIVED |
| SP-019 | Daily Review Read Model & Deterministic Follow-up View | APPROVED / MERGED / POST_MERGE_VERIFIED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| SP-020 | Local Daily Operating Loop & Review-to-Action Closure | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / ACC_020_PASSED / INDEPENDENT_EVIDENCE_REVIEW_APPROVED / RECONCILED / ARCHIVED |

ACC-016、ACC-017、ACC-018、ACC-019 与 ACC-020 均为 PASSED / FINAL。SP-020 的 RFC-029 为 Adopted，ADR-063、ADR-064 为 Accepted；Feature PR #57 已 Squash Merge 为 `9ea4b72241bd855319231c09fa6b80c112a14305`，main Quality Gate `30687851816` 为 SUCCESS，SP-020A 对账载体为 PR #58，并完成治理对账与封存。`v0.34.0` 历史发布不变；`v0.35.0` 已发布为 GitHub Pre-release，REL-035 已最终对账并封存。

REL-035 规划冻结无破坏性迁移、缺失 `followups.db` 时增量初始化、Local Daily Profile
显式配置升级，以及 Planning Approval、Implementation Approval、Release PR Merge、Tag
Authorization、GitHub Release Authorization 五个独立治理事件。规划不等于发布日期承诺。

## v0.36 可信自然交互与 Owner Pilot 候选路线

v0.36 不设计为一个巨大 SP。规划和授权顺序固定为：

```text
STRAT-001 → ARCH-001 → SP-021 → INT-001 → PILOT-001 → REL-036
```

| 工作项 | 范围 | 当前状态 |
|---|---|---|
| STRAT-001 | 产品定位、能力所有权、架构与路线基线 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED |
| ARCH-001 | 中立 Adapter Contract 与 Trusted Interaction Boundary | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED |
| SP-021 | Canonical Trusted Interaction Domain | NEXT_CANDIDATE / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION / IMPLEMENTATION_NOT_APPROVED |
| INT-001 | Hermes Adapter | NOT_STARTED / NOT_APPROVED |
| PILOT-001 | 企业微信 Owner Pilot | NOT_STARTED / NOT_APPROVED |
| REL-036 | v0.36 独立发布治理 | NOT_STARTED / NOT_APPROVED |

PR #62 已 `CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001 /
IMPLEMENTATION_NEVER_AUTHORIZED`。其历史设计证据继续保留；ARCH-001 和替代 SP-021
必须分别规划并获得 Owner 授权。ARCH-001 已采纳并封存 architecture contract；SP-021、INT-001、
PILOT-001 与 REL-036 仍未启动。

## v0.37 与 v0.38 候选路线

| 候选版本 | 产品闭环 | 最低领域范围 | 状态 |
|---|---|---|---|
| v0.37 | 报价需求与客户跟进 | Quote Request、Customer、Contact、Follow-up、Next Action、Audit | CANDIDATE / NOT_APPROVED / NOT_SCHEDULED |
| v0.38 | 企业知识审核与引用 | Knowledge Source、Document Version、Review Status、Citation、Expiry | CANDIDATE / NOT_APPROVED / NOT_SCHEDULED |

v0.37 先收集和推进报价需求，不提前实现自动价格计算；v0.38 只建设服务真实业务的审核、
版本和引用闭环，不扩张为通用 RAG 平台。这些版本没有承诺发布日期。

## 更远期候选方向

| 版本方向 | 候选目标 |
|---|---|
| v0.39 | 自动报价计算、报价版本与审批 |
| v0.40 | 主动提醒、经营分析与 ERP 集成 |
| 更后续 | 受控工具执行、Computer Use、多 Agent、研发编排与跨业务协作 |
| v1.0.0 | 满足独立生产就绪标准后的稳定发布 |

这些目标均为 tentative，不构成承诺。通用 Cron、渠道、Skills、Browser、Computer Use
与通用 Agent Loop 优先由可替换 Agent Shell 提供；AI-Lab 保留业务 Reminder/Scheduler
以及业务事实、规则、确认、审计、Verified Result 和 Recovery。实际执行可以由 Agent
Shell、AI-Lab 正式外部系统 Adapter 或其他受控 Execution Adapter 承担，不固定为某一
Shell 实现。

## 已完成基线

- v0.33.0：Composition Root、失败语义、DatabaseManager 所有权与版本治理基线。
- post-v0.33.0 至 v0.34.0 Alpha：UserTask、Reminder、Intent Safety、Daily Agenda、Unified Inbox、Capture-to-Action 与 API/CLI/CEO Assistant 产品闭环。
- ACC-014：A～L PASSED / FINAL。
- SP-015：APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED。
- SP-015A、SP-015R：APPROVED / MERGED / RECONCILED / ARCHIVED。
- SP-016：COMPLETED / MANUAL_ACCEPTANCE_PASSED / ARCHIVED；ACC-016：PASSED / FINAL。
