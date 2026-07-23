# AI-Lab Project Health

**Last Updated:** 2026-07-23
**Current Source Version:** v0.34.0 Alpha / Release Authorized

## Summary

AI-Lab 当前是本地优先、单用户导向的 Alpha 系统。Canonical Waiting-For、确定性 Follow-up Interaction 与 Inbox-to-Waiting-For conversion 已集成、通过人工验收并封存，Daily Agenda 使用可选来源组合。这些能力不等同于生产级多用户平台。

| Metric | Current fact |
|---|---|
| Verified release baseline | `22f88d1da962fb436c48c19e5343fad8bf62f5f6` |
| GitHub Quality Gate | run `29855987444` / SUCCESS |
| pytest (non-real) | 1163 passed, 6 skipped, 27 warnings |
| SP-017 post-merge main | `32bb9c0a939c65f2278fc2b6be8d072fb2e3656a` / run `30006958413` / SUCCESS |
| SP-017 post-merge pytest (non-real) | 1239 passed, 6 skipped, 27 warnings |
| Ruff | Changed Python files gate / SUCCESS |
| Current product SP | None |
| Current governance task | None |
| Next candidate | SP-018 — Work Log Query Boundary & Context Closure / planning baseline / implementation not approved / not started |
| Latest completed SP | SP-017 / manual acceptance passed / archived |
| Release stage | Alpha / RELEASE_AUTHORIZED；Authorized Tag v0.34.0 / GitHub Pre-release |

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
| SP-018 planning | Planning baseline only / Not implemented | RFC-027 Proposed；ADR-058～060 Accepted；ACC-018 NOT_EXECUTED；生产代码未改变 |
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
