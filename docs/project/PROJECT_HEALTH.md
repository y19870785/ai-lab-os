# AI-Lab 项目健康状态

**最近更新：** 2026-08-06
**当前源码版本：** v0.35.0 Alpha / GitHub Pre-release Published

## 摘要

AI-Lab 当前是本地优先、单用户导向的 Alpha 系统。SP-020 已通过正式 ACC-020 A～V、独立证据复核与 main Quality Gate，并完成合并、对账和封存。`v0.35.0` GitHub Pre-release 已发布并远端验证，REL-035 已最终对账并封存。STRAT-001 与 ARCH-001 均已合并、通过 main Quality Gate 并完成对账封存；当前 Product SP 与 Governance Task 均为 None。SP-021 是下一候选 Product SP，但未启动且需要单独授权。这些能力不等同于 production-ready 或完整多用户平台。

| 指标 | 当前事实 |
|---|---|
| Verified release baseline | `22f88d1da962fb436c48c19e5343fad8bf62f5f6` |
| GitHub Quality Gate | run `29855987444` / SUCCESS |
| pytest (non-real) | 1163 passed, 6 skipped, 27 warnings |
| SP-017 post-merge main | `32bb9c0a939c65f2278fc2b6be8d072fb2e3656a` / run `30006958413` / SUCCESS |
| SP-017 post-merge pytest (non-real) | 1239 passed, 6 skipped, 27 warnings |
| SP-018 post-merge main | `83ecb557fedd1d898712afc59ad13b3e0a684413` / run `30196719409` / SUCCESS |
| SP-019 planning merge baseline | `e7fc5b1dd66ff7828c1697bfd5610f300599eee5` / run `30205853257` / SUCCESS |
| SP-019 feature merge main | `a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49` / run `30382312419` / SUCCESS |
| SP-019 reconciliation merge main | `934075ceefe39ede3c624b621b7673d62f6d06dd` / run `30387237549` / SUCCESS |
| Ruff | Changed Python files gate / SUCCESS |
| Current product SP | None |
| Current governance task | None |
| ARCH-001 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED |
| RFC-032 / ADR-069～072 | Adopted / Accepted |
| Next candidate Product SP | SP-021 / Canonical Trusted Interaction Domain / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION / IMPLEMENTATION_NOT_APPROVED |
| Next planned governance item | None |
| STRAT-001 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED |
| STRAT-001 main Quality Gate | `31038950753` / SUCCESS |
| REL-035 | FINAL_RECONCILED / ARCHIVED |
| DOCS-001 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / RECONCILED / ARCHIVED |
| DOCS-001 merge | PR #55 / `2d04f1b8574fde43b1d64a53d1ad22573073a4ef` / `2026-07-29T14:43:26Z` |
| DOCS-001 main Quality Gate | run `30462290819` / SUCCESS |
| Next candidate | None |
| PR #62 | CLOSED / NOT_MERGED / SUPERSEDED_BY_STRAT_001 / IMPLEMENTATION_NEVER_AUTHORIZED |
| SP-020 | APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / ACC_020_PASSED / INDEPENDENT_EVIDENCE_REVIEW_APPROVED / RECONCILED / ARCHIVED |
| ACC-020 | PASSED / FINAL |
| SP-020 planning merge | PR #53 / `fbd10fb5c4cd3913bb70d0c17cdd6df9de196625` / run `30441534383` / SUCCESS |
| SP-020 feature merge | PR #57 / `9ea4b72241bd855319231c09fa6b80c112a14305` / run `30687851816` / SUCCESS |
| SP-020 reconciliation | SP-020A / PR #58 |
| SP-019 Phase 0 | UserTask Workspace Query Closure / ACCEPTED |
| SP-019 Daily Review | MERGED / VERIFIED / ACCEPTED / ARCHIVED |
| Latest completed SP | SP-020 / ACC-020 PASSED / FINAL / reconciled / archived |
| Release stage | v0.35.0 Alpha / PRE_RELEASE_PUBLISHED |
| v0.35.0 publication | Local Daily Operating Loop / PUBLISHED / PRE-RELEASE / REMOTE_VERIFIED / Assets 0 |

```text
SP-020:
APPROVED /
MERGED /
MAIN_QUALITY_GATE_PASSED /
ACC_020_PASSED /
INDEPENDENT_EVIDENCE_REVIEW_APPROVED /
RECONCILED /
ARCHIVED

ACC-020:
PASSED / FINAL

Approved Implementation Head:
1c9b69ee45b4e1545b67ecd841cc217e23d4f38f

Acceptance Evidence Head:
7a0944f4ad1deadefe636bf5abc3d30175de0b4d

Formal Run:
ai-lab-acc020-formal-20260730-175832-eda685f89c274e6cb520c0aaa964b3dc

Provider Calls:
0

Evidence Review:
APPROVED

Feature Merge Commit:
9ea4b72241bd855319231c09fa6b80c112a14305

Main Quality Gate:
30687851816 / SUCCESS

Reconciliation PR:
58
```

当前 GitHub main HEAD、Pull Request 状态和最新 Workflow run 是通过 Git/GitHub 实时查询的外部事实，不在本页维护自指的 `Current main` 镜像。

## 模块健康度

| 模块 | 状态 | 边界 |
|---|---|---|
| Core / Database / Memory | Integrated / Verified | Composition Root、失败语义与连接所有权已收口 |
| Provider / Agent / Workflow / Task | Integrated / Verified | 真实 Provider 需单独授权配置，不属于普通门禁 |
| UserTask | Integrated / Verified | Canonical domain 与 `tasks.db` |
| Reminder / Scheduler | Integrated / Verified / Disabled by default | 外部通知和 Recurring Reminder 未实现 |
| Intent Safety / Daily Agenda | Integrated / Verified / Optional-source composition | 确定性路由与聚合读取，不是通用 NLP |
| Waiting-For | Integrated / Verified / Manual acceptance passed | SP-016 与 SP-017 completed / archived；独立 canonical domain、确定性交互与 `followups.db` |
| Unified Inbox / Capture-to-Action | Integrated / Verified | workspace 隔离、持久化 resolution claim 与幂等已验收 |
| SP-017 interaction closure | Integrated / Verified / Archived | ACC-017 A～O PASSED / FINAL；RFC-026 Adopted；ADR-056、ADR-057 Accepted |
| Work Log / SP-018 | Integrated / Verified / Archived | RFC-027 Adopted；ADR-058～060 Accepted；ACC-018 A～O PASSED / FINAL |
| Daily Review / SP-019 | Integrated / Verified / Manual acceptance passed | RFC-028 Adopted；ADR-061、ADR-062 Accepted；ACC-019 A～M PASSED / FINAL；SP-019 archived |
| Local Daily Loop / SP-020 | Integrated / Verified / Archived | RFC-029 Adopted；ADR-063、ADR-064 Accepted；ACC-020 PASSED / FINAL；main Quality Gate SUCCESS |
| Knowledge | Implemented / Disabled | Reindex、Chunk Persistence、Citation 与真实主链路未完成 |
| Tool Runtime / MCP | Integrated | 自动 Tool Calling 和完整 MCP 产品闭环未完成 |
| Coordination | Implemented / Disabled | 未接入 CEO Assistant 主链路 |
| API / CLI / CEO Assistant | Integrated / Verified / Alpha | 仍是本地 Alpha 使用边界 |

## 未关闭质量债务

- QUALITY-001：Ruff 是 changed-files gate，不代表全仓历史 Ruff 已清零。
- Scheduler 测试曾出现一次短暂 `running` 时序波动；唯一重跑通过，未在 SP-014B 或 SP-015 中修改 Scheduler。
- Docker build/run、长时间运行、资源回收和高并发仍缺正式基线。
- Local Daily Profile 已要求显式绝对 data/sqlite root；Phase 0 自动化门禁已验证 shutdown
  幂等、partial-start rollback、持续运行与新容器恢复；正式静止备份与隔离恢复已由 ACC-020 验收通过。

CI-002 与 AGENDA-001 已解决：real-provider collection skip 只作用于 `tests/real`；Daily Agenda 会跳过未启用来源，并对已启用来源的运行错误失败关闭。

机器可读详情、历史 PR 对账与稳定发布授权配置以根 `project_state.json` 为准。Tag/Release 的存在性、目标、URL 与时间以 GitHub 为权威来源。
