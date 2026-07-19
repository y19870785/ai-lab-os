# AI-Lab Project Status

**Date:** 2026-07-20
**Source Version:** v0.34.0 Alpha Candidate
**Canonical main baseline:** `57444274abd4e568a6af72b218d50290de563654`

## Current governance state

| Item | State |
|---|---|
| SP-014 | APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED |
| SP-014B | APPROVED / MERGED / VERIFIED / RECONCILED / ARCHIVED |
| ACC-014 | PASSED / FINAL（A～L 全部通过） |
| SP-015 | APPROVED / IN_PROGRESS |
| SP-016 | CANDIDATE / NOT_APPROVED / NOT_STARTED |

根目录 `project_state.json` 是唯一机器可读实时项目状态源；本页是便于人工阅读的摘要。运行时产品版本仍只来自 `pyproject.toml`。

## Product baseline

v0.34.0 Alpha Candidate 汇总 Canonical UserTask、Reminder、Intent Safety、Daily Agenda、Unified Inbox 与 Capture-to-Action。Reminder 和 Scheduler 能力已集成并验证，但默认关闭；Knowledge 和 Coordination 仍不是默认主链路。

SP-014 通过 PR #32 合并，SP-014B 通过 PR #33 合并，最终治理对账通过 PR #34 合并。ACC-014 的场景 A～L 均为 PASSED，场景 K 的中文小时兼容缺口已由 SP-014B 修复并在 main 复验。

## Quality baseline

当前 main 的正式 GitHub Quality Gate 为 run `29691702903`：Ruff SUCCESS，pytest (non-real) SUCCESS，`1154 passed, 6 skipped, 27 warnings`。真实 Provider 测试不属于普通门禁。

## Release state

- 源码版本：`0.34.0`
- 成熟度：Alpha / local-first / single-user-oriented
- 上一 Tag：`v0.33.0`
- v0.34.0 Tag：未创建
- v0.34.0 GitHub Release：未创建
- 发布阻断：SP-015 合并、合并后验收、Release reconciliation

SP-015 只做状态、版本与发布治理收口，不修改业务语义或数据库 schema。后续 SP-016 仅为候选，不得由本状态自动启动。
