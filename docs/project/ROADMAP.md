# AI-Lab 路线图

**Last Updated:** 2026-08-02
**Current Version:** v0.35.0 Alpha / Release Candidate / Not Published
**Current SP:** None
**Current Governance Task:** REL-035 / IMPLEMENTATION_APPROVED / IMPLEMENTATION_IN_PROGRESS

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

## v0.35.0 Alpha 发布候选版

目标发布名称为 `v0.35.0 Alpha — Local Daily Operating Loop`。SP-016、SP-017、
SP-018、SP-019 与 SP-020 已完成验收并封存；当前没有 Product SP 或下一候选 SP。
REL-035 Implementation 已获正式授权，源码版本与发布文档已更新为 `0.35.0`，
Release Candidate 已完成本地验证并进入 Draft PR 独立审查；`v0.35.0` Tag 与 GitHub
Pre-release 均未授权、未创建：

| 候选 SP | 方向 | 状态 |
|---|---|---|
| SP-016 | Canonical Waiting-For Domain & Agenda Closure | COMPLETED / ARCHIVED |
| SP-017 | 跟进交互与捕获闭环——确定性 Waiting-For 交互、Inbox 捕获确认和持久化 Inbox-to-Waiting-For 转换 | COMPLETED / ARCHIVED |
| SP-018 | Work Log Query Boundary & Context Closure | COMPLETED / POST_MERGE_VERIFIED / RECONCILED / ARCHIVED |
| SP-019 | Daily Review Read Model & Deterministic Follow-up View | APPROVED / MERGED / POST_MERGE_VERIFIED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| SP-020 | Local Daily Operating Loop & Review-to-Action Closure | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / ACC_020_PASSED / INDEPENDENT_EVIDENCE_REVIEW_APPROVED / RECONCILED / ARCHIVED |

ACC-016、ACC-017、ACC-018、ACC-019 与 ACC-020 均为 PASSED / FINAL。SP-020 的 RFC-029 为 Adopted，ADR-063、ADR-064 为 Accepted；Feature PR #57 已 Squash Merge 为 `9ea4b72241bd855319231c09fa6b80c112a14305`，main Quality Gate `30687851816` 为 SUCCESS，SP-020A 对账载体为 PR #58，并完成治理对账与封存。`v0.34.0` 历史发布不变；当前 `0.35.0` 仍未发布。

REL-035 规划冻结无破坏性迁移、缺失 `followups.db` 时增量初始化、Local Daily Profile
显式配置升级，以及 Planning Approval、Implementation Approval、Release PR Merge、Tag
Authorization、GitHub Release Authorization 五个独立治理事件。规划不等于发布日期承诺。

## 后续候选版本

| 候选版本 | 候选方向 | 状态 |
|---|---|---|
| v0.36.0 | Recurring Reminder | CANDIDATE / NOT_APPROVED / NOT_SCHEDULED |
| v0.37.0 | Minimal Web Console | CANDIDATE / NOT_APPROVED / NOT_SCHEDULED |
| v0.40.0 或更后 | Knowledge Main Path | CANDIDATE / NOT_APPROVED / NOT_SCHEDULED |

这些版本没有承诺发布日期。

## 更远期方向

| 版本方向 | 候选目标 |
|---|---|
| v0.40.0 | 多应用与更完整的 Agent/Tool/MCP 产品闭环 |
| v0.50.0 | 受控业务系统与企业集成 |
| v1.0.0 | 满足独立生产就绪标准后的稳定发布 |

这些目标均为 tentative，不构成承诺。

## 已完成基线

- v0.33.0：Composition Root、失败语义、DatabaseManager 所有权与版本治理基线。
- post-v0.33.0 至 v0.34.0 Alpha：UserTask、Reminder、Intent Safety、Daily Agenda、Unified Inbox、Capture-to-Action 与 API/CLI/CEO Assistant 产品闭环。
- ACC-014：A～L PASSED / FINAL。
- SP-015：APPROVED / MERGED / POST_MERGE_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED。
- SP-015A、SP-015R：APPROVED / MERGED / RECONCILED / ARCHIVED。
- SP-016：COMPLETED / MANUAL_ACCEPTANCE_PASSED / ARCHIVED；ACC-016：PASSED / FINAL。
