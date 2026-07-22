# AI-Lab Roadmap

**Last Updated:** 2026-07-22
**Current Version:** v0.34.0 Alpha / Release Authorized
**Current SP:** None — SP-015, SP-015A and SP-015R archived; no current governance task

Roadmap 只描述版本范围、里程碑与候选任务。已完成 SP 的 PR、Head、merge commit 和验收状态以根目录 `project_state.json` 为唯一机器可读来源；用户可见版本变化记录在 `CHANGELOG.md` 和版本化 Release Notes。

## 版本与 SP 的关系

- 产品版本由若干 SP 共同组成；SP 编号是开发批次，不等同于产品版本。
- 每个产品版本必须明确功能范围、验收结果、Tag 和 Release Notes。
- 候选 SP 不代表已经批准、排期或启动。

## v0.34.0 Alpha

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

## v0.35.0 候选方向

以下顺序仅为候选规划：

| 候选 SP | 方向 | 状态 |
|---|---|---|
| SP-016 | Follow-up & Waiting-For Workflow | CANDIDATE / NOT_APPROVED / NOT_STARTED |
| SP-017 | Recurring Reminder | CANDIDATE / NOT_APPROVED / NOT_STARTED |
| SP-018 | Minimal Web Console | CANDIDATE / NOT_APPROVED / NOT_STARTED |
| SP-019 | Knowledge Main Path | CANDIDATE / NOT_APPROVED / NOT_STARTED |

每个候选都需要独立任务书、范围审查、质量门禁和人工验收；SP-015 不包含这些能力的设计或实现。

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
