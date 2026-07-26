# AI-Lab Project Health

**Last Updated:** 2026-07-26
**Current Source Version:** v0.34.0 Alpha / Release Authorized

## Summary

AI-Lab 当前是本地优先、单用户导向的 Alpha 系统。SP-018 canonical Work Log 查询边界已合并，ACC-018 A～O 与 post-merge verification 均已通过。SP-019 Planning Baseline 已 APPROVED / MERGED / RECONCILED，但 Implementation 仍为 NOT APPROVED / NOT STARTED。这些能力不等同于生产级多用户平台。

| Metric | Current fact |
|---|---|
| Verified release baseline | `22f88d1da962fb436c48c19e5343fad8bf62f5f6` |
| GitHub Quality Gate | run `29855987444` / SUCCESS |
| pytest (non-real) | 1163 passed, 6 skipped, 27 warnings |
| SP-017 post-merge main | `32bb9c0a939c65f2278fc2b6be8d072fb2e3656a` / run `30006958413` / SUCCESS |
| SP-017 post-merge pytest (non-real) | 1239 passed, 6 skipped, 27 warnings |
| SP-018 post-merge main | `83ecb557fedd1d898712afc59ad13b3e0a684413` / run `30196719409` / SUCCESS |
| SP-019 planning merge baseline | `e7fc5b1dd66ff7828c1697bfd5610f300599eee5` / run `30205853257` / SUCCESS |
| Ruff | Changed Python files gate / SUCCESS |
| Current product SP | SP-019 |
| Current governance task | None |
| Next candidate | None — SP-019 is current |
| SP-019 Phase 0 | UserTask Workspace Query Closure / IMPLEMENTED / PENDING ACCEPTANCE |
| SP-019 Daily Review | NOT STARTED |
| Latest completed SP | SP-018 / manual acceptance passed / post-merge verified / archived |
| Release stage | Alpha / RELEASE_AUTHORIZED；Authorized Tag v0.34.0 / GitHub Pre-release |

当前 GitHub main HEAD、Pull Request 状态和最新 Workflow run 是通过 Git/GitHub 实时查询的外部事实，不在本页维护自指的 `Current main` 镜像。

## Module health

| Module | State | Boundary |
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
| Daily Review / SP-019 | Planning baseline approved, merged and reconciled / Not implemented | RFC-028、ADR-061、ADR-062 Proposed / Planning Baseline；ACC-019 PLANNING_BASELINE / NOT_EXECUTED；UserTask Workspace query closure is Phase 0 |
| Knowledge | Implemented / Disabled | Reindex、Chunk Persistence、Citation 与真实主链路未完成 |
| Tool Runtime / MCP | Integrated | 自动 Tool Calling 和完整 MCP 产品闭环未完成 |
| Coordination | Implemented / Disabled | 未接入 CEO Assistant 主链路 |
| API / CLI / CEO Assistant | Integrated / Verified / Alpha | 仍是本地 Alpha 使用边界 |

## Open quality debt

- QUALITY-001：Ruff 是 changed-files gate，不代表全仓历史 Ruff 已清零。
- Scheduler 测试曾出现一次短暂 `running` 时序波动；唯一重跑通过，未在 SP-014B 或 SP-015 中修改 Scheduler。
- Docker build/run、长时间运行、资源回收和高并发仍缺正式基线。

CI-002 与 AGENDA-001 已解决：real-provider collection skip 只作用于 `tests/real`；Daily Agenda 会跳过未启用来源，并对已启用来源的运行错误失败关闭。

机器可读详情、历史 PR 对账与稳定发布授权配置以根 `project_state.json` 为准。Tag/Release 的存在性、目标、URL 与时间以 GitHub 为权威来源。
